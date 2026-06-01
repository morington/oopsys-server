import uuid

from dishka.integrations.fastapi import DishkaRoute, FromDishka
from fastapi import APIRouter, Depends, Form, Request
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import RedirectResponse, Response

from oopsys_server.application.bots import BotService
from oopsys_server.infrastructure.persistence.models import Account
from oopsys_server.presentation.web.deps import require_account
from oopsys_server.presentation.web.templating import render

router = APIRouter(route_class=DishkaRoute, tags=["web-bots"])

@router.get("/bots")
async def bots_page(
    request: Request,
    bots: FromDishka[BotService],
    session: FromDishka[AsyncSession],
    account: Account = Depends(require_account),
) -> Response:
    if await bots.ensure_usernames(account.id):
        await session.commit()
    rows = await bots.list_for_account(account.id)
    return render(request, "bots.html", {"active": "bots", "bots": rows})

@router.post("/bots/add")
async def add_bot(request: Request, bots: FromDishka[BotService], session: FromDishka[AsyncSession], bot_token: str=Form(...), account: Account=Depends(require_account)) -> Response:
    await bots.register(account.id, bot_token.strip())
    await session.commit()
    return RedirectResponse("/bots", status_code=303)

@router.post("/bots/{bot_id}/delete")
async def delete_bot(request: Request, bot_id: uuid.UUID, bots: FromDishka[BotService], session: FromDishka[AsyncSession], account: Account=Depends(require_account)) -> Response:
    await bots.delete(account.id, bot_id)
    await session.commit()
    return RedirectResponse("/bots", status_code=303)
