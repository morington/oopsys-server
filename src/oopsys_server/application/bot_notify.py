from typing import Any

from oopsys_server.domain.enums import NotificationKind

NOTIFY_KIND_LABELS: dict[str, str] = {
    "error": "Ошибки проектов",
    "error_unassigned": "Ошибки без проекта",
    "agent_down": "Агент недоступен",
    "agent_recovered": "Агент снова на связи",
    "agent_fault": "Сбои агента",
    "server_error": "Ошибки сервера oopsys",
}

DEFAULT_NOTIFY_KINDS: dict[str, bool] = dict.fromkeys(NOTIFY_KIND_LABELS, True)


def merge_notify_kinds(stored: dict[str, Any] | None) -> dict[str, bool]:
    merged = dict(DEFAULT_NOTIFY_KINDS)
    if stored:
        for key in NOTIFY_KIND_LABELS:
            if key in stored:
                merged[key] = bool(stored[key])
    return merged


def bot_accepts_notification(settings: dict[str, bool], payload: dict[str, Any]) -> bool:
    kind = payload.get("kind", "")
    if kind == NotificationKind.ERROR.value:
        if not settings.get("error", True):
            return False
        project_ids = payload.get("project_ids") or []
        if not project_ids:
            return settings.get("error_unassigned", True)
        return bool(payload.get("project_bot_enabled"))
    return settings.get(kind, DEFAULT_NOTIFY_KINDS.get(kind, True))


def notify_kinds_from_form(form: dict[str, str]) -> dict[str, bool]:
    return {key: form.get(f"notify_{key}") == "1" for key in NOTIFY_KIND_LABELS}
