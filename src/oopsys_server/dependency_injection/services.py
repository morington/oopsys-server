from dishka import Provider, Scope, provide

from oopsys_server.application.accounts import AccountService
from oopsys_server.application.auth import AuthService
from oopsys_server.application.bots import BotService
from oopsys_server.application.ingest import IngestService
from oopsys_server.application.notifications import NotificationService
from oopsys_server.application.projects import ProjectService
from oopsys_server.application.tokens import AgentTokenService
from oopsys_server.configuration import Configuration
from oopsys_server.infrastructure.nats import NotificationGateway
from oopsys_server.infrastructure.persistence.repositories import (
    AccountRepository,
    AgentFaultRepository,
    AgentRepository,
    AgentTokenRepository,
    BotRepository,
    ContainerRepository,
    ErrorRepository,
    MetricsRepository,
    NotificationRepository,
    ProjectRepository,
    SessionRepository,
)
from oopsys_server.infrastructure.realtime import RealtimeHub
from oopsys_server.infrastructure.security import PasswordHasher, TokenCipher


class ServiceProvider(Provider):
    scope = Scope.REQUEST

    @provide
    def auth_service(self, accounts: AccountRepository, sessions: SessionRepository, hasher: PasswordHasher, configuration: Configuration) -> AuthService:
        return AuthService(accounts, sessions, hasher, configuration.security)

    @provide
    def account_service(self, accounts: AccountRepository, sessions: SessionRepository, hasher: PasswordHasher) -> AccountService:
        return AccountService(accounts, sessions, hasher)

    @provide
    def token_service(self, tokens: AgentTokenRepository) -> AgentTokenService:
        return AgentTokenService(tokens)

    @provide
    def project_service(self, projects: ProjectRepository, containers: ContainerRepository) -> ProjectService:
        return ProjectService(projects, containers)

    @provide
    def notification_service(self, notifications: NotificationRepository, gateway: NotificationGateway, hub: RealtimeHub) -> NotificationService:
        return NotificationService(notifications, gateway, hub)

    @provide
    def bot_service(self, bots: BotRepository, cipher: TokenCipher) -> BotService:
        return BotService(bots, cipher)

    @provide
    def ingest_service(self, configuration: Configuration, agents: AgentRepository, tokens: AgentTokenRepository, errors: ErrorRepository, metrics: MetricsRepository, containers: ContainerRepository, faults: AgentFaultRepository, projects: ProjectService, notifications: NotificationService, hub: RealtimeHub) -> IngestService:
        return IngestService(configuration=configuration, agents=agents, tokens=tokens, errors=errors, metrics=metrics, containers=containers, faults=faults, projects=projects, notifications=notifications, hub=hub)
