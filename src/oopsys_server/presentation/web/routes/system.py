from dishka.integrations.fastapi import DishkaRoute, FromDishka
from fastapi import APIRouter, Depends, Request
from starlette.responses import Response

from oopsys_server.infrastructure.nats import NotificationGateway
from oopsys_server.infrastructure.persistence.models import Account
from oopsys_server.infrastructure.persistence.repositories import (
    AgentFaultRepository,
    AgentTokenRepository,
    SelfErrorRepository,
)
from oopsys_server.presentation.web.deps import require_account
from oopsys_server.presentation.web.templating import render

router = APIRouter(route_class=DishkaRoute, tags=["web-system"])

@router.get("/system")
async def system_page(request: Request, self_errors: FromDishka[SelfErrorRepository], faults: FromDishka[AgentFaultRepository], tokens: FromDishka[AgentTokenRepository], gateway: FromDishka[NotificationGateway], account: Account=Depends(require_account)) -> Response:
    bound = await tokens.list_for_account(account.id)
    agent_ids = [t.agent_id for t in bound if t.agent_id]
    return render(request, "system.html", {"active": "system", "self_errors": await self_errors.list_recent(limit=100), "agent_faults": await faults.list_for_agents(agent_ids, limit=100), "nats_connected": gateway.connected})
