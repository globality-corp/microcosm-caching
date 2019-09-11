"""
Cache abstractions for use with API resources.

"""
from abc import ABC, abstractmethod


class CacheBase(ABC):
    """
    A simple key-value cache interface.

    """
    @abstractmethod
    def get(self, key):
        pass

    @abstractmethod
    def set(self, key, value, ttl=None):
        """
        Set a key, value pair to the cache.

        Optional ttl (time-to-live) value should be in seconds.

        """
        pass
