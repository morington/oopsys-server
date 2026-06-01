import uuid
from dataclasses import dataclass

from oopsys_server.domain.enums import BotStatus
from oopsys_server.infrastructure.nats import NotificationGateway
from oopsys_server.infrastructure.persistence.models import Bot
from oopsys_server.infrastructure.security import TokenCipher
from oopsys_server.infrastructure.telegram import TelegramDeliveryError, send_telegram_message

_TEST_TEXT = "Тестовое уведомление oopsys.\nЕсли вы видите это сообщение — бот и чат настроены верно."


@dataclass(slots=True)
class BotTestResult:
    ok: bool
    flash: str
    detail: str | None = None


async def run_bot_test(
    bot: Bot,
    *,
    account_id: uuid.UUID,
    cipher: TokenCipher,
    gateway: NotificationGateway,
) -> BotTestResult:
    """Send a test message directly and verify the NATS delivery path."""
    if bot.account_id != account_id:
        return BotTestResult(ok=False, flash="test_forbidden")
    if bot.status is not BotStatus.LINKED or not bot.chat_id:
        return BotTestResult(ok=False, flash="test_not_linked")

    token = cipher.decrypt(bot.bot_token_encrypted)
    if not token:
        return BotTestResult(ok=False, flash="test_tg_fail", detail="не удалось расшифровать токен бота")

    try:
        await send_telegram_message(token, bot.chat_id, _TEST_TEXT)
    except TelegramDeliveryError as exc:
        return BotTestResult(ok=False, flash="test_tg_fail", detail=str(exc))

    nats_ok = await gateway.publish(
        str(account_id),
        {
            "kind": "test",
            "severity": "error",
            "title": "Проверка очереди oopsys",
            "body": "Сообщение через NATS — bot-worker доставил его в Telegram.",
        },
    )
    if not nats_ok:
        return BotTestResult(ok=True, flash="test_nats_unavailable")
    return BotTestResult(ok=True, flash="test_ok")
