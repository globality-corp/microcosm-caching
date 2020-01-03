"""
Serialization helpers for caching.

"""
from enum import IntEnum, unique
from typing import Optional, Tuple

from pymemcache.client.hash import HashClient
from pymemcache.test.utils import MockMemcacheClient
from simplejson import dumps, loads

from microcosm_caching.base import CacheBase


@unique
class SerializationFlag(IntEnum):
    """
    Used by caching backends to control how to serialize
    or deserialize cached values.

    Memcached is the primary use case.

    """
    STRING = 1
    JSON = 2


class JsonSerializerDeserializer:
    """
    Simple JSON serializer for use with caching backends
    that only support string/bytes value storage.

    Memcached is the primary use case.

    """

    def serialize(self, key, value):
        if isinstance(value, str) or isinstance(value, bytes):
            return value, SerializationFlag.STRING.value

        return dumps(value), SerializationFlag.JSON.value

    def deserialize(self, key, value, flags):
        if flags == SerializationFlag.STRING:
            if isinstance(value, bytes):
                value = value.decode("utf-8")
            return value
        elif flags == SerializationFlag.JSON:
            return loads(value)

        raise ValueError(f"Unknown serialization format flags: {flags}")


class MemcachedCache(CacheBase):
    """
    Memcached-backed cache implementation.

    Compatible with AWS ElastiCache when using their memcached interface.

    """
    def __init__(
        self,
        servers: Optional[Tuple[str, int]] = None,
        connect_timeout=None,
        read_timeout=None,
        serde=None,
        testing=False,
    ):
        client_kwargs = dict(
            connect_timeout=connect_timeout,
            timeout=read_timeout,
            serde=serde or JsonSerializerDeserializer(),
        )

        if testing:
            self.client = MockMemcacheClient(
                server=None,
                **client_kwargs,
            )
        else:
            self.client = HashClient(
                servers=servers,
                **client_kwargs,
            )

    def get(self, key: str):
        """
        Return the value for a key, or None if not found

        """
        return self.client.get(key)

    def add(self, key: str, value, ttl=None):
        """
        Set the value for a key, but only that key hasn't been set.

        """
        if ttl is None:
            # pymemcache interprets 0 as no expiration
            ttl = 0
        # NB: If input is malformed, this will not raise errors.
        # set `noreply` to False for further debugging
        return self.client.add(key, value, expire=ttl)

    def set(self, key: str, value, ttl=None):
        """
        Set the value for a key, but overwriting existing values

        """
        if ttl is None:
            # pymemcache interprets 0 as no expiration
            ttl = 0
        # NB: If input is malformed, this will not raise errors.
        # set `noreply` to False for further debugging
        return self.client.set(key, value, expire=ttl)

    def set_many(self, values, ttl=None):
        """
        Set the many key-value pairs at a time, overwriting existing values

        """
        if ttl is None:
            # pymemcache interprets 0 as no expiration
            ttl = 0

        return self.client.set_many(values, expire=ttl)
