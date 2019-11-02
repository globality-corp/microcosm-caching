from functools import wraps
from logging import Logger
from time import perf_counter
from typing import Any, Dict, Type

from marshmallow import Schema
from microcosm.errors import NotBoundError
from pymemcache.exceptions import MemcacheError

from microcosm_caching.base import CacheBase


DEFAULT_TTL = 60 * 60  # Cache for an hour by default
DEFAULT_LOCK_TTL = 3  # Stop incoming writes for 3 seconds by default


def get_metrics(graph):
    try:
        return graph.metrics
    except NotBoundError:
        return None


def cache_key(cache_prefix, schema, args, kwargs) -> str:
    """
    Hash a key according to the schema and input args.

    """
    key = (schema.__name__,) + args
    key += tuple(sorted((a, b) for a, b in kwargs.items()))
    key = hash(key)

    return f"{cache_prefix}:{key}"


def cached(component, schema: Type[Schema], cache_prefix: str, ttl: int = DEFAULT_TTL):
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
    :param cache_prefix: Namespace to use for cache keys
    :param ttl: How long to cache the underlying resource
    :return: the resource (i.e. loaded schema instance)
    """
    logger: Logger = getattr(component, "logger")

    graph = component.graph
    metrics = get_metrics(graph)
    resource_cache: CacheBase = graph.resource_cache

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
                key = cache_key(cache_prefix, schema, args, kwargs)
                cached_resource = retrieve_from_cache(key)
                if not cached_resource:
                    resource = func(*args, **kwargs)
                    cached_resource = schema().dump(resource)
                    add_in_cache(key, cached_resource)

                # NB: We're caching the serialized format of the resource, meaning
                # we need to do a (wasteful) load here to enable it to be dumped correctly
                # later on in the flow. This could probably be made more efficient
                return schema().load(cached_resource, unknown="exclude")
            except (MemcacheError, ConnectionRefusedError) as error:
                logger.warning("Unable to retrieve/save cache data", extra=dict(error=error))
                return func(*args, **kwargs)

        return cache
    return decorator


def invalidates(
    component,
    invalidations,
    cache_prefix,
    lock_ttl=DEFAULT_LOCK_TTL
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
            for schema, invalidation_kwargs in invalidations:
                # NB: We assume that we don't cache via args
                key = cache_key(cache_prefix, schema, (), {
                    invalidation_kwarg: kwargs[invalidation_kwarg]
                    for invalidation_kwarg in invalidation_kwargs
                })
                values[key] = None

            result = func(*args, **kwargs)
            # NB: Exceptions raised from cache operations aren't caught here;
            # This will prevent stale data from persisting after request completion
            delete_from_cache(values)

            return result

        return cache
    return decorator
