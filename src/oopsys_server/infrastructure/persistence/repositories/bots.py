import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from oopsys_server.domain.enums import BotStatus
from oopsys_server.infrastructure.persistence.models import Bot


class BotRepository:

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, bot: Bot) -> Bot:
        self._session.add(bot)
        await self._session.flush()
        return bot

    async def get(self, bot_id: uuid.UUID) -> Bot | None:
        return await self._session.get(Bot, bot_id)

    async def get_by_invite(self, invite_key: str) -> Bot | None:
        result = await self._session.execute(select(Bot).where(Bot.invite_key == invite_key))
        return result.scalar_one_or_none()

    async def list_for_account(self, account_id: uuid.UUID) -> list[Bot]:
        result = await self._session.execute(select(Bot).where(Bot.account_id == account_id).order_by(Bot.created_at))
        return list(result.scalars().all())

    async def list_linked(self) -> list[Bot]:
        result = await self._session.execute(select(Bot).where(Bot.status == BotStatus.LINKED))
        return list(result.scalars().all())

    async def list_pending(self) -> list[Bot]:
        result = await self._session.execute(select(Bot).where(Bot.status.in_([BotStatus.PENDING, BotStatus.LINKED])))
        return list(result.scalars().all())

    async def delete(self, bot: Bot) -> None:
        await self._session.delete(bot)
