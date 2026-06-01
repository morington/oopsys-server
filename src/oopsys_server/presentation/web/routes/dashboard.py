from dishka.integrations.fastapi import DishkaRoute, FromDishka
from fastapi import APIRouter, Depends, Request
from starlette.responses import Response

from oopsys_server.domain.enums import AgentStatus
from oopsys_server.infrastructure.persistence.models import Account
from oopsys_server.infrastructure.persistence.repositories import (
    AgentRepository,
    AgentTokenRepository,
    ErrorRepository,
    MetricsRepository,
    NotificationRepository,
)
from oopsys_server.presentation.web.deps import require_account
from oopsys_server.presentation.web.templating import render

router = APIRouter(route_class=DishkaRoute, tags=["web-dashboard"])

async def _agent_ids(tokens: AgentTokenRepository, account: Account) -> list[str]:
    bound = await tokens.list_for_account(account.id)
    return [t.agent_id for t in bound if t.agent_id]

@router.get("/")
async def dashboard(request: Request, tokens: FromDishka[AgentTokenRepository], agents_repo: FromDishka[AgentRepository], errors: FromDishka[ErrorRepository], metrics: FromDishka[MetricsRepository], notifications: FromDishka[NotificationRepository], account: Account=Depends(require_account)) -> Response:
    agent_ids = await _agent_ids(tokens, account)
    all_agents = [a for a in await agents_repo.list_all() if a.agent_id in agent_ids]
    online = sum(1 for a in all_agents if a.status is AgentStatus.ONLINE)
    down = sum(1 for a in all_agents if a.status is AgentStatus.DOWN)
    groups = await errors.list_groups(agent_ids=agent_ids, limit=8)
    open_errors = len(groups)
    recent_notifications = await notifications.list_for_account(account.id, limit=8)
    server_cards = []
    for agent in all_agents:
        latest = await metrics.latest(agent.agent_id)
        server_cards.append({"agent": agent, "latest": latest})
    return render(request, "dashboard.html", {"active": "", "agents_total": len(all_agents), "agents_online": online, "agents_down": down, "open_errors": open_errors, "groups": groups, "notifications": recent_notifications, "server_cards": server_cards})
