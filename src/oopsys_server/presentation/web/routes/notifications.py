import uuid

from dishka.integrations.fastapi import DishkaRoute, FromDishka
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import RedirectResponse, Response

from oopsys_server.infrastructure.persistence.models import Account
from oopsys_server.infrastructure.persistence.repositories import NotificationRepository
from oopsys_server.presentation.web.deps import require_account

router = APIRouter(route_class=DishkaRoute, tags=["web-notifications"])


@router.post("/notifications/clear")
async def clear_notifications(
    notifications: FromDishka[NotificationRepository],
    session: FromDishka[AsyncSession],
    account: Account = Depends(require_account),
) -> Response:
    await notifications.delete_all_for_account(account.id)
    await session.commit()
    return RedirectResponse("/", status_code=303)


@router.post("/notifications/{notification_id}/delete")
async def delete_notification(
    notification_id: uuid.UUID,
    notifications: FromDishka[NotificationRepository],
    session: FromDishka[AsyncSession],
    account: Account = Depends(require_account),
) -> Response:
    deleted = await notifications.delete_for_account(account.id, notification_id)
    if not deleted:
        raise HTTPException(status_code=404)
    await session.commit()
    return RedirectResponse("/", status_code=303)
