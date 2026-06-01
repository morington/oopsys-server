import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from oopsys_server.domain.enums import AgentStatus, BotStatus, ErrorGroupStatus, NotificationKind, Severity
from oopsys_server.infrastructure.persistence.base import Base, EnumValue, utc_now


def _uuid() -> uuid.UUID:
    return uuid.uuid4()

class Account(Base):
    __tablename__ = "accounts"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_uuid)
    login: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    must_change_password: Mapped[bool] = mapped_column(Boolean, default=True)
    totp_secret: Mapped[str | None] = mapped_column(String(64), nullable=True)
    failed_attempts: Mapped[int] = mapped_column(Integer, default=0)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

class Session(Base):
    __tablename__ = "sessions"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_uuid)
    account_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("accounts.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    remember: Mapped[bool] = mapped_column(Boolean, default=False)
    ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(256), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

class AgentToken(Base):
    __tablename__ = "agent_tokens"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_uuid)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    label: Mapped[str | None] = mapped_column(String(128), nullable=True)
    agent_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    endpoint_url: Mapped[str | None] = mapped_column(String(256), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

class AccountAgent(Base):
    __tablename__ = "account_agents"
    __table_args__ = (UniqueConstraint("account_id", "agent_token_id", name="uq_account_agent"),)
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_uuid)
    account_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("accounts.id", ondelete="CASCADE"), index=True)
    agent_token_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("agent_tokens.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

class Agent(Base):
    __tablename__ = "agents"
    agent_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    version: Mapped[str | None] = mapped_column(String(32), nullable=True)
    status: Mapped[AgentStatus] = mapped_column(EnumValue(AgentStatus, 16), default=AgentStatus.ONLINE)
    first_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    last_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

class ErrorGroup(Base):
    __tablename__ = "error_groups"
    __table_args__ = (UniqueConstraint("agent_id", "fingerprint", name="uq_group_agent_fingerprint"), Index("ix_group_agent_lastseen", "agent_id", "last_seen"))
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_uuid)
    agent_id: Mapped[str] = mapped_column(String(36), index=True)
    fingerprint: Mapped[str] = mapped_column(String(64), index=True)
    service: Mapped[str] = mapped_column(String(255), index=True)
    environment: Mapped[str] = mapped_column(String(64), default="production")
    exception_type: Mapped[str] = mapped_column(String(255))
    title: Mapped[str] = mapped_column(Text)
    severity: Mapped[Severity] = mapped_column(EnumValue(Severity, 16), default=Severity.ERROR)
    status: Mapped[ErrorGroupStatus] = mapped_column(EnumValue(ErrorGroupStatus, 16), default=ErrorGroupStatus.OPEN)
    count: Mapped[int] = mapped_column(BigInteger, default=0)
    first_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    last_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    last_notified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reports: Mapped[list["ErrorReport"]] = relationship(back_populates="group", cascade="all, delete-orphan")

class ErrorReport(Base):
    __tablename__ = "error_reports"
    __table_args__ = (Index("ix_report_group_occurred", "group_id", "occurred_at"),)
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    group_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("error_groups.id", ondelete="CASCADE"), index=True)
    agent_id: Mapped[str] = mapped_column(String(36), index=True)
    service: Mapped[str] = mapped_column(String(255))
    environment: Mapped[str] = mapped_column(String(64))
    severity: Mapped[Severity] = mapped_column(EnumValue(Severity, 16))
    exception_type: Mapped[str] = mapped_column(String(255))
    message: Mapped[str] = mapped_column(Text)
    traceback: Mapped[str] = mapped_column(Text)
    context: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    group: Mapped[ErrorGroup] = relationship(back_populates="reports")

class ServerMetricRecord(Base):
    __tablename__ = "server_metrics"
    __table_args__ = (Index("ix_metric_agent_captured", "agent_id", "captured_at"),)
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    agent_id: Mapped[str] = mapped_column(String(36), index=True)
    cpu_percent: Mapped[float] = mapped_column(Float)
    mem_percent: Mapped[float] = mapped_column(Float)
    mem_used: Mapped[int] = mapped_column(BigInteger)
    mem_total: Mapped[int] = mapped_column(BigInteger)
    net_bytes_sent: Mapped[int] = mapped_column(BigInteger)
    net_bytes_recv: Mapped[int] = mapped_column(BigInteger)
    load_1: Mapped[float] = mapped_column(Float)
    load_5: Mapped[float] = mapped_column(Float)
    load_15: Mapped[float] = mapped_column(Float)
    disk_percent: Mapped[float | None] = mapped_column(Float, nullable=True)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

