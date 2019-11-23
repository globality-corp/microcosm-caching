from dataclasses import dataclass
from functools import wraps
from hashlib import sha1
from logging import Logger
from time import perf_counter
from typing import (
    Any,
    Dict,
    List,
    Optional,
    Type,
)

from marshmallow import EXCLUDE, Schema
from microcosm.errors import NotBoundError
from pymemcache.exceptions import MemcacheError

from microcosm_caching.base import CacheBase
from microcosm_caching.build_info import BuildInfo


DEFAULT_TTL = 60 * 60  # Cache for an hour by default
DEFAULT_LOCK_TTL = 3  # Stop incoming writes for 3 seconds by default


def get_metrics(graph):
    try:
        return graph.metrics
    except NotBoundError:
        return None


def get_build_version(graph) -> Optional[str]:
    build_info: BuildInfo = graph.build_info
    return build_info.sha1


@dataclass
class Invalidation:
    schema: Type[Schema]
    arguments: List[str]
    kwarg_mappings: Optional[Dict[str, str]] = None

    def from_kwargs(self, kwargs) -> Dict[str, Any]:
        """
        Constructs invalidation kwargs based on known search arguments

        """
        # Default case, no need for special mappings
        if not self.kwarg_mappings:
            return {
                argument: kwargs[argument]
                for argument in self.arguments
            }

        invalidation_kwargs: Dict[str, Any] = {}
        for argument in self.arguments:
            try:
                invalidation_kwargs[argument] = kwargs[argument]
            except KeyError:
                mapped_argument = self.kwarg_mappings[argument]
                invalidation_kwargs[argument] = kwargs[mapped_argument]

        return invalidation_kwargs


def cache_key(cache_prefix, schema, args, kwargs, version: Optional[str] = None) -> str:
    """
    Hash a key according to the schema and input args.

    """
    key = (schema.__name__,) + args
    key += tuple(sorted((a, b) for a, b in kwargs.items()))

    return sha1(f"{cache_prefix}:{version}:{key}".encode("utf-8")).hexdigest()


def cached(
    component,
    schema: Type[Schema],
    cache_prefix: Optional[str] = None,
    ttl: int = DEFAULT_TTL,
    schema_version: Optional[str] = None,
):
    """
    Caches the result of a decorated component function, given that the both the underlying
    function and the component itself adhere to a given structure.

    Decorated components must expose:
      * an identifier_key function
      * a logger reference
      * the graph

    The cached resource must be:
      * Adhere to a given Schema resource
      * Be identifiable by a single ID

    Main usage expected here is for a CRUDStoreAdapter subclass, but may be usable in other contexts as well.

    Example usage:
        cached(component, ConcreteSchema, "prefix")(component.retrieve)

    :param component: A microcosm-based component
    :param schema: The schema corresponding to the response type of the component
    :param cache_prefix: Namespace to use for cache keys. Defaults to the name attached to the graph
    :param ttl: How long to cache the underlying resource
    :param schema_version: The version of this schema. Used as part of the cache key. If not supplied,
                           will default to the build version, if supplied
    :return: the resource (i.e. loaded schema instance)
    """
    logger: Logger = getattr(component, "logger")

    graph = component.graph
    metrics = get_metrics(graph)
    resource_cache: CacheBase = graph.resource_cache

    version = schema_version or get_build_version(graph)
    cache_prefix = cache_prefix or graph.metadata.name

    def retrieve_from_cache(key: str):
        start_time = perf_counter()

        resource = resource_cache.get(key)

        elapsed_ms = (perf_counter() - start_time) * 1000

        if metrics:
            tags = [
                "action:get",
                f"resource:{schema.__name__}",
            ]

            metrics.timing("cache_timing", elapsed_ms, tags=tags)

            if resource:
                metrics.increment("cache_hit", tags=tags)
            else:
                metrics.increment("cache_miss", tags=tags)

        return resource

    def add_in_cache(key: str, value: Any) -> None:
        start_time = perf_counter()

        resource_cache.add(key, value, ttl=ttl)

        elapsed_ms = (perf_counter() - start_time) * 1000

        if metrics:
            tags = [
                "action:add",
                f"resource:{schema.__name__}",
            ]

            metrics.timing("cache_timing", elapsed_ms, tags=tags)
            metrics.increment("cache_add", tags=tags)

    def decorator(func):
        @wraps(func)
        def cache(*args, **kwargs) -> Schema:
            if not resource_cache:
                return func(*args, **kwargs)

            try:
                key = cache_key(cache_prefix, schema, args, kwargs, version)
                cached_resource = retrieve_from_cache(key)
                if not cached_resource:
                    resource = func(*args, **kwargs)
                    cached_resource = schema().dump(resource)
                    add_in_cache(key, cached_resource)

                # NB: We're caching the serialized format of the resource, meaning
                # we need to do a (wasteful) load here to enable it to be dumped correctly
                # later on in the flow. This could probably be made more efficient
                return schema().load(cached_resource, unknown=EXCLUDE)
            except (MemcacheError, ConnectionRefusedError) as error:
                logger.warning("Unable to retrieve/save cache data", extra=dict(error=error))
                return func(*args, **kwargs)

        return cache
    return decorator


