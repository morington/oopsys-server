from dishka import AsyncContainer, make_async_container
from dishka.provider import BaseProvider

from oopsys_server.dependency_injection.configuration import ConfigurationProvider
from oopsys_server.dependency_injection.connections import ConnectionProvider
from oopsys_server.dependency_injection.infrastructure import InfrastructureProvider
from oopsys_server.dependency_injection.repositories import RepositoryProvider
from oopsys_server.dependency_injection.security import SecurityProvider
from oopsys_server.dependency_injection.services import ServiceProvider


def build_container(*providers: BaseProvider) -> AsyncContainer:
    return make_async_container(ConfigurationProvider(), ConnectionProvider(), SecurityProvider(), InfrastructureProvider(), RepositoryProvider(), ServiceProvider(), *providers)
