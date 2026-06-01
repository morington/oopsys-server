import uuid

from dishka.integrations.fastapi import DishkaRoute, FromDishka
from fastapi import APIRouter, Depends, Form, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import RedirectResponse, Response

from oopsys_server.application.projects import ProjectService
from oopsys_server.infrastructure.persistence.models import Account
from oopsys_server.infrastructure.persistence.repositories import (
    AgentTokenRepository,
    ContainerRepository,
    ProjectRepository,
)
from oopsys_server.presentation.web.deps import require_account
from oopsys_server.presentation.web.templating import render

router = APIRouter(route_class=DishkaRoute, tags=["web-projects"])

@router.get("/projects")
async def projects_page(request: Request, projects: FromDishka[ProjectRepository], containers: FromDishka[ContainerRepository], tokens: FromDishka[AgentTokenRepository], account: Account=Depends(require_account)) -> Response:
    project_rows = await projects.list_for_account(account.id)
    bound = await tokens.list_for_account(account.id)
    agent_ids = [t.agent_id for t in bound if t.agent_id]
    all_containers = await containers.list_for_agents(agent_ids)
    counts: dict[uuid.UUID, int] = {}
    for c in all_containers:
        if c.project_id is not None:
            counts[c.project_id] = counts.get(c.project_id, 0) + 1
    rules = await projects.list_rules_for_account(account.id)
    rules_by_project: dict[uuid.UUID, list] = {}
    for rule in rules:
        rules_by_project.setdefault(rule.project_id, []).append(rule)
    return render(request, "projects.html", {"active": "projects", "projects": project_rows, "counts": counts, "rules_by_project": rules_by_project})

@router.post("/projects/create")
async def create_project(request: Request, project_service: FromDishka[ProjectService], session: FromDishka[AsyncSession], name: str=Form(...), account: Account=Depends(require_account)) -> Response:
    await project_service.create(account.id, name.strip())
    await session.commit()
    return RedirectResponse("/projects", status_code=303)

@router.post("/projects/{project_id}/rules")
async def add_rule(request: Request, project_id: uuid.UUID, project_service: FromDishka[ProjectService], projects: FromDishka[ProjectRepository], session: FromDishka[AsyncSession], match_type: str=Form(...), match_value: str=Form(...), account: Account=Depends(require_account)) -> Response:
    project = await projects.get(project_id)
    if project is None or project.account_id != account.id:
        raise HTTPException(status_code=404)
    if match_type not in {"service", "label", "container_name"}:
        raise HTTPException(status_code=400)
    await project_service.add_rule(project_id, match_type, match_value.strip())
    await session.commit()
    return RedirectResponse("/projects", status_code=303)

@router.post("/projects/{project_id}/delete")
async def delete_project(request: Request, project_id: uuid.UUID, projects: FromDishka[ProjectRepository], session: FromDishka[AsyncSession], account: Account=Depends(require_account)) -> Response:
    project = await projects.get(project_id)
    if project is None or project.account_id != account.id:
        raise HTTPException(status_code=404)
    await projects.delete(project)
    await session.commit()
    return RedirectResponse("/projects", status_code=303)
