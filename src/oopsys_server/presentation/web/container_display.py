from datetime import UTC, datetime

from oopsys_server.infrastructure.persistence.base import utc_now
from oopsys_server.infrastructure.persistence.models import ContainerStateRecord


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def format_started_at(started_at: datetime | None) -> str:
    if started_at is None:
        return "—"
    return _as_utc(started_at).strftime("%d.%m %H:%M")


def format_uptime(started_at: datetime | None, *, status: str) -> str:
    if started_at is None or status != "running":
        return "—"
    seconds = int((_as_utc(utc_now()) - _as_utc(started_at)).total_seconds())
    if seconds < 0:
        return "—"
    minutes = seconds // 60
    if minutes < 1:
        return "< 1 мин"
    if minutes < 60:
        return f"{minutes} мин"
    hours, mins = divmod(minutes, 60)
    if hours < 24:
        return f"{hours} ч {mins} мин"
    days, hours = divmod(hours, 24)
    return f"{days} д {hours} ч"


def format_ports(ports: list[str] | None) -> str:
    if not ports:
        return "—"
    return ", ".join(ports)


def format_status_label(status: str, health: str | None = None) -> str:
    labels = {
        "running": "running",
        "exited": "exited",
        "paused": "paused",
        "restarting": "restarting",
        "dead": "dead",
        "created": "created",
        "offline": "нет данных",
        "removing": "removing",
    }
    label = labels.get(status, status)
    if health and health not in ("healthy", "none"):
        return f"{label} · {health}"
    return label


def _cpu_label(value: float | None) -> str:
    if value is None:
        return "—"
    try:
        return f"{float(value):.1f}%"
    except (TypeError, ValueError):
        return "—"


def build_container_view(record: ContainerStateRecord) -> dict[str, object]:
    cid = record.container_id or ""
    status = record.status or "unknown"
    ports = list(record.ports or [])
    return {
        "agent_id": record.agent_id,
        "container_id": cid,
        "container_id_short": cid[:12],
        "name": record.name or cid[:12] or "—",
        "image": record.image or "—",
        "status": status,
        "status_label": format_status_label(status, record.health),
        "health": record.health,
        "started_label": format_started_at(record.started_at),
        "uptime_label": format_uptime(record.started_at, status=status),
        "ports_label": format_ports(ports),
        "ports": ports,
        "restarts": record.restarts,
        "cpu_label": _cpu_label(record.cpu_percent),
        "cpu_percent": record.cpu_percent,
        "mem_percent": record.mem_percent,
        "project_id": record.project_id,
        "hidden": record.hidden,
    }
