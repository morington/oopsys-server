from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum

from oopsys_server.configuration.config import SecurityModel
from oopsys_server.infrastructure.persistence.base import utc_now
from oopsys_server.infrastructure.persistence.models import Account, Session
from oopsys_server.infrastructure.persistence.repositories import AccountRepository, SessionRepository
from oopsys_server.infrastructure.security import PasswordHasher, generate_token, hash_token


class AuthStatus(str, Enum):
    OK = "ok"
    INVALID = "invalid"
    LOCKED = "locked"

@dataclass(slots=True)
class AuthResult:
    status: AuthStatus
    account: Account | None = None
    retry_after: int = 0

@dataclass(slots=True)
class IssuedSession:
    raw_token: str
    expires_at: datetime

class AuthService:

    def __init__(self, accounts: AccountRepository, sessions: SessionRepository, hasher: PasswordHasher, config: SecurityModel) -> None:
        self._accounts = accounts
        self._sessions = sessions
        self._hasher = hasher
        self._cfg = config

    def needs_captcha(self, account: Account | None) -> bool:
        return account is not None and account.failed_attempts >= self._cfg.captcha_after_attempts

    def _lock_seconds(self, attempts: int) -> int:
        over = max(0, attempts - self._cfg.max_failed_attempts + 1)
        backoff = self._cfg.lockout_base_seconds * 2 ** max(0, over - 1)
        return min(backoff, self._cfg.lockout_max_seconds)

    async def authenticate(self, login: str, password: str, *, now: datetime | None=None) -> AuthResult:
        now = now or utc_now()
        account = await self._accounts.get_by_login(login)
        if account is None or not account.is_active:
            self._hasher.hash(password)
            return AuthResult(status=AuthStatus.INVALID)
        if account.locked_until is not None and account.locked_until > now:
            return AuthResult(status=AuthStatus.LOCKED, account=account, retry_after=int((account.locked_until - now).total_seconds()))
        if not self._hasher.verify(account.password_hash, password):
            account.failed_attempts += 1
            if account.failed_attempts >= self._cfg.max_failed_attempts:
                lock_for = self._lock_seconds(account.failed_attempts)
                account.locked_until = now + timedelta(seconds=lock_for)
                return AuthResult(status=AuthStatus.LOCKED, account=account, retry_after=lock_for)
            return AuthResult(status=AuthStatus.INVALID, account=account)
        account.failed_attempts = 0
        account.locked_until = None
        return AuthResult(status=AuthStatus.OK, account=account)

    async def issue_session(self, account: Account, *, remember: bool, ip: str | None=None, user_agent: str | None=None) -> IssuedSession:
        raw_token = generate_token(32)
        ttl = self._cfg.remember_ttl_seconds if remember else self._cfg.session_ttl_seconds
        expires_at = utc_now() + timedelta(seconds=ttl)
        await self._sessions.add(Session(account_id=account.id, token_hash=hash_token(raw_token), remember=remember, ip=ip, user_agent=(user_agent or "")[:256] or None, expires_at=expires_at))
        return IssuedSession(raw_token=raw_token, expires_at=expires_at)

    async def resolve_session(self, raw_token: str, *, now: datetime | None=None) -> Account | None:
        now = now or utc_now()
        session = await self._sessions.get_by_token_hash(hash_token(raw_token))
        if session is None:
            return None
        if session.expires_at <= now:
            await self._sessions.delete_by_token_hash(session.token_hash)
            return None
        return await self._accounts.get_by_id(session.account_id)

    async def revoke_session(self, raw_token: str) -> None:
        await self._sessions.delete_by_token_hash(hash_token(raw_token))
