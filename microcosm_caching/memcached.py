"""
Serialization helpers for caching.

"""
from enum import IntEnum, unique
from json import dumps, loads

from pymemcache.client.base import Client
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
        return value, SerializationFlag.STRING

    return dumps(value), SerializationFlag.JSON


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
        host="localhost",
        port=11211,
        connect_timeout=None,
        read_timeout=None,
        serializer=json_serializer,
        deserializer=json_deserializer,
        testing=False,
    ):
        client_kwargs = dict(
            server=(host, port),
            connect_timeout=connect_timeout,
            timeout=read_timeout,
            serializer=json_serializer,
            deserializer=json_deserializer,
        )
        if testing:
            self.client = MockMemcacheClient(**client_kwargs)
        else:
            self.client = Client(**client_kwargs)

    def get(self, key):
        return self.client.get(key)

    def set(self, key, value, ttl=None):
        if ttl is None:
            # pymemcache interprets 0 as no expiration
            ttl = 0
        return self.client.set(key, value, expire=ttl)
