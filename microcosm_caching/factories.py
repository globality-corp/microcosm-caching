from microcosm.api import defaults, typed
from microcosm.config.types import boolean, comma_separated_list

from microcosm_caching.memcached import MemcachedCache


@defaults(
    enabled=typed(boolean, default_value=False),
    servers=typed(comma_separated_list, default_value="localhost:11211"),
    connect_timeout=typed(int, default_value=3),
    read_timeout=typed(int, default_value=2),
)
def configure_resource_cache(graph):
    """
    Configure the resource cache which will be exposed via the
    microcosm application graph.

    """
    if not graph.config.resource_cache.enabled:
        return None

    kwargs = dict(
        servers=parse_server_config(graph.config.resource_cache.servers),
        connect_timeout=graph.config.resource_cache.connect_timeout,
        read_timeout=graph.config.resource_cache.read_timeout,
    )

    if graph.metadata.testing:
        kwargs.update(dict(testing=True))

    return MemcachedCache(**kwargs)


def parse_server_config(servers):
    # NB: Assume input of the form: ["host:port","host:port"]
    parsed_servers = []
    for server in servers:
        host, port = server.split(":")
        parsed_servers.append((host, int(port)))

    return parsed_servers
