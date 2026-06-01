import uuid
from dataclasses import dataclass

from oopsys_server.domain.enums import BotStatus
from oopsys_server.infrastructure.nats import NotificationGateway
from oopsys_server.infrastructure.persistence.models import Bot


@dataclass(slots=True)
class BotTestResult:
    ok: bool
    flash: str
    detail: str | None = None


async def run_bot_test(
    bot: Bot,
    *,
    account_id: uuid.UUID,
    gateway: NotificationGateway,
) -> BotTestResult:
    """Enqueue a test notification through NATS (same path as real alerts)."""
    if bot.account_id != account_id:
        return BotTestResult(ok=False, flash="test_forbidden")
    if bot.status is not BotStatus.LINKED or not bot.chat_id:
        return BotTestResult(ok=False, flash="test_not_linked")

    nats_ok = await gateway.publish(
        str(account_id),
        {
            "kind": "test",
            "severity": "error",
            "title": "Проверка уведомлений",
            "body": "Если вы видите это — NATS и bot-worker работают.",
        },
    )
    if not nats_ok:
        return BotTestResult(ok=False, flash="test_nats_unavailable")
    return BotTestResult(ok=True, flash="test_ok")
