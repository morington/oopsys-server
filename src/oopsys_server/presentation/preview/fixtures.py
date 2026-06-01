import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any

from oopsys_server.domain.enums import AgentStatus, BotStatus, ErrorGroupStatus, Severity

PAGES: dict[str, str] = {"dashboard": "dashboard.html", "agents": "agents.html", "servers": "servers.html", "server_detail": "server_detail.html", "errors": "errors.html", "error_detail": "error_detail.html", "containers": "containers.html", "projects": "projects.html", "bots": "bots.html", "system": "system.html", "settings": "settings.html", "login": "login.html"}
SCENARIOS = ["default", "empty", "critical", "down", "spam"]
_NOW = datetime.now(tz=UTC)

def _ns(**kwargs: Any) -> SimpleNamespace:
    return SimpleNamespace(**kwargs)

def _agent(name: str, status: AgentStatus=AgentStatus.ONLINE) -> SimpleNamespace:
    return _ns(agent_id=str(uuid.uuid4()), name=name, version="1.2.0", status=status, first_seen=_NOW - timedelta(days=3), last_seen=_NOW - timedelta(seconds=12 if status is AgentStatus.ONLINE else 600))

def _metric(cpu: float, mem: float, disk: float=40.0) -> SimpleNamespace:
    return _ns(cpu_percent=cpu, mem_percent=mem, mem_used=4 * 1024 * 1024 * 1024, mem_total=8 * 1024 * 1024 * 1024, load_1=cpu / 50, load_5=cpu / 60, load_15=cpu / 70, disk_percent=disk, captured_at=_NOW)

def _group(exc: str, service: str, severity: Severity, count: int, status: ErrorGroupStatus=ErrorGroupStatus.OPEN) -> SimpleNamespace:
    return _ns(id=uuid.uuid4(), agent_id=str(uuid.uuid4()), fingerprint=uuid.uuid4().hex, service=service, environment="production", exception_type=exc, title=f"{exc}: something went wrong in {service}", severity=severity, status=status, count=count, first_seen=_NOW - timedelta(hours=4), last_seen=_NOW - timedelta(minutes=2), last_notified_at=_NOW - timedelta(minutes=5))

def _container(name: str, image: str, status: str="running", project_id: uuid.UUID | None=None) -> SimpleNamespace:
    return _ns(agent_id=str(uuid.uuid4()), container_id=uuid.uuid4().hex, name=name, image=image, status=status, cpu_percent=12.3, mem_percent=22.1, restarts=0, project_id=project_id)

def _notification(title: str, severity: Severity, body: str="") -> SimpleNamespace:
    return _ns(title=title, body=body, severity=severity, created_at=_NOW - timedelta(minutes=1))

def _account() -> SimpleNamespace:
    return _ns(login="agent-demo01", must_change_password=True)

def build_context(page: str, scenario: str) -> dict[str, Any]:
    builder = _BUILDERS.get(page)
    if builder is None:
        return {"active": page}
    ctx = builder(scenario)
    ctx.setdefault("active", page)
    return ctx

def _dashboard(scenario: str) -> dict[str, Any]:
    if scenario == "empty":
        return {"agents_total": 0, "agents_online": 0, "agents_down": 0, "open_errors": 0, "server_cards": [], "notifications": [], "groups": []}
    online = _agent("web-prod")
    down = _agent("worker-eu", AgentStatus.DOWN)
    severity = Severity.CRITICAL if scenario == "critical" else Severity.ERROR
    return {"agents_total": 2, "agents_online": 1, "agents_down": 1 if scenario == "down" else 0, "open_errors": 3, "server_cards": [{"agent": online, "latest": _metric(72 if scenario == "critical" else 35, 58)}, {"agent": down, "latest": _metric(5, 20)}], "notifications": [_notification("Агент недоступен: worker-eu", Severity.CRITICAL, "Нет данных более 90 с"), _notification("ValueError в cryptobot", severity, "cryptobot · production")], "groups": [_group("ValueError", "cryptobot", severity, 42 if scenario == "spam" else 3), _group("TimeoutError", "payments", Severity.ERROR, 7)]}

def _agents(scenario: str) -> dict[str, Any]:
    if scenario == "empty":
        return {"items": []}
    a1 = _agent("web-prod")
    a2 = _agent("worker-eu", AgentStatus.DOWN)
    return {"items": [{"token": _ns(id=uuid.uuid4(), label="prod-1", agent_id=a1.agent_id, is_active=True), "agent": a1}, {"token": _ns(id=uuid.uuid4(), label="eu-worker", agent_id=a2.agent_id, is_active=True), "agent": a2}, {"token": _ns(id=uuid.uuid4(), label="new", agent_id=None, is_active=True), "agent": None}]}

def _servers(scenario: str) -> dict[str, Any]:
    if scenario == "empty":
        return {"cards": []}
    cpu = 88 if scenario == "critical" else 34
    return {"cards": [{"agent": _agent("web-prod"), "latest": _metric(cpu, 61)}, {"agent": _agent("worker-eu", AgentStatus.DOWN), "latest": _metric(4, 18)}]}

