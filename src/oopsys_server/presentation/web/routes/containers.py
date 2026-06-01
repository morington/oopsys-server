import uuid

from dishka.integrations.fastapi import DishkaRoute, FromDishka
from fastapi import APIRouter, Depends, Form, Request
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import RedirectResponse, Response

from oopsys_server.infrastructure.persistence.models import Account
from oopsys_server.infrastructure.persistence.repositories import (
    AgentTokenRepository,
    ContainerRepository,
    ProjectRepository,
)
from oopsys_server.presentation.web.deps import require_account
from oopsys_server.presentation.web.templating import render

router = APIRouter(route_class=DishkaRoute, tags=["web-containers"])

async def _agent_ids(tokens: AgentTokenRepository, account: Account) -> list[str]:
    bound = await tokens.list_for_account(account.id)
    return [t.agent_id for t in bound if t.agent_id]

@router.get("/containers")
async def containers_page(request: Request, tokens: FromDishka[AgentTokenRepository], containers: FromDishka[ContainerRepository], projects: FromDishka[ProjectRepository], account: Account=Depends(require_account)) -> Response:
    agent_ids = await _agent_ids(tokens, account)
    rows = await containers.list_for_agents(agent_ids)
    project_rows = await projects.list_for_account(account.id)
    project_names = {p.id: p.name for p in project_rows}
    assigned = [r for r in rows if r.project_id in project_names]
    unassigned = [r for r in rows if r.project_id not in project_names]
    return render(request, "containers.html", {"active": "containers", "assigned": assigned, "unassigned": unassigned, "projects": project_rows, "project_names": project_names})

@router.post("/containers/assign")
async def assign(request: Request, tokens: FromDishka[AgentTokenRepository], containers: FromDishka[ContainerRepository], session: FromDishka[AsyncSession], agent_id: str=Form(...), container_id: str=Form(...), project_id: str=Form(...), account: Account=Depends(require_account)) -> Response:
    if agent_id in await _agent_ids(tokens, account):
        target = uuid.UUID(project_id) if project_id else None
        await containers.assign_project(agent_id, container_id, target)
        await session.commit()
    return RedirectResponse("/containers", status_code=303)
