from dishka import Provider, Scope, provide
from sqlalchemy.ext.asyncio import AsyncSession

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
    SelfErrorRepository,
    SessionRepository,
)


class RepositoryProvider(Provider):
    scope = Scope.REQUEST

    @provide
    def accounts(self, session: AsyncSession) -> AccountRepository:
        return AccountRepository(session)

    @provide
    def sessions(self, session: AsyncSession) -> SessionRepository:
        return SessionRepository(session)

    @provide
    def agent_tokens(self, session: AsyncSession) -> AgentTokenRepository:
        return AgentTokenRepository(session)

    @provide
    def agents(self, session: AsyncSession) -> AgentRepository:
        return AgentRepository(session)

    @provide
    def errors(self, session: AsyncSession) -> ErrorRepository:
        return ErrorRepository(session)

    @provide
    def agent_faults(self, session: AsyncSession) -> AgentFaultRepository:
        return AgentFaultRepository(session)

    @provide
    def self_errors(self, session: AsyncSession) -> SelfErrorRepository:
        return SelfErrorRepository(session)

    @provide
    def metrics(self, session: AsyncSession) -> MetricsRepository:
        return MetricsRepository(session)

    @provide
    def containers(self, session: AsyncSession) -> ContainerRepository:
        return ContainerRepository(session)

    @provide
    def projects(self, session: AsyncSession) -> ProjectRepository:
        return ProjectRepository(session)

    @provide
    def bots(self, session: AsyncSession) -> BotRepository:
        return BotRepository(session)

    @provide
    def notifications(self, session: AsyncSession) -> NotificationRepository:
        return NotificationRepository(session)
