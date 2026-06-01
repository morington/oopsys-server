import uuid
from urllib.parse import quote

from dishka.integrations.fastapi import DishkaRoute, FromDishka
from fastapi import APIRouter, Depends, Form, Request
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import RedirectResponse, Response

from oopsys_server.application.bot_notify import NOTIFY_KIND_LABELS, merge_notify_kinds, notify_kinds_from_form
from oopsys_server.application.bot_test import run_bot_test
from oopsys_server.application.bots import BotService
from oopsys_server.infrastructure.nats import NotificationGateway
from oopsys_server.infrastructure.persistence.models import Account
from oopsys_server.infrastructure.security import TokenCipher
from oopsys_server.presentation.web.deps import require_account
from oopsys_server.presentation.web.templating import render

router = APIRouter(route_class=DishkaRoute, tags=["web-bots"])

_FLASH_MESSAGES: dict[str, tuple[str, str]] = {
    "test_ok": (
        "ok",
        "Тестовое сообщение отправлено в Telegram. Проверьте чат — должно быть два сообщения "
        "(прямая отправка и через очередь NATS).",
    ),
    "test_nats_unavailable": (
        "info",
        "Прямая отправка в Telegram прошла, но очередь NATS недоступна. "
        "Автоматические уведомления не дойдут, пока не заработают NATS и bot-worker.",
    ),
    "test_not_linked": ("error", "Сначала привяжите бота к чату через ссылку или код."),
    "test_tg_fail": ("error", "Не удалось отправить сообщение в Telegram."),
    "test_forbidden": ("error", "Бот не найден."),
}


def _flash_context(flash: str | None, detail: str | None) -> dict[str, str | None]:
    if flash is None or flash not in _FLASH_MESSAGES:
        return {"flash_level": None, "flash_message": None, "flash_detail": None}
    level, message = _FLASH_MESSAGES[flash]
    return {"flash_level": level, "flash_message": message, "flash_detail": detail}


@router.get("/bots")
async def bots_page(
    request: Request,
    bots: FromDishka[BotService],
    session: FromDishka[AsyncSession],
    account: Account = Depends(require_account),
    flash: str | None = None,
    detail: str | None = None,
) -> Response:
    if await bots.ensure_usernames(account.id):
        await session.commit()
    rows = await bots.list_for_account(account.id)
    return render(
        request,
        "bots.html",
        {
            "active": "bots",
            "bots": rows,
            "notify_labels": NOTIFY_KIND_LABELS,
            "bot_settings": {bot.id: merge_notify_kinds(bot.notify_kinds) for bot in rows},
            **_flash_context(flash, detail),
        },
    )


@router.post("/bots/add")
async def add_bot(
    request: Request,
    bots: FromDishka[BotService],
    session: FromDishka[AsyncSession],
    bot_token: str = Form(...),
    account: Account = Depends(require_account),
) -> Response:
    await bots.register(account.id, bot_token.strip())
    await session.commit()
    return RedirectResponse("/bots", status_code=303)


@router.post("/bots/{bot_id}/settings")
async def update_bot_settings(
    request: Request,
    bot_id: uuid.UUID,
    bots: FromDishka[BotService],
    session: FromDishka[AsyncSession],
    account: Account = Depends(require_account),
) -> Response:
    form = {key: value for key, value in (await request.form()).multi_items() if isinstance(value, str)}
    if await bots.update_notify_kinds(account.id, bot_id, notify_kinds_from_form(form)):
        await session.commit()
    return RedirectResponse("/bots", status_code=303)


@router.post("/bots/{bot_id}/test")
async def test_bot(
    request: Request,
    bot_id: uuid.UUID,
    bots: FromDishka[BotService],
    gateway: FromDishka[NotificationGateway],
    cipher: FromDishka[TokenCipher],
    account: Account = Depends(require_account),
) -> Response:
    bot = await bots.get_for_account(account.id, bot_id)
    if bot is None:
        return RedirectResponse("/bots?flash=test_forbidden", status_code=303)
    result = await run_bot_test(bot, account_id=account.id, cipher=cipher, gateway=gateway)
    url = f"/bots?flash={result.flash}"
    if result.detail:
        url = f"{url}&detail={quote(result.detail, safe='')}"
    return RedirectResponse(url, status_code=303)


@router.post("/bots/{bot_id}/delete")
async def delete_bot(
    request: Request,
    bot_id: uuid.UUID,
    bots: FromDishka[BotService],
    session: FromDishka[AsyncSession],
    account: Account = Depends(require_account),
) -> Response:
    await bots.delete(account.id, bot_id)
    await session.commit()
    return RedirectResponse("/bots", status_code=303)
