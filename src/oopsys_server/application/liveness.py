import asyncio
import contextlib

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from structlog import getLogger

from oopsys_server.application.agent_display import resolve_agent_display_name
from oopsys_server.application.notifications import NotificationService
from oopsys_server.configuration import Configuration, Loggers
from oopsys_server.domain.enums import AgentStatus, NotificationKind, Severity
from oopsys_server.infrastructure.nats import NotificationGateway
from oopsys_server.infrastructure.persistence.repositories import (
    AgentRepository,
    AgentTokenRepository,
    NotificationRepository,
)
from oopsys_server.infrastructure.realtime import RealtimeHub

logger = getLogger(Loggers.liveness.name)


class LivenessMonitor:
    def __init__(
        self,
        *,
        configuration: Configuration,
        session_factory: async_sessionmaker[AsyncSession],
        gateway: NotificationGateway,
        hub: RealtimeHub,
    ) -> None:
        self._cfg = configuration
        self._session_factory = session_factory
        self._gateway = gateway
        self._hub = hub
        self._task: asyncio.Task | None = None

    async def start(self) -> None:
        self._task = asyncio.create_task(self._loop(), name="oopsys-liveness")
        await logger.ainfo("liveness monitor started", stale_seconds=self._cfg.liveness.stale_seconds)

    async def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await self._task
        await logger.ainfo("liveness monitor stopped")

    async def _loop(self) -> None:
        while True:
            with contextlib.suppress(Exception):
                await self._scan_once()
            await asyncio.sleep(self._cfg.liveness.scan_interval_seconds)

    async def _scan_once(self) -> None:
        async with self._session_factory() as session:
            agents = AgentRepository(session)
            tokens = AgentTokenRepository(session)
            notifications = NotificationService(NotificationRepository(session), self._gateway, self._hub)
            stale = await agents.list_stale(self._cfg.liveness.stale_seconds)
            for agent in stale:
                await agents.set_status(agent.agent_id, AgentStatus.DOWN)
                account_rows = await tokens.accounts_with_labels_for_agent(agent.agent_id)
                for account, token_label in account_rows:
                    display = resolve_agent_display_name(
                        token_label=token_label,
                        agent_name=agent.name,
                        agent_id=agent.agent_id,
                    )
                    await notifications.emit(
                        [account.id],
                        kind=NotificationKind.AGENT_DOWN,
                        severity=Severity.CRITICAL,
                        title=f"Агент недоступен: {display}",
                        body=f"Нет данных более {self._cfg.liveness.stale_seconds} с",
                        ref={"agent_id": agent.agent_id},
                    )
                    await self._hub.publish_many(
                        [account.id],
                        "agent_status",
                        {"agent_id": agent.agent_id, "status": "down"},
                    )
                await logger.awarning("agent marked down", agent_id=agent.agent_id)
            await session.commit()
