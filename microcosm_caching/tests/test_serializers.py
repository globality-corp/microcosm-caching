from json import dumps

from hamcrest import assert_that, is_
from parameterized import parameterized

from microcosm_caching.memcached import (
    SerializationFlag,
    json_deserializer,
    json_serializer,
)


@parameterized([
    ("key", "string-value", ("string-value", SerializationFlag.STRING.value)),
    ("key", dict(foo="bar"), (dumps(dict(foo="bar")), SerializationFlag.JSON.value)),
])
def test_serializer(key, value, result):
    assert_that(json_serializer(key, value), is_(result))


@parameterized([
    ("key", "string-value", SerializationFlag.STRING.value, "string-value"),
    ("key", dumps(dict(foo="bar")), SerializationFlag.JSON.value, dict(foo="bar")),
])
def test_deserializer(key, value, flag, expected_value):
    assert_that(json_deserializer(key, value, flag), is_(expected_value))
