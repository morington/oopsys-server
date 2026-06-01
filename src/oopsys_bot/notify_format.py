"""Telegram message formatting for bot notifications."""

from __future__ import annotations

import html
import re

TELEGRAM_PARSE_MODE = "HTML"

_AGENT_DOWN = re.compile(r"^Агент недоступен:\s*(.+)$", re.DOTALL)
_AGENT_UP = re.compile(r"^Агент снова на связи:\s*(.+)$", re.DOTALL)
_AGENT_FAULT = re.compile(r"^Сбой агента:\s*(.+)$", re.DOTALL)
_SERVER_ERROR = re.compile(r"^Ошибка сервера:\s*(.+)$", re.DOTALL)


def _esc(text: str) -> str:
    return html.escape(text, quote=False)


def _lines(*parts: str) -> str:
    return "\n".join(part for part in parts if part)


def format_telegram_notification(body: dict) -> str:
    """Build a human-readable Telegram message from a NATS notification payload."""
    kind = str(body.get("kind") or "")
    title = str(body.get("title") or "Уведомление").strip()
    detail = str(body.get("body") or "").strip()

    if kind == "agent_down":
        match = _AGENT_DOWN.match(title)
        server = match.group(1).strip() if match else title
        return _lines(
            "<b>🔴 Агент недоступен</b>",
            f"Сервер: <b>{_esc(server)}</b>",
            f"<i>{_esc(detail)}</i>" if detail else "",
        )

    if kind == "agent_recovered":
        match = _AGENT_UP.match(title)
        server = match.group(1).strip() if match else title
        return _lines(
            "<b>🟢 Агент на связи</b>",
            f"Сервер: <b>{_esc(server)}</b>",
            f"<i>{_esc(detail)}</i>" if detail else "",
        )

    if kind == "agent_fault":
        match = _AGENT_FAULT.match(title)
        where = match.group(1).strip() if match else title
        return _lines(
            "<b>⚠️ Сбой агента</b>",
            f"Компонент: <code>{_esc(where)}</code>",
            f"{_esc(detail)}" if detail else "",
        )

    if kind == "server_error":
        match = _SERVER_ERROR.match(title)
        component = match.group(1).strip() if match else title
        return _lines(
            "<b>🛠 Ошибка сервера oopsys</b>",
            f"Компонент: <code>{_esc(component)}</code>",
            f"{_esc(detail)}" if detail else "",
        )

    if kind == "test":
        return _lines(
            "<b>🧪 Тест уведомлений</b>",
            f"{_esc(detail)}" if detail else "<i>Проверка доставки через NATS и bot-worker.</i>",
        )

    if kind == "error":
        return _lines(
            "<b>❌ Ошибка проекта</b>",
            f"<code>{_esc(title)}</code>",
            f"<i>{_esc(detail)}</i>" if detail else "",
        )

    severity = str(body.get("severity") or "error").lower()
    badge = "🔴" if severity == "critical" else "⚠️"
    return _lines(
        f"<b>{badge} {_esc(title)}</b>",
        f"{_esc(detail)}" if detail else "",
    )
