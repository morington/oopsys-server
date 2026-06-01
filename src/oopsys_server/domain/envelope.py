from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from oopsys_server.domain.enums import Severity, Source


class ErrorReportPayload(BaseModel):
    severity: Severity
    service: str
    environment: str
    exception_type: str
    message: str
    traceback: str
    timestamp: datetime
    context: dict[str, Any] = Field(default_factory=dict)


class ServerMetricsPayload(BaseModel):
    cpu_percent: float
    mem_percent: float
    mem_used: int
    mem_total: int
    net_bytes_sent: int
    net_bytes_recv: int
    load_1: float
    load_5: float
    load_15: float
    disk_percent: float | None = None
    captured_at: datetime


class ContainerStatePayload(BaseModel):
    container_id: str
    name: str
    image: str
    status: str
    started_at: datetime | None = None
    restarts: int = 0
    cpu_percent: float | None = None
    mem_percent: float | None = None
    mem_usage: int | None = None
    net_rx: int | None = None
    net_tx: int | None = None
    blk_read: int | None = None
    blk_write: int | None = None
    labels: dict[str, str] = Field(default_factory=dict)
    ports: list[str] = Field(default_factory=list)
    health: str | None = None
    captured_at: datetime


class ContainerSnapshotPayload(BaseModel):
    """Full docker state for an agent; replaces stale container rows on the server."""

    captured_at: datetime
    containers: list[ContainerStatePayload] = Field(default_factory=list)


class AgentFaultPayload(BaseModel):
    component: str
    operation: str
    exception_type: str
    message: str
    traceback: str
    severity: Severity = Severity.ERROR
    occurred_at: datetime


class Envelope(BaseModel):
    schema_version: int = 1
    agent_id: str
    source: Source
    occurred_at: datetime
    payload: dict[str, Any]