def invalidates(
    component,
    invalidations: List[Invalidation],
    cache_prefix: Optional[str] = None,
    lock_ttl=DEFAULT_LOCK_TTL,
    schema_version: Optional[str] = None,
):
    """
    Invalidates a set of prescribed keys, based on a combination of:
        * specified arguments
        * schema

    Note: this does require that the input args to the given function correspond to the
    invalidation args given. As such, using it conjunction with certain functions (such as
    a plain delete) may not provide sufficient context for invalidation, and caching should
    not be used in such scenarios.

    """
    graph = component.graph
    metrics = get_metrics(graph)
    resource_cache: CacheBase = graph.resource_cache

    version = schema_version or get_build_version(graph)
    cache_prefix = cache_prefix or graph.metadata.name

    def delete_from_cache(values) -> None:
        """
        "Delete" from cache by locking writes to a key for a designated
        amount of time.

        In conjunction with the cached() decorator, this allows the "get and set"
        flow to behave without special cases

        """
        start_time = perf_counter()

        resource_cache.set_many(values, ttl=lock_ttl)

        elapsed_ms = (perf_counter() - start_time) * 1000

        if metrics:
            tags = [
                "action:set_many",
            ]

            metrics.timing("cache_timing", elapsed_ms, tags=tags)
            metrics.increment("cache_set_many", tags=tags)

    def decorator(func):
        @wraps(func)
        def cache(*args, **kwargs) -> Schema:
            if not resource_cache:
                return func(*args, **kwargs)

            values: Dict[str, None] = {}
            for invalidation in invalidations:
                invalidation_kwargs = invalidation.from_kwargs(kwargs)

                # NB: We assume that we don't cache via args
                key = cache_key(cache_prefix, invalidation.schema, (), invalidation_kwargs, version)
                values[key] = None

            result = func(*args, **kwargs)
            # NB: Exceptions raised from cache operations aren't caught here;
            # This will prevent stale data from persisting after request completion
            delete_from_cache(values)

            return result

        return cache
    return decorator


def invalidate_batch(
    component,
    batch_attribute,
    invalidations: List[Invalidation],
    cache_prefix: Optional[str] = None,
    lock_ttl=DEFAULT_LOCK_TTL,
    schema_version: Optional[str] = None,
):
    """
    Invalidates a set of prescribed keys, based on a combination of:
        * specified arguments
        * schema
        * a "batch" attribute

    This function is meant for cases of batch uploads, such that there would
    exist a set of resources created as a part of this operation which may each
    need to trigger their own invalidations. This is subject to the same limitations
    as the `invalidates` decorator.

    """
    graph = component.graph
    metrics = get_metrics(graph)
    resource_cache: CacheBase = graph.resource_cache

    version = schema_version or get_build_version(graph)
    cache_prefix = cache_prefix or graph.metadata.name

    def delete_from_cache(values) -> None:
        """
        "Delete" from cache by locking writes to a key for a designated
        amount of time.

        In conjunction with the cached() decorator, this allows the "get and set"
        flow to behave without special cases

        """
        start_time = perf_counter()

        resource_cache.set_many(values, ttl=lock_ttl)

        elapsed_ms = (perf_counter() - start_time) * 1000

        if metrics:
            tags = [
                "action:set_many",
            ]

            metrics.timing("cache_timing", elapsed_ms, tags=tags)
            metrics.increment("cache_set_many", tags=tags)

    def decorator(func):
        @wraps(func)
        def cache(*args, **kwargs) -> Schema:
            if not resource_cache:
                return func(*args, **kwargs)

            values: Dict[str, None] = {}
            for item in kwargs[batch_attribute]:
                # NB: We assume that we don't cache via args
                for invalidation in invalidations:
                    invalidation_kwargs = invalidation.from_kwargs(item)
                    key = cache_key(cache_prefix, invalidation.schema, (), invalidation_kwargs, version)
                    values[key] = None

            batch_result = func(*args, **kwargs)
            # NB: Exceptions raised from cache operations aren't caught here;
            # This will prevent stale data from persisting after request completion
            delete_from_cache(values)

            return batch_result
        return cache
    return decorator
