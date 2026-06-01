from datetime import UTC, datetime, timedelta

from oopsys_server.presentation.web.container_display import (
    build_container_view,
    format_ports,
    format_started_at,
    format_uptime,
)


def test_format_uptime_running() -> None:
    started = datetime.now(tz=UTC) - timedelta(minutes=42)
    assert format_uptime(started, status="running") == "42 мин"


def test_format_uptime_not_running() -> None:
    started = datetime.now(tz=UTC) - timedelta(minutes=42)
    assert format_uptime(started, status="exited") == "—"


def test_format_ports_joins() -> None:
    assert format_ports(["8000→8000/tcp", "443→443/tcp"]) == "8000→8000/tcp, 443→443/tcp"


def test_build_container_view_includes_runtime_fields() -> None:
    from oopsys_server.infrastructure.persistence.models import ContainerStateRecord

    started = datetime(2026, 6, 1, 19, 12, tzinfo=UTC)
    record = ContainerStateRecord(
        agent_id="a",
        container_id="cid",
        name="web",
        image="nginx",
        status="running",
        started_at=started,
        restarts=2,
        cpu_percent=1.5,
        ports=["8080→80/tcp"],
        health="healthy",
        captured_at=started,
        updated_at=started,
    )
    view = build_container_view(record)
    assert view["started_label"] == "01.06 19:12"
    assert view["ports_label"] == "8080→80/tcp"
    assert view["status_label"] == "running"
