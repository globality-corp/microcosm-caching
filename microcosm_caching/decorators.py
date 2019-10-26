from functools import wraps
from logging import Logger
from time import perf_counter
from typing import Any, Optional, Type

from marshmallow import Schema
from microcosm.errors import NotBoundError
from pymemcache.exceptions import MemcacheError

from microcosm_caching.base import CacheBase


DEFAULT_TTL = 60 * 60  # Cache for an hour by default


def get_metrics(graph):
    try:
        return graph.metrics
    except NotBoundError:
        return None


def cache_key(cache_prefix, key):
    return f"{cache_prefix}:{key}"


def cached(component, schema: Type[Schema], cache_prefix: str, ttl: int = DEFAULT_TTL):
    """
    Intended mainly for use as a decorator around microcosm_flask.CRUDStoreAdapters, namely
    those revolving around retrieve functions, such that the resource is identifiable
    by a single ID.

    Decorated components must expose:
      * an identifier_key function
      * a logger reference
      * the graph

    :param component: A microcosm-based controller component
    :param schema: The schema corresponding to the response type of the component
    :param cache_prefix: Namespace to use for cache keys
    :param ttl: How long to cache the underlying resource
    :return: the resource (i.e. loaded schema instance)
    """
    identifier_key: str = getattr(component, "identifier_key")
    logger: Logger = getattr(component, "logger")

    graph = component.graph
    metrics = get_metrics(graph)
    resource_cache: Optional[CacheBase] = graph.resource_cache

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

    def set_in_cache(key: str, value: Any) -> None:
        start_time = perf_counter()

        resource_cache.set(key, value, ttl=ttl)

        elapsed_ms = (perf_counter() - start_time) * 1000

        if metrics:
            tags = [
                "action:set",
                f"resource:{schema.__name__}",
            ]

            metrics.timing("cache_timing", elapsed_ms, tags=tags)
            metrics.increment("cache_set", tags=tags)

    def decorator(func):
        @wraps(func)
        def cache(*args, **kwargs) -> Schema:
            if not resource_cache:
                return func(*args, **kwargs)

            try:
                key = cache_key(cache_prefix, kwargs[identifier_key])
                cached_resource = retrieve_from_cache(key)
                if not cached_resource:
                    resource = func(*args, **kwargs)
                    cached_resource = schema().dump(resource)
                    set_in_cache( key, cached_resource )

                # NB: We're caching the serialized format of the resource, meaning
                # we need to do a (wasteful) load here to enable it to be dumped correctly
                # later on in the flow. This could probably be made more efficient
                return schema().load(cached_resource, unknown="exclude")
            except (MemcacheError, ConnectionRefusedError) as error:
                logger.warning("Unable to retrieve/save cache data", extra=dict(error=error))
                return func(*args, **kwargs)

        return cache
    return decorator


