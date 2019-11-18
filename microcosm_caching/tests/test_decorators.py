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
    value = fields.Integer(required=True)


class TestExtendedSchema(Schema):
    value = fields.Integer(required=True)


class TestForSchema(Schema):
    values = fields.Integer(required=True)


@binding("controller")
@logger
class TestController:
    def __init__(self, graph):
        self.graph = graph
        self._calls = 0

    @property
    def calls(self):
        self._calls += 1
        return self._calls

    def retrieve(self, **kwargs):
        return {"value": self.calls}

    def extended_retrieve(self, **kwargs):
        return {"value": self.calls}

    def create(self, **kwargs):
        return

    def retrieve_for(self, **kwargs):
        return {"values": self.calls}


class TestDecorators:

    def setup(self):
        self.build_version = "asdf1234"

        self.graph = create_object_graph(
            "test",
            testing=True,
            loader=load_from_dict(dict(
                resource_cache=dict(enabled=True),
                build_info=dict(sha1=self.build_version, build_num="5"),
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

        invalidations = [
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
        ]

        self.cached_create = invalidates(
            controller,
            invalidations=invalidations,
        )(controller.create)

        self.cached_retrieve_for = cached(controller, TestForSchema)(controller.retrieve_for)

    def test_cached(self):
        first_call = self.cached_retrieve(key_id=1)
        key = cache_key(self.cache_prefix, TestSchema, (), dict(key_id=1), version=self.build_version)

        # Check that we pushed the resource into the cache
        assert_that(
            self.graph.resource_cache.get(key),
            is_({"value": 1}),
        )

        # And that a subsequent call hits the cache
        assert_that(self.cached_retrieve(key_id=1)["value"], is_(first_call["value"]))

    def test_caching_multi_args(self):
        # Validate that we cache between requests
        first_call = self.cached_retrieve_for(key_id=1, other_key_id=2)
        second_call = self.cached_retrieve_for(key_id=1, other_key_id=2)
        assert_that(first_call["values"], is_(second_call["values"]))

        key = cache_key(
            self.cache_prefix,
            TestForSchema,
            (),
            dict(key_id=1, other_key_id=2),
            version=self.build_version,
        )
        assert_that(
            self.graph.resource_cache.get(key),
            is_({"values": 1}),
        )

    def test_invalidates(self):
        # Populate the basic retrieve key
        self.cached_retrieve(key_id=1)

        # And the extended key
        self.cached_extended_retrieve(extended_key_id=1)

        # And the retrieve_for key
        self.cached_retrieve_for(key_id=1)

        # Then trigger invalidation
        self.cached_create(key_id=1)

        # And check that all keys are marked for deletion
        for schema, kwargs in (
            (TestSchema, dict(key_id=1)),
            (TestForSchema, dict(key_id=1)),
            (TestExtendedSchema, dict(extended_key_id=1)),
        ):
            key = cache_key(self.cache_prefix, schema, (), kwargs, version=self.build_version)
            assert_that(
                self.graph.resource_cache.get(key),
                is_(None),
            )

        # Then validate that it was invalidated correctly
        assert_that(self.cached_retrieve(key_id=1)["value"], is_(4))
        assert_that(self.cached_extended_retrieve(key_id=1)["value"], is_(5))
        assert_that(self.cached_retrieve_for(key_id=1)["values"], is_(6))

    def test_cached_with_no_build_version(self):
        name = "test"
        graph = create_object_graph(
            name,
            testing=True,
            loader=load_from_dict(dict(
                resource_cache=dict(enabled=True),
            )),
        )
        graph.use("controller")
        controller = graph.controller

        cached_retrieve = cached(controller, TestSchema)(controller.retrieve)

        first_call = cached_retrieve(key_id=1)
        key = cache_key(name, TestSchema, (), dict(key_id=1), version=None)

        # Check that we pushed the resource into the cache
        assert_that(
            graph.resource_cache.get(key),
            is_({"value": 1}),
        )

        # And that a subsequent call hits the cache
        assert_that(cached_retrieve(key_id=1)["value"], is_(first_call["value"]))
