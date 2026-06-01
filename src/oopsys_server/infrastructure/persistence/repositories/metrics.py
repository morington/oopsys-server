import uuid
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from oopsys_server.domain.envelope import ContainerStatePayload, ServerMetricsPayload
from oopsys_server.infrastructure.persistence.base import utc_now
from oopsys_server.infrastructure.persistence.models import ContainerStateRecord, ServerMetricRecord


class MetricsRepository:

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, agent_id: str, payload: ServerMetricsPayload) -> ServerMetricRecord:
        record = ServerMetricRecord(agent_id=agent_id, cpu_percent=payload.cpu_percent, mem_percent=payload.mem_percent, mem_used=payload.mem_used, mem_total=payload.mem_total, net_bytes_sent=payload.net_bytes_sent, net_bytes_recv=payload.net_bytes_recv, load_1=payload.load_1, load_5=payload.load_5, load_15=payload.load_15, disk_percent=payload.disk_percent, captured_at=payload.captured_at)
        self._session.add(record)
        await self._session.flush()
        return record

    async def latest(self, agent_id: str) -> ServerMetricRecord | None:
        result = await self._session.execute(select(ServerMetricRecord).where(ServerMetricRecord.agent_id == agent_id).order_by(ServerMetricRecord.captured_at.desc()).limit(1))
        return result.scalar_one_or_none()

    async def history(self, agent_id: str, *, since_minutes: int=60) -> list[ServerMetricRecord]:
        cutoff = utc_now() - timedelta(minutes=since_minutes)
        result = await self._session.execute(select(ServerMetricRecord).where(ServerMetricRecord.agent_id == agent_id, ServerMetricRecord.captured_at >= cutoff).order_by(ServerMetricRecord.captured_at))
        return list(result.scalars().all())

    async def prune(self, older_than_days: int) -> None:
        from sqlalchemy import delete
        cutoff = utc_now() - timedelta(days=older_than_days)
        await self._session.execute(delete(ServerMetricRecord).where(ServerMetricRecord.captured_at < cutoff))

class ContainerRepository:

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def upsert(self, agent_id: str, payload: ContainerStatePayload) -> ContainerStateRecord:
        result = await self._session.execute(select(ContainerStateRecord).where(ContainerStateRecord.agent_id == agent_id, ContainerStateRecord.container_id == payload.container_id))
        record = result.scalar_one_or_none()
        if record is None:
            record = ContainerStateRecord(agent_id=agent_id, container_id=payload.container_id)
            self._session.add(record)
        record.name = payload.name
        record.image = payload.image
        record.status = payload.status
        record.started_at = payload.started_at
        record.restarts = payload.restarts
        record.cpu_percent = payload.cpu_percent
        record.mem_percent = payload.mem_percent
        record.mem_usage = payload.mem_usage
        record.net_rx = payload.net_rx
        record.net_tx = payload.net_tx
        record.blk_read = payload.blk_read
        record.blk_write = payload.blk_write
        record.labels = payload.labels
        record.captured_at = payload.captured_at
        record.updated_at = utc_now()
        await self._session.flush()
        return record

    async def list_for_agents(self, agent_ids: list[str]) -> list[ContainerStateRecord]:
        if not agent_ids:
            return []
        result = await self._session.execute(select(ContainerStateRecord).where(ContainerStateRecord.agent_id.in_(agent_ids)).order_by(ContainerStateRecord.name))
        return list(result.scalars().all())

    async def get(self, record_id: int) -> ContainerStateRecord | None:
        return await self._session.get(ContainerStateRecord, record_id)

    async def assign_project(self, agent_id: str, container_id: str, project_id: uuid.UUID | None) -> None:
        result = await self._session.execute(select(ContainerStateRecord).where(ContainerStateRecord.agent_id == agent_id, ContainerStateRecord.container_id == container_id))
        record = result.scalar_one_or_none()
        if record is not None:
            record.project_id = project_id
