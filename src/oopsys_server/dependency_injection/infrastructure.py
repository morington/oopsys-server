from dishka import Provider, Scope, provide
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from oopsys_server.application.liveness import LivenessMonitor
from oopsys_server.application.self_errors import SelfErrorReporter
from oopsys_server.configuration import Configuration
from oopsys_server.infrastructure.agent_client import AgentHealthClient
from oopsys_server.infrastructure.nats import NotificationGateway
from oopsys_server.infrastructure.realtime import RealtimeHub


class InfrastructureProvider(Provider):
    scope = Scope.APP

    @provide
    def realtime_hub(self) -> RealtimeHub:
        return RealtimeHub()

    @provide
    def notification_gateway(self, configuration: Configuration) -> NotificationGateway:
        return NotificationGateway(configuration.nats)

    @provide
    def agent_health_client(self, configuration: Configuration) -> AgentHealthClient:
        return AgentHealthClient(timeout=configuration.liveness.poll_timeout)

    @provide
    def self_error_reporter(self, session_factory: async_sessionmaker[AsyncSession]) -> SelfErrorReporter:
        return SelfErrorReporter(session_factory)

    @provide
    def liveness_monitor(self, configuration: Configuration, session_factory: async_sessionmaker[AsyncSession], gateway: NotificationGateway, hub: RealtimeHub) -> LivenessMonitor:
        return LivenessMonitor(configuration=configuration, session_factory=session_factory, gateway=gateway, hub=hub)
