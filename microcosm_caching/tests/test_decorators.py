"""
Unit tests for decorators

"""
from hamcrest import assert_that, is_
from marshmallow import Schema, fields
from microcosm.api import binding, create_object_graph, load_from_dict
from microcosm_logging.decorators import logger

from microcosm_caching.decorators import cached


class TestSchema(Schema):
    key = fields.String(required=True)


@binding("controller")
@logger
class TestController:
    def __init__(self, graph):
        self.graph = graph

    def retrieve(self, **kwargs):
        return {"key": "value"}

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
        controller = self.graph.controller
        self.cached_retrieve = cached(controller, TestSchema, "test")(controller.retrieve)

    def test_decorator(self):
        self.cached_retrieve(key_id=1)
        assert_that(
            self.graph.resource_cache.get("test:1"),
            is_({"key": "value"}),
        )
