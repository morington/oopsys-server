from dishka import Provider, Scope, provide

from oopsys_server.configuration import Configuration
from oopsys_server.infrastructure.security import PasswordHasher, TokenCipher


class SecurityProvider(Provider):
    scope = Scope.APP

    @provide
    def password_hasher(self) -> PasswordHasher:
        return PasswordHasher()

    @provide
    def token_cipher(self, configuration: Configuration) -> TokenCipher:
        return TokenCipher(configuration.security.bot_token_key)
