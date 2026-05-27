from dishka import Provider, Scope, provide

from oopsys_server.configuration import Configuration


class ConfigurationProvider(Provider):
    scope = Scope.APP

    @provide
    def get_configuration(self) -> Configuration:
        return Configuration()
