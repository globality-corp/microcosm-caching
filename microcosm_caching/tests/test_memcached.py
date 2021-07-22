"""
Unit-tests for memcached cache backend.

"""
from decimal import Decimal
from time import sleep

from hamcrest import assert_that, equal_to, is_
from microcosm_caching.memcached import MemcachedCache
from parameterized import parameterized


class TestMemcachedCache:

    def setup(self):
        self.cache = MemcachedCache(testing=True)

    @parameterized([
        ("key", "string-value"),
        ("http://globality.io/resource/98f6c9ec-043f-4997-b98d-c72b5088c204", dict(
            foo="bar",
            bar=1,
            baz=123.45,
            nested=dict(nested_key="nested_value"),
            lst=["1", "2", "3"],
        )),
        ("key", Decimal("10000.0")),
    ])
    def test_set_and_get_value(self, key, value):
        self.cache.set(key, value)

        assert_that(
            self.cache.get(key),
            is_(equal_to(value)),
        )

    def test_set_with_ttl_works(self):
        self.cache.set("key", "value", ttl=1)

        assert_that(
            self.cache.get("key"),
            is_(equal_to("value")),
        )

        # retrieving key again should fail once ttl expired
        # Nb. using sleep in unit-tests is not a best practice generally.
        sleep(1)
        assert_that(
            self.cache.get("key"),
            is_(equal_to(None)),
        )
