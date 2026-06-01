import uuid
from dataclasses import dataclass

from oopsys_server.infrastructure.persistence.base import utc_now
from oopsys_server.infrastructure.persistence.models import AgentToken
from oopsys_server.infrastructure.persistence.repositories import AgentTokenRepository
from oopsys_server.infrastructure.security import hash_token


@dataclass(slots=True)
class TokenView:
    id: uuid.UUID
    label: str | None
    agent_id: str | None
    endpoint_url: str | None
    is_active: bool
    last_seen_at: str | None


class AgentTokenService:
    def __init__(self, tokens: AgentTokenRepository) -> None:
        self._tokens = tokens

    async def authenticate(self, raw_token: str) -> AgentToken | None:
        token = await self._tokens.get_by_hash(hash_token(raw_token))
        if token is None or not token.is_active:
            return None
        if not await self._tokens.is_bound_to_account(token.id):
            return None
        token.last_seen_at = utc_now()
        return token

    async def link_agent(self, token: AgentToken, agent_id: str) -> None:
        if token.agent_id != agent_id:
            token.agent_id = agent_id

    async def bind(
        self,
        account_id: uuid.UUID,
        raw_token: str,
        *,
        label: str | None = None,
        endpoint_url: str | None = None,
    ) -> AgentToken:
        token_hash = hash_token(raw_token)
        token = await self._tokens.get_by_hash(token_hash)
        if token is None:
            token = await self._tokens.add(
                AgentToken(
                    token_hash=token_hash,
                    label=label,
                    endpoint_url=endpoint_url,
                    is_active=True,
                )
            )
        else:
            if label:
                token.label = label
            if endpoint_url:
                token.endpoint_url = endpoint_url
            token.is_active = True
        await self._tokens.bind_account(account_id, token.id)
        return token

    async def unbind(self, account_id: uuid.UUID, token_id: uuid.UUID) -> None:
        await self._tokens.unbind_account(account_id, token_id)

    async def revoke(self, token_id: uuid.UUID) -> bool:
        token = await self._tokens.get_by_id(token_id)
        if token is None:
            return False
        await self._tokens.delete(token)
        return True

    async def list_for_account(self, account_id: uuid.UUID) -> list[TokenView]:
        tokens = await self._tokens.list_for_account(account_id)
        return [
            TokenView(
                id=token.id,
                label=token.label,
                agent_id=token.agent_id,
                endpoint_url=token.endpoint_url,
                is_active=token.is_active,
                last_seen_at=token.last_seen_at.isoformat()
                if token.last_seen_at
                else None,
            )
            for token in tokens
        ]