class ContainerStateRecord(Base):
    __tablename__ = "container_states"
    __table_args__ = (UniqueConstraint("agent_id", "container_id", name="uq_container_agent_id"), Index("ix_container_agent", "agent_id"))
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    agent_id: Mapped[str] = mapped_column(String(36), index=True)
    container_id: Mapped[str] = mapped_column(String(64))
    name: Mapped[str] = mapped_column(String(255))
    image: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(64))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    restarts: Mapped[int] = mapped_column(Integer, default=0)
    cpu_percent: Mapped[float | None] = mapped_column(Float, nullable=True)
    mem_percent: Mapped[float | None] = mapped_column(Float, nullable=True)
    mem_usage: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    net_rx: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    net_tx: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    blk_read: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    blk_write: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    labels: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    project_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("projects.id", ondelete="SET NULL"), nullable=True, index=True)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

class AgentFaultRecord(Base):
    __tablename__ = "agent_faults"
    __table_args__ = (Index("ix_fault_agent_occurred", "agent_id", "occurred_at"),)
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    agent_id: Mapped[str] = mapped_column(String(36), index=True)
    component: Mapped[str] = mapped_column(String(64))
    operation: Mapped[str] = mapped_column(String(128))
    exception_type: Mapped[str] = mapped_column(String(255))
    message: Mapped[str] = mapped_column(Text)
    traceback: Mapped[str] = mapped_column(Text)
    severity: Mapped[Severity] = mapped_column(EnumValue(Severity, 16), default=Severity.ERROR)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

class Project(Base):
    __tablename__ = "projects"
    __table_args__ = (UniqueConstraint("account_id", "slug", name="uq_project_account_slug"),)
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_uuid)
    account_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("accounts.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(128))
    slug: Mapped[str] = mapped_column(String(128), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    rules: Mapped[list["ProjectRule"]] = relationship(back_populates="project", cascade="all, delete-orphan")

class ProjectRule(Base):
    __tablename__ = "project_rules"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_uuid)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    match_type: Mapped[str] = mapped_column(String(32))
    match_value: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    project: Mapped[Project] = relationship(back_populates="rules")

class ContainerAssignment(Base):
    __tablename__ = "container_assignments"
    __table_args__ = (UniqueConstraint("project_id", "agent_id", "container_key", name="uq_assignment"),)
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_uuid)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    agent_id: Mapped[str] = mapped_column(String(36), index=True)
    container_key: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

class Bot(Base):
    __tablename__ = "bots"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_uuid)
    account_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("accounts.id", ondelete="CASCADE"), index=True)
    platform: Mapped[str] = mapped_column(String(32), default="telegram")
    bot_token_encrypted: Mapped[str] = mapped_column(Text)
    bot_username: Mapped[str | None] = mapped_column(String(128), nullable=True)
    invite_key: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    invite_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    chat_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[BotStatus] = mapped_column(EnumValue(BotStatus, 16), default=BotStatus.PENDING)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

class Notification(Base):
    __tablename__ = "notifications"
    __table_args__ = (Index("ix_notification_account_created", "account_id", "created_at"),)
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_uuid)
    account_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("accounts.id", ondelete="CASCADE"), index=True)
    kind: Mapped[NotificationKind] = mapped_column(EnumValue(NotificationKind, 32))
    severity: Mapped[Severity] = mapped_column(EnumValue(Severity, 16), default=Severity.ERROR)
    title: Mapped[str] = mapped_column(Text)
    body: Mapped[str] = mapped_column(Text, default="")
    ref: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

class SelfError(Base):
    __tablename__ = "self_errors"
    __table_args__ = (Index("ix_self_error_occurred", "occurred_at"),)
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    component: Mapped[str] = mapped_column(String(128))
    exception_type: Mapped[str] = mapped_column(String(255))
    message: Mapped[str] = mapped_column(Text)
    traceback: Mapped[str] = mapped_column(Text, default="")
    fingerprint: Mapped[str] = mapped_column(String(64), index=True)
    context: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    count: Mapped[int] = mapped_column(BigInteger, default=1)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
