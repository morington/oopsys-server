from oopsys_server.application.bot_notify import bot_accepts_notification, merge_notify_kinds, notify_kinds_from_form
from oopsys_server.domain.enums import NotificationKind


def test_merge_notify_kinds_defaults() -> None:
    settings = merge_notify_kinds({})
    assert settings["agent_down"] is True
    assert settings["error_unassigned"] is True


def test_merge_notify_kinds_stored_values() -> None:
    settings = merge_notify_kinds({"agent_down": False, "error": True})
    assert settings["agent_down"] is False
    assert settings["agent_recovered"] is True


def test_bot_accepts_project_error_when_project_enabled() -> None:
    settings = merge_notify_kinds({"error": True})
    payload = {
        "kind": NotificationKind.ERROR.value,
        "project_ids": ["abc"],
        "project_bot_enabled": True,
    }
    assert bot_accepts_notification(settings, payload) is True


def test_bot_rejects_project_error_when_project_disabled() -> None:
    settings = merge_notify_kinds({"error": True})
    payload = {
        "kind": NotificationKind.ERROR.value,
        "project_ids": ["abc"],
        "project_bot_enabled": False,
    }
    assert bot_accepts_notification(settings, payload) is False


def test_bot_rejects_unassigned_errors_when_disabled() -> None:
    settings = merge_notify_kinds({"error": True, "error_unassigned": False})
    payload = {"kind": NotificationKind.ERROR.value, "project_ids": []}
    assert bot_accepts_notification(settings, payload) is False


def test_bot_accepts_test_kind() -> None:
    settings = merge_notify_kinds({"agent_down": False})
    assert bot_accepts_notification(settings, {"kind": "test"}) is True


def test_notify_kinds_from_form() -> None:
    kinds = notify_kinds_from_form({"notify_agent_down": "1", "notify_error": "0"})
    assert kinds["agent_down"] is True
    assert kinds["error"] is False
