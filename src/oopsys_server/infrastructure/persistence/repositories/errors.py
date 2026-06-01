import uuid
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from oopsys_server.domain.enums import ErrorGroupStatus, Severity
from oopsys_server.infrastructure.persistence.base import utc_now
from oopsys_server.infrastructure.persistence.models import AgentFaultRecord, ErrorGroup, ErrorReport, SelfError


class ErrorRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_or_create_group(
        self,
        *,
        agent_id: str,
        fingerprint: str,
        service: str,
        environment: str,
        exception_type: str,
        title: str,
        severity: Severity,
    ) -> tuple[ErrorGroup, bool]:
        result = await self._session.execute(
            select(ErrorGroup).where(ErrorGroup.agent_id == agent_id, ErrorGroup.fingerprint == fingerprint)
        )
        group = result.scalar_one_or_none()
        if group is not None:
            return (group, False)
        group = ErrorGroup(
            agent_id=agent_id,
            fingerprint=fingerprint,
            service=service,
            environment=environment,
            exception_type=exception_type,
            title=title,
            severity=severity,
            count=0,
        )
        self._session.add(group)
        await self._session.flush()
        return (group, True)

    async def add_report(self, report: ErrorReport) -> ErrorReport:
        self._session.add(report)
        await self._session.flush()
        return report

    async def get_group(self, group_id: uuid.UUID) -> ErrorGroup | None:
        return await self._session.get(ErrorGroup, group_id)

    async def list_groups(self, *, agent_ids: list[str], limit: int = 200) -> list[ErrorGroup]:
        if not agent_ids:
            return []
        result = await self._session.execute(
            select(ErrorGroup)
            .where(ErrorGroup.agent_id.in_(agent_ids))
            .order_by(ErrorGroup.last_seen.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def recent_reports(self, group_id: uuid.UUID, limit: int = 20) -> list[ErrorReport]:
        result = await self._session.execute(
            select(ErrorReport)
            .where(ErrorReport.group_id == group_id)
            .order_by(ErrorReport.occurred_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def set_status(self, group_id: uuid.UUID, status: ErrorGroupStatus) -> None:
        group = await self._session.get(ErrorGroup, group_id)
        if group is not None:
            group.status = status

    async def mark_notified(self, group: ErrorGroup, when: datetime | None = None) -> None:
        group.last_notified_at = when or utc_now()


class AgentFaultRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, fault: AgentFaultRecord) -> AgentFaultRecord:
        self._session.add(fault)
        await self._session.flush()
        return fault

    async def list_for_agents(self, agent_ids: list[str], limit: int = 100) -> list[AgentFaultRecord]:
        if not agent_ids:
            return []
        result = await self._session.execute(
            select(AgentFaultRecord)
            .where(AgentFaultRecord.agent_id.in_(agent_ids))
            .order_by(AgentFaultRecord.occurred_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())


class SelfErrorRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def record(
        self,
        *,
        component: str,
        exception_type: str,
        message: str,
        traceback: str,
        fingerprint: str,
        context: dict | None = None,
    ) -> tuple[SelfError, bool]:
        result = await self._session.execute(select(SelfError).where(SelfError.fingerprint == fingerprint))
        existing = result.scalar_one_or_none()
        if existing is not None:
            existing.count += 1
            existing.occurred_at = utc_now()
            return (existing, False)
        record = SelfError(
            component=component,
            exception_type=exception_type,
            message=message,
            traceback=traceback,
            fingerprint=fingerprint,
            context=context or {},
        )
        self._session.add(record)
        await self._session.flush()
        return (record, True)

    async def list_recent(self, limit: int = 100) -> list[SelfError]:
        result = await self._session.execute(select(SelfError).order_by(SelfError.occurred_at.desc()).limit(limit))
        return list(result.scalars().all())

    async def count(self) -> int:
        result = await self._session.execute(select(func.count(SelfError.id)))
        return int(result.scalar_one())