def _server_detail(scenario: str) -> dict[str, Any]:
    history_labels = [f"{h:02d}:00" for h in range(10, 22)]
    cfg = {"type": "line", "data": {"labels": history_labels, "datasets": [{"label": "CPU %", "data": [20, 35, 60, 88, 70, 40, 30, 33, 41, 55, 62, 48], "borderColor": "#3b6cf6", "tension": 0.3, "pointRadius": 0}, {"label": "RAM %", "data": [40, 42, 45, 60, 58, 55, 50, 52, 53, 57, 61, 59], "borderColor": "#1f9d57", "tension": 0.3, "pointRadius": 0}]}, "options": {"responsive": True, "maintainAspectRatio": False, "scales": {"y": {"beginAtZero": True, "max": 100}}, "plugins": {"legend": {"position": "bottom"}}}}
    return {"agent": _agent("web-prod"), "latest": _metric(88 if scenario == "critical" else 34, 61), "chart_config": cfg, "has_history": scenario != "empty", "containers": [_container("web", "nginx:1.27"), _container("db", "postgres:16", "exited")]}

def _errors(scenario: str) -> dict[str, Any]:
    if scenario == "empty":
        return {"groups": []}
    sev = Severity.CRITICAL if scenario == "critical" else Severity.ERROR
    return {"groups": [_group("ValueError", "cryptobot", sev, 42 if scenario == "spam" else 3), _group("TimeoutError", "payments", Severity.ERROR, 7), _group("KeyError", "api", Severity.ERROR, 1, ErrorGroupStatus.RESOLVED)]}

def _error_detail(scenario: str) -> dict[str, Any]:
    group = _group("ValueError", "cryptobot", Severity.CRITICAL if scenario == "critical" else Severity.ERROR, 12)
    reports = [_ns(message="invalid literal for int() with base 10: 'abc'", occurred_at=_NOW - timedelta(minutes=i * 3), context={"user_id": 1024, "endpoint": "/pay"}, traceback="Traceback (most recent call last):\n  File 'app.py', line 42, in handle\n    int(value)\nValueError: invalid literal for int()") for i in range(3)]
    return {"group": group, "reports": reports}

def _containers(scenario: str) -> dict[str, Any]:
    pid = uuid.uuid4()
    projects = [_ns(id=pid, name="cryptobot", slug="cryptobot")]
    if scenario == "empty":
        return {"assigned": [], "unassigned": [], "projects": projects, "project_names": {pid: "cryptobot"}}
    return {"assigned": [_container("bot", "cryptobot:latest", project_id=pid)], "unassigned": [_container("redis", "redis:7"), _container("nginx", "nginx:1.27")], "projects": projects, "project_names": {pid: "cryptobot"}}

def _projects(scenario: str) -> dict[str, Any]:
    if scenario == "empty":
        return {"projects": [], "counts": {}, "rules_by_project": {}}
    pid = uuid.uuid4()
    return {"projects": [_ns(id=pid, name="cryptobot", slug="cryptobot")], "counts": {pid: 3}, "rules_by_project": {pid: [_ns(match_type="service", match_value="cryptobot"), _ns(match_type="label", match_value="com.docker.compose.project=cryptobot")]}}

def _bots(scenario: str) -> dict[str, Any]:
    if scenario == "empty":
        return {"bots": []}
    return {"bots": [_ns(id=uuid.uuid4(), bot_username="@my_alerts_bot", status=BotStatus.LINKED, invite_key="abc123", chat_id="123456789"), _ns(id=uuid.uuid4(), bot_username=None, status=BotStatus.PENDING, invite_key="invite-xyz-789", chat_id=None)]}

def _system(scenario: str) -> dict[str, Any]:
    if scenario == "empty":
        return {"nats_connected": True, "self_errors": [], "agent_faults": []}
    return {"nats_connected": scenario != "down", "self_errors": [_ns(component="web:/agents/ingest", exception_type="IntegrityError", message="duplicate key value", count=2, occurred_at=_NOW)], "agent_faults": [_ns(agent_id=str(uuid.uuid4()), component="docker", operation="collect_stats", exception_type="DockerException", occurred_at=_NOW)]}

def _settings(scenario: str) -> dict[str, Any]:
    return {"error": "Пароли не совпадают" if scenario == "critical" else None, "ok": "Настройки сохранены" if scenario == "default" else None}

def _login(scenario: str) -> dict[str, Any]:
    from oopsys_server.infrastructure.security.captcha import generate_captcha
    ctx: dict[str, Any] = {"error": None, "login_value": "", "captcha_required": False}
    if scenario in {"critical", "spam"}:
        ctx["error"] = "Неверный логин или пароль"
    if scenario == "spam":
        ctx["captcha_required"] = True
        ctx["captcha_data_uri"] = generate_captcha().data_uri
        ctx["captcha_id"] = "preview"
    return ctx
_BUILDERS = {"dashboard": _dashboard, "agents": _agents, "servers": _servers, "server_detail": _server_detail, "errors": _errors, "error_detail": _error_detail, "containers": _containers, "projects": _projects, "bots": _bots, "system": _system, "settings": _settings, "login": _login}
