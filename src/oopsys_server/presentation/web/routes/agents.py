import uuid

from dishka.integrations.fastapi import DishkaRoute, FromDishka
from fastapi import APIRouter, Depends, Form, Request
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import RedirectResponse, Response

from oopsys_server.application.tokens import AgentTokenService
from oopsys_server.infrastructure.persistence.models import Account
from oopsys_server.infrastructure.persistence.repositories import AgentRepository, AgentTokenRepository
from oopsys_server.presentation.web.deps import require_account
from oopsys_server.presentation.web.templating import render

router = APIRouter(route_class=DishkaRoute, tags=["web-agents"])

@router.get("/agents")
async def agents_page(request: Request, tokens: FromDishka[AgentTokenService], token_repo: FromDishka[AgentTokenRepository], agents_repo: FromDishka[AgentRepository], account: Account=Depends(require_account)) -> Response:
    views = await tokens.list_for_account(account.id)
    agent_rows = {a.agent_id: a for a in await agents_repo.list_all()}
    items = []
    for view in views:
        agent = agent_rows.get(view.agent_id) if view.agent_id else None
        items.append({"token": view, "agent": agent})
    return render(request, "agents.html", {"active": "agents", "items": items})

@router.post("/agents/bind")
async def bind_token(request: Request, tokens: FromDishka[AgentTokenService], session: FromDishka[AsyncSession], token: str=Form(...), label: str | None=Form(None), endpoint_url: str | None=Form(None), account: Account=Depends(require_account)) -> Response:
    await tokens.bind(account.id, token.strip(), label=label or None, endpoint_url=endpoint_url or None)
    await session.commit()
    return RedirectResponse("/agents", status_code=303)

@router.post("/agents/{token_id}/unbind")
async def unbind_token(request: Request, token_id: uuid.UUID, tokens: FromDishka[AgentTokenService], session: FromDishka[AsyncSession], account: Account=Depends(require_account)) -> Response:
    await tokens.unbind(account.id, token_id)
    await session.commit()
    return RedirectResponse("/agents", status_code=303)

@router.post("/agents/{token_id}/revoke")
async def revoke_token(request: Request, token_id: uuid.UUID, tokens: FromDishka[AgentTokenService], session: FromDishka[AsyncSession], account: Account=Depends(require_account)) -> Response:
    await tokens.revoke(token_id)
    await session.commit()
    return RedirectResponse("/agents", status_code=303)
