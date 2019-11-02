"""
Unit tests for decorators

"""
from hamcrest import assert_that, is_
from marshmallow import Schema, fields
from microcosm.api import binding, create_object_graph, load_from_dict
from microcosm_logging.decorators import logger

from microcosm_caching.decorators import cache_key, cached, invalidates


class TestSchema(Schema):
    key = fields.String(required=True)


class TestForSchema(Schema):
    values = fields.Integer(required=True)


@binding("controller")
@logger
class TestController:
    def __init__(self, graph):
        self.graph = graph
        self.calls = 0

    def retrieve(self, **kwargs):
        return {"key": "value"}

    def create(self, **kwargs):
        return

    def retrieve_for(self, **kwargs):
        self.calls += 1
        return {"values": self.calls}

    @property
    def identifier_key(self):
        return "key_id"


class TestDecorators:

    def setup(self):
        self.graph = create_object_graph(
            "test",
            testing=True,
            loader=load_from_dict(dict(
                resource_cache=dict(enabled=True),
            )),
        )
        self.graph.use(
            "controller",
        )
        self.cache_prefix = "test"
        controller = self.graph.controller

        self.cached_retrieve = cached(controller, TestSchema, self.cache_prefix)(controller.retrieve)

        self.cached_create = invalidates(
            controller,
            invalidations=[(TestForSchema, ("key_id",))],
            cache_prefix=self.cache_prefix,
        )(controller.create)

        self.cached_retrieve_for = cached(controller, TestForSchema, self.cache_prefix)(controller.retrieve_for)

    def test_cached(self):
        self.cached_retrieve(key_id=1)
        key = cache_key(self.cache_prefix, TestSchema, (), dict(key_id=1))
        assert_that(
            self.graph.resource_cache.get(key),
            is_({"key": "value"}),
        )

    def test_invalidates(self):
        # Validate that we cache between requests
        first_call = self.cached_retrieve_for(key_id=1)
        second_call = self.cached_retrieve_for(key_id=1)
        assert_that(first_call["values"], is_(second_call["values"]))

        key = cache_key(self.cache_prefix, TestForSchema, (), dict(key_id=1))
        assert_that(
            self.graph.resource_cache.get(key),
            is_({"values": 1}),
        )

        self.cached_create(key_id=1)

        # And check that
        key = cache_key(self.cache_prefix, TestForSchema, (), dict(key_id=1))
        assert_that(
            self.graph.resource_cache.get(key),
            is_(None),
        )

        # Then validate that it was invalidated correctly
        assert_that(self.cached_retrieve_for(key_id=1)["values"], is_(first_call["values"] + 1))
