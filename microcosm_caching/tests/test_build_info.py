"""
Unit tests for build_info

"""
from hamcrest import assert_that, is_
from microcosm.api import create_object_graph, load_from_dict


class TestBuildInfo:

    def test_cached(self):
        graph = create_object_graph(
            "test",
            testing=True,
            loader=load_from_dict(dict(
                build_info=dict(sha1="asdf1234", build_num="5"),
            )),
        )
        graph.use(
            "build_info",
        )

        assert_that(graph.build_info.sha1, is_("asdf1234"))
