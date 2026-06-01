from dishka.integrations.fastapi import DishkaRoute, FromDishka
from fastapi import APIRouter, Depends, HTTPException, Request
from starlette.responses import Response

from oopsys_server.infrastructure.persistence.models import Account
from oopsys_server.infrastructure.persistence.repositories import (
    AgentRepository,
    AgentTokenRepository,
    ContainerRepository,
    MetricsRepository,
)
from oopsys_server.presentation.web.agent_names import agent_display_name, agent_labels
from oopsys_server.presentation.web.deps import require_account
from oopsys_server.presentation.web.templating import render

router = APIRouter(route_class=DishkaRoute, tags=["web-servers"])


@router.get("/servers")
async def servers_page(
    request: Request,
    tokens: FromDishka[AgentTokenRepository],
    agents_repo: FromDishka[AgentRepository],
    metrics: FromDishka[MetricsRepository],
    account: Account = Depends(require_account),
) -> Response:
    labels = await agent_labels(tokens, account)
    agent_ids = list(labels)
    rows = [a for a in await agents_repo.list_all() if a.agent_id in agent_ids]
    cards = [
        {
            "agent": agent,
            "latest": await metrics.latest(agent.agent_id),
            "display_name": agent_display_name(agent, labels),
        }
        for agent in rows
    ]
    return render(request, "servers.html", {"active": "servers", "cards": cards})


@router.get("/servers/{agent_id}")
async def server_detail(
    request: Request,
    agent_id: str,
    tokens: FromDishka[AgentTokenRepository],
    agents_repo: FromDishka[AgentRepository],
    metrics: FromDishka[MetricsRepository],
    containers: FromDishka[ContainerRepository],
    account: Account = Depends(require_account),
) -> Response:
    labels = await agent_labels(tokens, account)
    if agent_id not in labels:
        raise HTTPException(status_code=404)
    agent = await agents_repo.get(agent_id)
    if agent is None:
        raise HTTPException(status_code=404)
    display_name = agent_display_name(agent, labels)
    history = await metrics.history(agent_id, since_minutes=120)
    labels = [m.captured_at.strftime("%H:%M") for m in history]
    chart_config = {
        "type": "line",
        "data": {
            "labels": labels,
            "datasets": [
                {
                    "label": "CPU %",
                    "data": [round(m.cpu_percent, 1) for m in history],
                    "borderColor": "#3b6cf6",
                    "tension": 0.3,
                    "pointRadius": 0,
                },
                {
                    "label": "RAM %",
                    "data": [round(m.mem_percent, 1) for m in history],
                    "borderColor": "#1f9d57",
                    "tension": 0.3,
                    "pointRadius": 0,
                },
            ],
        },
        "options": {
            "responsive": True,
            "maintainAspectRatio": False,
            "scales": {"y": {"beginAtZero": True, "max": 100}},
            "plugins": {"legend": {"position": "bottom"}},
        },
    }
    container_rows = await containers.list_for_agents([agent_id])
    return render(
        request,
        "server_detail.html",
        {
            "active": "servers",
            "agent": agent,
            "display_name": display_name,
            "latest": await metrics.latest(agent_id),
            "chart_config": chart_config,
            "containers": container_rows,
            "has_history": bool(history),
        },
    )
