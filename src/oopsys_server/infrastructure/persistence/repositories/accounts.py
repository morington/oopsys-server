import uuid
from datetime import datetime

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from oopsys_server.infrastructure.persistence.base import utc_now
from oopsys_server.infrastructure.persistence.models import Account, Session


class AccountRepository:

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_login(self, login: str) -> Account | None:
        result = await self._session.execute(select(Account).where(Account.login == login))
        return result.scalar_one_or_none()

    async def get_by_id(self, account_id: uuid.UUID) -> Account | None:
        return await self._session.get(Account, account_id)

    async def list_all(self) -> list[Account]:
        result = await self._session.execute(select(Account).order_by(Account.created_at))
        return list(result.scalars().all())

    async def add(self, account: Account) -> Account:
        self._session.add(account)
        await self._session.flush()
        return account

    async def count(self) -> int:
        result = await self._session.execute(select(Account.id))
        return len(result.scalars().all())

class SessionRepository:

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, record: Session) -> Session:
        self._session.add(record)
        await self._session.flush()
        return record

    async def get_by_token_hash(self, token_hash: str) -> Session | None:
        result = await self._session.execute(select(Session).where(Session.token_hash == token_hash))
        return result.scalar_one_or_none()

    async def delete_by_token_hash(self, token_hash: str) -> None:
        await self._session.execute(delete(Session).where(Session.token_hash == token_hash))

    async def delete_for_account(self, account_id: uuid.UUID) -> None:
        await self._session.execute(delete(Session).where(Session.account_id == account_id))

    async def delete_expired(self, now: datetime | None=None) -> None:
        await self._session.execute(delete(Session).where(Session.expires_at < (now or utc_now())))
