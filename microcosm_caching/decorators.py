"""
Fluent decorators for resources and handlers.

"""
from functools import wraps


def cacheable(endpoint):
    """
    Decorate a microcosm controller method for an API route as cacheable.

    """
    @wraps(endpoint)
    def decorator(func):
        return func
    return decorator
