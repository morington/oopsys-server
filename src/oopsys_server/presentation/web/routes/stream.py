import asyncio
import json

from dishka.integrations.fastapi import DishkaRoute, FromDishka
from fastapi import APIRouter, Depends, Request
from sse_starlette.sse import EventSourceResponse

from oopsys_server.infrastructure.persistence.models import Account
from oopsys_server.infrastructure.realtime import RealtimeHub
from oopsys_server.presentation.web.deps import require_account

router = APIRouter(route_class=DishkaRoute, tags=["web-stream"])

@router.get("/web/stream")
async def stream(request: Request, hub: FromDishka[RealtimeHub], account: Account=Depends(require_account)) -> EventSourceResponse:
    queue = await hub.subscribe(account.id)

    async def event_generator():
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=20.0)
                except TimeoutError:
                    yield {"event": "ping", "data": "{}"}
                    continue
                yield {"event": event.event, "data": json.dumps(event.data, ensure_ascii=False)}
        finally:
            await hub.unsubscribe(account.id, queue)
    return EventSourceResponse(event_generator())
