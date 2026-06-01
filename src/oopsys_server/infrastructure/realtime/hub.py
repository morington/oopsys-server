import asyncio
import contextlib
import uuid
from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class RealtimeEvent:
    account_id: uuid.UUID
    event: str
    data: dict[str, Any] = field(default_factory=dict)

class RealtimeHub:

    def __init__(self, max_queue: int=100) -> None:
        self._subscribers: dict[uuid.UUID, set[asyncio.Queue[RealtimeEvent]]] = {}
        self._max_queue = max_queue
        self._lock = asyncio.Lock()

    async def subscribe(self, account_id: uuid.UUID) -> asyncio.Queue[RealtimeEvent]:
        queue: asyncio.Queue[RealtimeEvent] = asyncio.Queue(maxsize=self._max_queue)
        async with self._lock:
            self._subscribers.setdefault(account_id, set()).add(queue)
        return queue

    async def unsubscribe(self, account_id: uuid.UUID, queue: asyncio.Queue[RealtimeEvent]) -> None:
        async with self._lock:
            subscribers = self._subscribers.get(account_id)
            if subscribers is not None:
                subscribers.discard(queue)
                if not subscribers:
                    self._subscribers.pop(account_id, None)

    async def publish(self, event: RealtimeEvent) -> None:
        async with self._lock:
            queues = list(self._subscribers.get(event.account_id, ()))
        for queue in queues:
            with contextlib.suppress(asyncio.QueueFull):
                queue.put_nowait(event)

    async def publish_many(self, account_ids: list[uuid.UUID], event_name: str, data: dict[str, Any]) -> None:
        for account_id in account_ids:
            await self.publish(RealtimeEvent(account_id=account_id, event=event_name, data=data))
