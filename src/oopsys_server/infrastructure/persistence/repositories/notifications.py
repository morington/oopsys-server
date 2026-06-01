import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from oopsys_server.infrastructure.persistence.base import utc_now
from oopsys_server.infrastructure.persistence.models import Notification


class NotificationRepository:

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, notification: Notification) -> Notification:
        self._session.add(notification)
        await self._session.flush()
        return notification

    async def list_for_account(self, account_id: uuid.UUID, limit: int=50) -> list[Notification]:
        result = await self._session.execute(select(Notification).where(Notification.account_id == account_id).order_by(Notification.created_at.desc()).limit(limit))
        return list(result.scalars().all())

    async def mark_read(self, account_id: uuid.UUID, notification_id: uuid.UUID) -> None:
        notification = await self._session.get(Notification, notification_id)
        if notification is not None and notification.account_id == account_id:
            notification.read_at = utc_now()

    async def mark_all_read(self, account_id: uuid.UUID) -> None:
        result = await self._session.execute(select(Notification).where(Notification.account_id == account_id, Notification.read_at.is_(None)))
        for notification in result.scalars().all():
            notification.read_at = utc_now()
