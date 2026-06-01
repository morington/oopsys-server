import uuid
from datetime import datetime, timedelta

from oopsys_server.domain.enums import AgentStatus
from oopsys_server.infrastructure.persistence.base import utc_now
from oopsys_server.infrastructure.persistence.models import (
    Account,
    AccountAgent,
    Agent,
    AgentToken,
)
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession


class AgentTokenRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_hash(self, token_hash: str) -> AgentToken | None:
        result = await self._session.execute(
            select(AgentToken).where(AgentToken.token_hash == token_hash)
        )
        return result.scalar_one_or_none()

    async def get_by_id(self, token_id: uuid.UUID) -> AgentToken | None:
        return await self._session.get(AgentToken, token_id)

    async def add(self, token: AgentToken) -> AgentToken:
        self._session.add(token)
        await self._session.flush()
        return token

    async def delete(self, token: AgentToken) -> None:
        await self._session.delete(token)

    async def is_bound_to_account(self, token_id: uuid.UUID) -> bool:
        result = await self._session.execute(
            select(AccountAgent.id)
            .where(AccountAgent.agent_token_id == token_id)
            .limit(1)
        )
        return result.scalar_one_or_none() is not None

    async def bind_account(
        self, account_id: uuid.UUID, token_id: uuid.UUID
    ) -> AccountAgent | None:
        existing = await self._session.execute(
            select(AccountAgent).where(
                AccountAgent.account_id == account_id,
                AccountAgent.agent_token_id == token_id,
            )
        )
        if existing.scalar_one_or_none() is not None:
            return None
        link = AccountAgent(account_id=account_id, agent_token_id=token_id)
        self._session.add(link)
        await self._session.flush()
        return link

    async def unbind_account(self, account_id: uuid.UUID, token_id: uuid.UUID) -> None:
        await self._session.execute(
            delete(AccountAgent).where(
                AccountAgent.account_id == account_id,
                AccountAgent.agent_token_id == token_id,
            )
        )

    async def list_for_account(self, account_id: uuid.UUID) -> list[AgentToken]:
        result = await self._session.execute(
            select(AgentToken)
            .join(AccountAgent, AccountAgent.agent_token_id == AgentToken.id)
            .where(AccountAgent.account_id == account_id)
            .order_by(AgentToken.created_at)
        )
        return list(result.scalars().all())

    async def list_all(self) -> list[AgentToken]:
        result = await self._session.execute(
            select(AgentToken).order_by(AgentToken.created_at)
        )
        return list(result.scalars().all())

    async def accounts_for_agent(self, agent_id: str) -> list[Account]:
        result = await self._session.execute(
            select(Account)
            .join(AccountAgent, AccountAgent.account_id == Account.id)
            .join(AgentToken, AgentToken.id == AccountAgent.agent_token_id)
            .where(AgentToken.agent_id == agent_id)
        )
        return list(result.scalars().unique().all())


class AgentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, agent_id: str) -> Agent | None:
        return await self._session.get(Agent, agent_id)

    async def touch(
        self,
        agent_id: str,
        *,
        name: str | None = None,
        version: str | None = None,
        seen_at: datetime | None = None,
    ) -> Agent:
        seen = seen_at or utc_now()
        agent = await self._session.get(Agent, agent_id)
        if agent is None:
            agent = Agent(
                agent_id=agent_id,
                name=name,
                version=version,
                first_seen=seen,
                last_seen=seen,
            )
            self._session.add(agent)
        else:
            agent.last_seen = seen
            agent.status = AgentStatus.ONLINE
            if name:
                agent.name = name
            if version:
                agent.version = version
        await self._session.flush()
        return agent

    async def list_all(self) -> list[Agent]:
        result = await self._session.execute(select(Agent).order_by(Agent.name))
        return list(result.scalars().all())

    async def list_stale(self, stale_seconds: int) -> list[Agent]:
        cutoff = utc_now() - timedelta(seconds=stale_seconds)
        result = await self._session.execute(
            select(Agent).where(
                Agent.last_seen < cutoff, Agent.status == AgentStatus.ONLINE
            )
        )
        return list(result.scalars().all())

    async def set_status(self, agent_id: str, status: AgentStatus) -> None:
        agent = await self._session.get(Agent, agent_id)
        if agent is not None:
            agent.status = status
