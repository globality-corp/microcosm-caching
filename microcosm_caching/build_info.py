"""
Store build information.

"""
from dataclasses import dataclass
from typing import Optional

from microcosm.api import defaults, typed


@dataclass
class BuildInfo:
    build_num: Optional[str]
    sha1: Optional[str]


@defaults(
    build_num=typed(str, default_value=None),
    sha1=typed(str, default_value=None),
)
def configure_build_info(graph):
    """
    Configure build info

    """
    return BuildInfo(
        build_num=graph.config.build_info.build_num,
        sha1=graph.config.build_info.sha1,
    )
