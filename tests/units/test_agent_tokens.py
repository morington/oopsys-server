import uuid
from unittest.mock import AsyncMock

from oopsys_server.application.tokens import AgentTokenService
from oopsys_server.infrastructure.persistence.models import AgentToken


async def test_authenticate_rejects_unbound_token() -> None:
    token = AgentToken(id=uuid.uuid4(), token_hash="abc", is_active=True)
    repo = AsyncMock()
    repo.get_by_hash.return_value = token
    repo.is_bound_to_account.return_value = False

    result = await AgentTokenService(repo).authenticate("raw")

    assert result is None
    repo.is_bound_to_account.assert_awaited_once_with(token.id)


async def test_authenticate_accepts_bound_active_token() -> None:
    token = AgentToken(id=uuid.uuid4(), token_hash="abc", is_active=True)
    repo = AsyncMock()
    repo.get_by_hash.return_value = token
    repo.is_bound_to_account.return_value = True

    result = await AgentTokenService(repo).authenticate("raw")

    assert result is token
    assert result.last_seen_at is not None
