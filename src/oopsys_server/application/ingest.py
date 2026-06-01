import uuid

from structlog import getLogger

from oopsys_server.application.agent_display import resolve_agent_display_name
from oopsys_server.application.dedup import ThrottleInput, should_notify
from oopsys_server.application.notifications import NotificationService
from oopsys_server.application.projects import ProjectService
from oopsys_server.configuration import Configuration, Loggers
from oopsys_server.domain.enums import AgentStatus, NotificationKind, Severity, Source
from oopsys_server.domain.envelope import (
    AgentFaultPayload,
    ContainerSnapshotPayload,
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


def _container_name_from_context(context: dict) -> str | None:
    for key in ("container_name", "container", "docker_container"):
        value = context.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


class IngestService:
    def __init__(
        self,
        *,
        configuration: Configuration,
        agents: AgentRepository,
        tokens: AgentTokenRepository,
        errors: ErrorRepository,
        metrics: MetricsRepository,
        containers: ContainerRepository,
        faults: AgentFaultRepository,
        projects: ProjectService,
        notifications: NotificationService,
        hub: RealtimeHub,
    ) -> None:
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

    async def _bound_accounts_for_agent(self, agent_id: str) -> list[tuple[uuid.UUID, str | None]]:
        rows = await self._tokens.accounts_with_labels_for_agent(agent_id)
        return [(account.id, label) for account, label in rows]

    async def _touch_agent(
        self,
        envelope: Envelope,
        account_rows: list[tuple[uuid.UUID, str | None]],
    ) -> None:
        current = await self._agents.get(envelope.agent_id)
        was_down = current is not None and current.status is AgentStatus.DOWN
        await self._agents.touch(envelope.agent_id, seen_at=utc_now())
        if was_down:
            for account_id, token_label in account_rows:
                display = resolve_agent_display_name(
                    token_label=token_label,
                    agent_name=current.name if current else None,
                    agent_id=envelope.agent_id,
                )
                await self._notifications.emit(
                    [account_id],
                    kind=NotificationKind.AGENT_RECOVERED,
                    severity=Severity.ERROR,
                    title=f"Агент снова на связи: {display}",
                    ref={"agent_id": envelope.agent_id},
                )
            await self._hub.publish_many(
                [account_id for account_id, _ in account_rows],
                "agent_status",
                {"agent_id": envelope.agent_id, "status": "online"},
            )

    async def handle(self, envelope: Envelope) -> None:
        account_rows = await self._bound_accounts_for_agent(envelope.agent_id)
        account_ids = [account_id for account_id, _ in account_rows]
        await self._touch_agent(envelope, account_rows)
        if envelope.source is Source.PROJECTS:
            await self._handle_error(envelope, account_rows)
        elif envelope.source is Source.SERVER:
            await self._handle_server(envelope, account_ids)
        elif envelope.source is Source.DOCKER:
            await self._handle_docker(envelope, account_ids)
        elif envelope.source is Source.AGENT:
            await self._handle_fault(envelope, account_ids)

    async def _handle_error(
        self,
        envelope: Envelope,
        account_rows: list[tuple[uuid.UUID, str | None]],
    ) -> None:
        payload = ErrorReportPayload.model_validate(envelope.payload)
        fingerprint = compute_fingerprint(
            service=payload.service,
            exception_type=payload.exception_type,
            message=payload.message,
            traceback=payload.traceback,
        )
        title = f"{payload.exception_type}: {payload.message}".strip()[:240]
        group, is_new = await self._errors.get_or_create_group(
            agent_id=envelope.agent_id,
            fingerprint=fingerprint,
            service=payload.service,
            environment=payload.environment,
            exception_type=payload.exception_type,
            title=title,
            severity=payload.severity,
        )
        prev_last_seen = group.last_seen if not is_new else None
        last_notified = group.last_notified_at
        group.count += 1
        group.last_seen = payload.timestamp
        group.title = title
        if payload.severity is Severity.CRITICAL:
            group.severity = Severity.CRITICAL
        await self._errors.add_report(
            ErrorReport(
                group_id=group.id,
                agent_id=envelope.agent_id,
                service=payload.service,
                environment=payload.environment,
                severity=payload.severity,
                exception_type=payload.exception_type,
                message=payload.message,
                traceback=payload.traceback,
                context=payload.context,
                occurred_at=payload.timestamp,
            )
        )
        notify = should_notify(
            ThrottleInput(
                is_new=is_new,
                status=group.status,
                severity=group.severity,
                previous_last_seen=prev_last_seen,
                last_notified_at=last_notified,
            ),
            now=utc_now(),
            quiet_gap_seconds=self._cfg.notifications.quiet_gap_seconds,
            renotify_window_seconds=self._cfg.notifications.renotify_window_seconds,
        )
        if notify:
            agent = await self._agents.get(envelope.agent_id)
            agent_name = agent.name if agent else None
            container_name = _container_name_from_context(payload.context)
            occurred_at = payload.timestamp.isoformat()
            for account_id, token_label in account_rows:
                project_ids = await self._projects.matching_project_ids(account_id, payload.service)
                project_bot_enabled = await self._projects.project_bot_enabled(account_id, project_ids)
                ref = {
                    "group_id": str(group.id),
                    "agent_id": envelope.agent_id,
                    "service": payload.service,
                    "project_ids": [str(project_id) for project_id in project_ids],
                }
                bot_fields: dict[str, object] = {
                    "project_ids": ref["project_ids"],
                    "project_bot_enabled": project_bot_enabled,
                    "agent_display": resolve_agent_display_name(
                        token_label=token_label,
                        agent_name=agent_name,
                        agent_id=envelope.agent_id,
                    ),
                    "occurred_at": occurred_at,
                }
                if container_name:
                    bot_fields["container_name"] = container_name
                await self._notifications.emit(
                    [account_id],
                    kind=NotificationKind.ERROR,
                    severity=group.severity,
                    title=title,
                    body=f"{payload.service} · {payload.environment}",
                    ref=ref,
                    bot_fields=bot_fields,
                )
            await self._errors.mark_notified(group)
        account_ids = [account_id for account_id, _ in account_rows]
        await self._hub.publish_many(
            "error",
            {
                "group_id": str(group.id),
                "service": payload.service,
                "exception_type": payload.exception_type,
                "severity": group.severity.value,
                "count": group.count,
                "last_seen": group.last_seen.isoformat(),
            },
        )

    async def _handle_server(self, envelope: Envelope, account_ids: list[uuid.UUID]) -> None:
        payload = ServerMetricsPayload.model_validate(envelope.payload)
        await self._metrics.add(envelope.agent_id, payload)
        await self._hub.publish_many(
            account_ids,
            "metric",
            {
                "agent_id": envelope.agent_id,
                "cpu_percent": payload.cpu_percent,
                "mem_percent": payload.mem_percent,
                "disk_percent": payload.disk_percent,
                "load_1": payload.load_1,
                "captured_at": payload.captured_at.isoformat(),
            },
        )

    async def _handle_docker(self, envelope: Envelope, account_ids: list[uuid.UUID]) -> None:
        raw = envelope.payload
        if "containers" in raw:
            snapshot = ContainerSnapshotPayload.model_validate(raw)
            records = await self._containers.replace_snapshot(envelope.agent_id, snapshot.containers)
            for account_id in account_ids:
                for record in records:
                    if await self._projects.auto_assign(account_id, record):
                        break
            if records:
                for record in records:
                    await self._hub.publish_many(
                        account_ids,
                        "container",
                        {
                            "agent_id": envelope.agent_id,
                            "container_id": record.container_id,
                            "name": record.name,
                            "status": record.status,
                            "cpu_percent": record.cpu_percent,
                            "mem_percent": record.mem_percent,
                        },
                    )
            else:
                await self._hub.publish_many(
                    account_ids,
                    "container",
                    {"agent_id": envelope.agent_id, "sync": True},
                )
            return

        payload = ContainerStatePayload.model_validate(raw)
        record = await self._containers.upsert(envelope.agent_id, payload)
        for account_id in account_ids:
            if await self._projects.auto_assign(account_id, record):
                break
        await self._hub.publish_many(
            account_ids,
            "container",
            {
                "agent_id": envelope.agent_id,
                "container_id": payload.container_id,
                "name": payload.name,
                "status": payload.status,
                "cpu_percent": payload.cpu_percent,
                "mem_percent": payload.mem_percent,
            },
        )

    async def _handle_fault(self, envelope: Envelope, account_ids: list[uuid.UUID]) -> None:
        payload = AgentFaultPayload.model_validate(envelope.payload)
        await self._faults.add(
            AgentFaultRecord(
                agent_id=envelope.agent_id,
                component=payload.component,
                operation=payload.operation,
                exception_type=payload.exception_type,
                message=payload.message,
                traceback=payload.traceback,
                severity=payload.severity,
                occurred_at=payload.occurred_at,
            )
        )
        await self._notifications.emit(
            account_ids,
            kind=NotificationKind.AGENT_FAULT,
            severity=payload.severity,
            title=f"Сбой агента: {payload.component}/{payload.operation}",
            body=f"{payload.exception_type}: {payload.message}"[:240],
            ref={"agent_id": envelope.agent_id},
        )
