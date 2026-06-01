import uuid

from dishka.integrations.fastapi import DishkaRoute, FromDishka
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import RedirectResponse, Response

from oopsys_server.domain.enums import ErrorGroupStatus
from oopsys_server.infrastructure.persistence.models import Account
from oopsys_server.infrastructure.persistence.repositories import AgentTokenRepository, ErrorRepository
from oopsys_server.presentation.web.deps import require_account
from oopsys_server.presentation.web.templating import render

router = APIRouter(route_class=DishkaRoute, tags=["web-errors"])


async def _agent_ids(tokens: AgentTokenRepository, account: Account) -> list[str]:
    bound = await tokens.list_for_account(account.id)
    return [t.agent_id for t in bound if t.agent_id]


@router.post("/errors/clear")
async def clear_errors(
    tokens: FromDishka[AgentTokenRepository],
    errors: FromDishka[ErrorRepository],
    session: FromDishka[AsyncSession],
    account: Account = Depends(require_account),
) -> Response:
    await errors.delete_groups_for_agents(await _agent_ids(tokens, account))
    await session.commit()
    return RedirectResponse("/", status_code=303)


@router.post("/errors/{group_id}/delete")
async def delete_error_group(
    group_id: uuid.UUID,
    tokens: FromDishka[AgentTokenRepository],
    errors: FromDishka[ErrorRepository],
    session: FromDishka[AsyncSession],
    account: Account = Depends(require_account),
) -> Response:
    group = await errors.get_group(group_id)
    if group is None or group.agent_id not in await _agent_ids(tokens, account):
        raise HTTPException(status_code=404)
    await errors.delete_group(group_id)
    await session.commit()
    return RedirectResponse("/", status_code=303)


@router.get("/errors")
async def errors_page(
    request: Request,
    tokens: FromDishka[AgentTokenRepository],
    errors: FromDishka[ErrorRepository],
    account: Account = Depends(require_account),
) -> Response:
    groups = await errors.list_groups(agent_ids=await _agent_ids(tokens, account), limit=200)
    return render(request, "errors.html", {"active": "errors", "groups": groups})


@router.get("/errors/{group_id}")
async def error_detail(
    request: Request,
    group_id: uuid.UUID,
    tokens: FromDishka[AgentTokenRepository],
    errors: FromDishka[ErrorRepository],
    account: Account = Depends(require_account),
) -> Response:
    group = await errors.get_group(group_id)
    if group is None or group.agent_id not in await _agent_ids(tokens, account):
        raise HTTPException(status_code=404)
    reports = await errors.recent_reports(group_id, limit=20)
    return render(request, "error_detail.html", {"active": "errors", "group": group, "reports": reports})


async def _set_status(
    group_id: uuid.UUID,
    status: ErrorGroupStatus,
    tokens: AgentTokenRepository,
    errors: ErrorRepository,
    session: AsyncSession,
    account: Account,
) -> None:
    group = await errors.get_group(group_id)
    if group is None or group.agent_id not in await _agent_ids(tokens, account):
        raise HTTPException(status_code=404)
    await errors.set_status(group_id, status)
    await session.commit()


@router.post("/errors/{group_id}/mute")
async def mute(
    request: Request,
    group_id: uuid.UUID,
    tokens: FromDishka[AgentTokenRepository],
    errors: FromDishka[ErrorRepository],
    session: FromDishka[AsyncSession],
    account: Account = Depends(require_account),
) -> Response:
    await _set_status(group_id, ErrorGroupStatus.MUTED, tokens, errors, session, account)
    return RedirectResponse(f"/errors/{group_id}", status_code=303)


@router.post("/errors/{group_id}/resolve")
async def resolve(
    request: Request,
    group_id: uuid.UUID,
    tokens: FromDishka[AgentTokenRepository],
    errors: FromDishka[ErrorRepository],
    session: FromDishka[AsyncSession],
    account: Account = Depends(require_account),
) -> Response:
    await _set_status(group_id, ErrorGroupStatus.RESOLVED, tokens, errors, session, account)
    return RedirectResponse(f"/errors/{group_id}", status_code=303)


@router.post("/errors/{group_id}/reopen")
async def reopen(
    request: Request,
    group_id: uuid.UUID,
    tokens: FromDishka[AgentTokenRepository],
    errors: FromDishka[ErrorRepository],
    session: FromDishka[AsyncSession],
    account: Account = Depends(require_account),
) -> Response:
    await _set_status(group_id, ErrorGroupStatus.OPEN, tokens, errors, session, account)
    return RedirectResponse(f"/errors/{group_id}", status_code=303)
