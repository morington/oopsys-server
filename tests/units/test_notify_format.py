from oopsys_bot.notify_format import format_telegram_notification


def test_agent_down_format() -> None:
    text = format_telegram_notification(
        {
            "kind": "agent_down",
            "severity": "critical",
            "title": "Агент недоступен: serverbots",
            "body": "Нет данных более 90 с",
        }
    )
    assert "🔴" in text
    assert "serverbots" in text
    assert "90" in text
    assert "[CRITICAL]" not in text


def test_agent_recovered_format() -> None:
    text = format_telegram_notification(
        {
            "kind": "agent_recovered",
            "severity": "error",
            "title": "Агент снова на связи: serverbots",
        }
    )
    assert "🟢" in text
    assert "serverbots" in text


def test_project_error_format() -> None:
    text = format_telegram_notification(
        {
            "kind": "error",
            "title": "ZeroDivisionError: division by zero",
            "body": "test_app · production",
        }
    )
    assert "❌" in text
    assert "ZeroDivisionError" in text
    assert "test_app" in text


def test_test_kind_format() -> None:
    text = format_telegram_notification(
        {
            "kind": "test",
            "title": "Проверка уведомлений oopsys",
            "body": "Если вы видите это — NATS и bot-worker работают.",
        }
    )
    assert "🧪" in text
    assert "NATS" in text
