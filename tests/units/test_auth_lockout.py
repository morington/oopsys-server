from datetime import UTC, datetime, timedelta

import pytest

from oopsys_server.application.auth import AuthService, AuthStatus
from oopsys_server.configuration.config import SecurityModel
from oopsys_server.infrastructure.persistence.models import Account
from oopsys_server.infrastructure.security import PasswordHasher

pytestmark = pytest.mark.asyncio

NOW = datetime(2026, 1, 1, tzinfo=UTC)


class _FakeAccounts:
    def __init__(self, account: Account | None) -> None:
        self._account = account

    async def get_by_login(self, login: str) -> Account | None:
        return self._account

    async def get_by_id(self, account_id):  # noqa: ANN001
        return self._account


class _FakeSessions:
    async def delete_for_account(self, account_id):  # noqa: ANN001
        return None


def _service(account: Account | None) -> AuthService:
    cfg = SecurityModel(max_failed_attempts=3, lockout_base_seconds=5, captcha_after_attempts=2)
    return AuthService(_FakeAccounts(account), _FakeSessions(), PasswordHasher(), cfg)


async def test_authenticate_success():
    hasher = PasswordHasher()
    account = Account(login="u", password_hash=hasher.hash("pw-correct-123"), is_active=True)
    result = await _service(account).authenticate("u", "pw-correct-123", now=NOW)
    assert result.status is AuthStatus.OK


async def test_authenticate_unknown_login():
    result = await _service(None).authenticate("ghost", "whatever", now=NOW)
    assert result.status is AuthStatus.INVALID


async def test_lockout_after_max_attempts():
    hasher = PasswordHasher()
    account = Account(login="u", password_hash=hasher.hash("right"), failed_attempts=2, is_active=True)
    service = _service(account)
    result = await service.authenticate("u", "wrong", now=NOW)
    assert result.status is AuthStatus.LOCKED
    assert account.locked_until is not None
    assert result.retry_after > 0


async def test_locked_account_rejected_before_verify():
    account = Account(login="u", password_hash="x", locked_until=NOW + timedelta(minutes=5), is_active=True)
    result = await _service(account).authenticate("u", "anything", now=NOW)
    assert result.status is AuthStatus.LOCKED


async def test_needs_captcha_threshold():
    account = Account(login="u", password_hash="x", failed_attempts=2)
    assert _service(account).needs_captcha(account) is True
    account.failed_attempts = 1
    assert _service(account).needs_captcha(account) is False
