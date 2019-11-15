# microcosm_caching

Caching for microcosm microservices.

Provides a generic caching client, as well as as some common decorators / patterns to manage result caching

In general, caching is useful because:
* lookups are costly (either because they incur a network or computational cost)
* data may rarely change, relative to how often it's read

[![CircleCI](https://circleci.com/gh/globality-corp/microcosm-caching.svg?style=svg&circle-token=4d985d6947b5d753c6f3b779a2475f389e7c0ef1)](https://circleci.com/gh/globality-corp/microcosm-caching)

## Usage ##
This library exposes a `resource_cache` component in its entry points, automatically configuring a caching client
for general use for direct cache manipulation.

Common patterns have emerged out of common usages of this component, however, which we generalize into a general caching
strategy via several decorators.

### Decorators ###
`cached`:
```python
from typing import Type
from marshmallow import Schema

def cached(component, schema: Type[Schema], cache_prefix: str, ttl: int = DEFAULT_TTL):
    pass

# Example usage
return cached(component, ExampleSchema, "prefix")(component.func)
```
This performs a basic "get and set" for a result from a decorated function.

`invalidates` / `invalidates_batch`
```python
from typing import List

def invalidates(component, invalidations: List[Invalidation], cache_prefix, lock_ttl=DEFAULT_LOCK_TTL):
    pass
# example usage
return invalidates(component, cache_prefix=CACHE_PREFIX, invalidations=[
    Invalidation(
        ExampleSchema,
        arguments=["example_id"],
    )
])(component.func)
```
This will allow for the invalidation of a set of keys based on the *input* params of the function, such that they match
how a given resource is cached.

This may be useful if you want to invalidate a resource based on the creation of another resource (e.g. the creation of
another associated event with that resource).

This does add a limitation that those given params need to provide some link to the related resource. This may be
difficult in some cases, as that parameter may not exist.

An additional detail to the above is the actual invalidation strategy. Instead of directly deleting the cache key,
invalidation will render a given resource as uncacheable for a period of time, during which caching reads won't do anything.

This is done because we commonly cache in conjunction with another service such as a database, meaning that a
given request may not be done until that other service has completed (imagine a case where we invalidate, try to commit,
and find that that operation takes longer than we expect). If we were to simply delete, that would allow an interleaved
read to re-cache the now-stale data, if it happened to read right between the cache delete and a database commit.

So, as an important caveat: if that secondary operation starts taking longer than the lock TTL, you may find yourself
possibly caching stale data.
