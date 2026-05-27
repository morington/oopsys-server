from dishka import AsyncContainer, make_async_container
from dishka.provider import BaseProvider

from oopsys_server.dependency_injection.configuration import ConfigurationProvider
from oopsys_server.dependency_injection.connections import ConnectionProvider


def build_container(*providers: BaseProvider) -> AsyncContainer:
    return make_async_container(
        ConfigurationProvider(),
        ConnectionProvider(),
        *providers,
    )
