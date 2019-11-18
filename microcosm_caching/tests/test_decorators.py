"""
Unit tests for decorators

"""
from hamcrest import assert_that, is_
from marshmallow import Schema, fields
from microcosm.api import binding, create_object_graph, load_from_dict
from microcosm_logging.decorators import logger

from microcosm_caching.decorators import (
    Invalidation,
    cache_key,
    cached,
    invalidates,
)


class TestSchema(Schema):
    key = fields.String(required=True)


class TestExtendedSchema(Schema):
    extended_key = fields.String(required=True)


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

    def extended_retrieve(self, **kwargs):
        return {"extended_key": "value"}

    def create(self, **kwargs):
        return

    def retrieve_for(self, **kwargs):
        self.calls += 1
        return {"values": self.calls}


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

        self.cached_retrieve = cached(controller, TestSchema)(controller.retrieve)
        self.cached_extended_retrieve = cached(controller, TestExtendedSchema)(controller.extended_retrieve)
        self.cached_retrieve_for = cached(controller, TestForSchema)(controller.retrieve_for)

        self.cached_create = invalidates(
            controller,
            invalidations=[
                Invalidation(
                    schema=TestForSchema,
                    arguments=[
                        "key_id",
                    ],
                ),
                Invalidation(
                    schema=TestSchema,
                    arguments=[
                        "key_id",
                    ],
                ),
                Invalidation(
                    schema=TestExtendedSchema,
                    arguments=[
                        "extended_key_id",
                    ],
                    kwarg_mappings=dict(
                        extended_key_id="key_id",
                    ),
                ),
            ],
        )(controller.create)

        self.cached_retrieve_for = cached(controller, TestForSchema)(controller.retrieve_for)

    def test_cached(self):
        self.cached_retrieve(key_id=1)
        key = cache_key(self.cache_prefix, TestSchema, (), dict(key_id=1))
        assert_that(
            self.graph.resource_cache.get(key),
            is_({"key": "value"}),
        )

    def test_invalidates(self):
        # Validate that we cache between requests
        first_call = self.cached_retrieve_for(key_id=1, other_key_id=2)
        second_call = self.cached_retrieve_for(key_id=1, other_key_id=2)
        assert_that(first_call["values"], is_(second_call["values"]))

        key = cache_key(self.cache_prefix, TestForSchema, (), dict(key_id=1, other_key_id=2))
        assert_that(
            self.graph.resource_cache.get(key),
            is_({"values": 1}),
        )

        # Then populate the basic retrieve key
        self.cached_retrieve(key_id=1)

        # And the extended key
        self.cached_extended_retrieve(extended_key_id=1)

        self.cached_create(key_id=1)

        # And check that all keys are marked for deletion
        for schema, kwargs in (
            (TestSchema, dict(key_id=1)),
            (TestForSchema, dict(key_id=1)),
            (TestExtendedSchema, dict(extended_key_id=1)),
        ):
            key = cache_key(self.cache_prefix, schema, (), kwargs)
            assert_that(
                self.graph.resource_cache.get(key),
                is_(None),
            )

        # Then validate that it was invalidated correctly
        assert_that(self.cached_retrieve_for(key_id=1)["values"], is_(first_call["values"] + 1))
