import uuid
from typing import Any

from oopsys_server.domain.enums import NotificationKind, Severity
from oopsys_server.infrastructure.nats import NotificationGateway
from oopsys_server.infrastructure.persistence.models import Notification
from oopsys_server.infrastructure.persistence.repositories import NotificationRepository
from oopsys_server.infrastructure.realtime import RealtimeHub


class NotificationService:

    def __init__(self, notifications: NotificationRepository, gateway: NotificationGateway, hub: RealtimeHub) -> None:
        self._notifications = notifications
        self._gateway = gateway
        self._hub = hub

    async def emit(self, account_ids: list[uuid.UUID], *, kind: NotificationKind, severity: Severity, title: str, body: str="", ref: dict[str, Any] | None=None, push_to_bot: bool=True) -> None:
        ref = ref or {}
        for account_id in account_ids:
            notification = Notification(account_id=account_id, kind=kind, severity=severity, title=title, body=body, ref=ref)
            await self._notifications.add(notification)
            payload = {"id": str(notification.id), "kind": kind.value, "severity": severity.value, "title": title, "body": body, "ref": ref, "created_at": notification.created_at.isoformat()}
            await self._hub.publish_many([account_id], "notification", payload)
            if push_to_bot:
                await self._gateway.publish(str(account_id), payload)
