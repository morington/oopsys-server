import uuid

from structlog import getLogger

from oopsys_server.application.dedup import ThrottleInput, should_notify
from oopsys_server.application.notifications import NotificationService
from oopsys_server.application.projects import ProjectService
from oopsys_server.configuration import Configuration, Loggers
from oopsys_server.domain.enums import AgentStatus, NotificationKind, Severity, Source
from oopsys_server.domain.envelope import (
    AgentFaultPayload,
    ContainerStatePayload,
    Envelope,
    ErrorReportPayload,
    ServerMetricsPayload,
)
from oopsys_server.domain.fingerprint import compute_fingerprint
from oopsys_server.infrastructure.persistence.base import utc_now
from oopsys_server.infrastructure.persistence.models import AgentFaultRecord, ErrorReport
from oopsys_server.infrastructure.persistence.repositories import (
    AgentFaultRepository,
    AgentRepository,
    AgentTokenRepository,
    ContainerRepository,
    ErrorRepository,
    MetricsRepository,
)
from oopsys_server.infrastructure.realtime import RealtimeHub

logger = getLogger(Loggers.ingest.name)

class IngestService:

    def __init__(self, *, configuration: Configuration, agents: AgentRepository, tokens: AgentTokenRepository, errors: ErrorRepository, metrics: MetricsRepository, containers: ContainerRepository, faults: AgentFaultRepository, projects: ProjectService, notifications: NotificationService, hub: RealtimeHub) -> None:
        self._cfg = configuration
        self._agents = agents
        self._tokens = tokens
        self._errors = errors
        self._metrics = metrics
        self._containers = containers
        self._faults = faults
        self._projects = projects
        self._notifications = notifications
        self._hub = hub

    async def _bound_account_ids(self, agent_id: str) -> list[uuid.UUID]:
        accounts = await self._tokens.accounts_for_agent(agent_id)
        return [account.id for account in accounts]

    async def _touch_agent(self, envelope: Envelope, account_ids: list[uuid.UUID]) -> None:
        current = await self._agents.get(envelope.agent_id)
        was_down = current is not None and current.status is AgentStatus.DOWN
        await self._agents.touch(envelope.agent_id, seen_at=utc_now())
        if was_down:
            await self._notifications.emit(account_ids, kind=NotificationKind.AGENT_RECOVERED, severity=Severity.ERROR, title=f"Агент снова на связи: {envelope.agent_id[:8]}", ref={"agent_id": envelope.agent_id})
            await self._hub.publish_many(account_ids, "agent_status", {"agent_id": envelope.agent_id, "status": "online"})

    async def handle(self, envelope: Envelope) -> None:
        account_ids = await self._bound_account_ids(envelope.agent_id)
        await self._touch_agent(envelope, account_ids)
        if envelope.source is Source.PROJECTS:
            await self._handle_error(envelope, account_ids)
        elif envelope.source is Source.SERVER:
            await self._handle_server(envelope, account_ids)
        elif envelope.source is Source.DOCKER:
            await self._handle_docker(envelope, account_ids)
        elif envelope.source is Source.AGENT:
            await self._handle_fault(envelope, account_ids)

    async def _handle_error(self, envelope: Envelope, account_ids: list[uuid.UUID]) -> None:
        payload = ErrorReportPayload.model_validate(envelope.payload)
        fingerprint = compute_fingerprint(service=payload.service, exception_type=payload.exception_type, message=payload.message, traceback=payload.traceback)
        title = f"{payload.exception_type}: {payload.message}".strip()[:240]
        group, is_new = await self._errors.get_or_create_group(agent_id=envelope.agent_id, fingerprint=fingerprint, service=payload.service, environment=payload.environment, exception_type=payload.exception_type, title=title, severity=payload.severity)
        prev_last_seen = group.last_seen if not is_new else None
        last_notified = group.last_notified_at
        group.count += 1
        group.last_seen = payload.timestamp
        group.title = title
        if payload.severity is Severity.CRITICAL:
            group.severity = Severity.CRITICAL
        await self._errors.add_report(ErrorReport(group_id=group.id, agent_id=envelope.agent_id, service=payload.service, environment=payload.environment, severity=payload.severity, exception_type=payload.exception_type, message=payload.message, traceback=payload.traceback, context=payload.context, occurred_at=payload.timestamp))
        notify = should_notify(ThrottleInput(is_new=is_new, status=group.status, severity=group.severity, previous_last_seen=prev_last_seen, last_notified_at=last_notified), now=utc_now(), quiet_gap_seconds=self._cfg.notifications.quiet_gap_seconds, renotify_window_seconds=self._cfg.notifications.renotify_window_seconds)
        if notify:
            await self._notifications.emit(account_ids, kind=NotificationKind.ERROR, severity=group.severity, title=title, body=f"{payload.service} · {payload.environment}", ref={"group_id": str(group.id), "agent_id": envelope.agent_id, "service": payload.service})
            await self._errors.mark_notified(group)
        await self._hub.publish_many(account_ids, "error", {"group_id": str(group.id), "service": payload.service, "exception_type": payload.exception_type, "severity": group.severity.value, "count": group.count, "last_seen": group.last_seen.isoformat()})

    async def _handle_server(self, envelope: Envelope, account_ids: list[uuid.UUID]) -> None:
        payload = ServerMetricsPayload.model_validate(envelope.payload)
        await self._metrics.add(envelope.agent_id, payload)
        await self._hub.publish_many(account_ids, "metric", {"agent_id": envelope.agent_id, "cpu_percent": payload.cpu_percent, "mem_percent": payload.mem_percent, "disk_percent": payload.disk_percent, "load_1": payload.load_1, "captured_at": payload.captured_at.isoformat()})

    async def _handle_docker(self, envelope: Envelope, account_ids: list[uuid.UUID]) -> None:
        payload = ContainerStatePayload.model_validate(envelope.payload)
        record = await self._containers.upsert(envelope.agent_id, payload)
        for account_id in account_ids:
            if await self._projects.auto_assign(account_id, record):
                break
        await self._hub.publish_many(account_ids, "container", {"agent_id": envelope.agent_id, "container_id": payload.container_id, "name": payload.name, "status": payload.status, "cpu_percent": payload.cpu_percent, "mem_percent": payload.mem_percent})

    async def _handle_fault(self, envelope: Envelope, account_ids: list[uuid.UUID]) -> None:
        payload = AgentFaultPayload.model_validate(envelope.payload)
        await self._faults.add(AgentFaultRecord(agent_id=envelope.agent_id, component=payload.component, operation=payload.operation, exception_type=payload.exception_type, message=payload.message, traceback=payload.traceback, severity=payload.severity, occurred_at=payload.occurred_at))
        await self._notifications.emit(account_ids, kind=NotificationKind.AGENT_FAULT, severity=payload.severity, title=f"Сбой агента: {payload.component}/{payload.operation}", body=f"{payload.exception_type}: {payload.message}"[:240], ref={"agent_id": envelope.agent_id})
