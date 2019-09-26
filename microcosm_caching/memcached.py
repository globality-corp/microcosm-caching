"""
Serialization helpers for caching.

"""
from enum import IntEnum, unique
from json import dumps, loads
from typing import Optional, Tuple

from pymemcache.client.hash import HashClient
from pymemcache.test.utils import MockMemcacheClient

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


def json_serializer(key, value):
    """
    Simple JSON serializer for use with caching backends
    that only support string/bytes value storage.

    Memcached is the primary use case.

    """
    if isinstance(value, str) or isinstance(value, bytes):
        return value, SerializationFlag.STRING.value

    return dumps(value), SerializationFlag.JSON.value


def json_deserializer(key, value, flags):
    """
    Simple JSON deserializer for use with caching backends
    that only support string/bytes value storage.

    Memcached is the primary use case.

    """
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
        serializer=json_serializer,
        deserializer=json_deserializer,
        testing=False,
    ):
        client_kwargs = dict(
            connect_timeout=connect_timeout,
            timeout=read_timeout,
            serializer=serializer,
            deserializer=deserializer,
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
        return self.client.get(key)

    def set(self, key: str, value, ttl=None):
        if ttl is None:
            # pymemcache interprets 0 as no expiration
            ttl = 0
        # NB: If input is malformed, this will not raise errors.
        # set `noreply` to False for further debugging
        return self.client.set(key, value, expire=ttl)
