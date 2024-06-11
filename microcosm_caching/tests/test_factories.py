"""
Unit-tests for memcached cache backend.

"""
import pytest
from hamcrest import assert_that, equal_to, is_
from microcosm.api import create_object_graph, load_from_dict

from microcosm_caching.factories import parse_server_config


class TestResourceCacheFactory:

    def setup_method(self):
        self.graph = create_object_graph(
            "test",
            testing=True,
            loader=load_from_dict(dict(
                resource_cache=dict(enabled=True),
            )),
        )

    @pytest.mark.parametrize(
        "key, value",
        [
            (
                    "http://globality.io/resource/98f6c9ec-043f-4997-b98d-c72b5088c204",
                    dict(
                        foo="bar",
                        bar=1,
                        baz=123.45,
                        nested=dict(nested_key="nested_value"),
                        lst=["1", "2", "3"],
                    ),
            ),
         ],
    )
    def test_set_and_get_value_when_resource_cache_is_enabled(self, key, value):
        self.graph.resource_cache.set(key, value)

        assert_that(
            self.graph.resource_cache.get(key),
            is_(equal_to(value)),
        )

    def test_parse_server_config(self):
        assert_that(
            parse_server_config(["server1:11211", "server2:22122"]),
            is_(
                [("server1", 11211), ("server2", 22122)],
            ),
        )
