import secrets
import string
import uuid
from dataclasses import dataclass

from oopsys_server.infrastructure.persistence.models import Account
from oopsys_server.infrastructure.persistence.repositories import AccountRepository, SessionRepository
from oopsys_server.infrastructure.security import PasswordHasher

_LOGIN_ALPHABET = string.ascii_lowercase + string.digits
_PASSWORD_ALPHABET = string.ascii_letters + string.digits + "!@#$%^&*-_"

class LoginTakenError(RuntimeError):
    pass

@dataclass(slots=True)
class CreatedAccount:
    login: str
    password: str
    account_id: uuid.UUID

def _random_login() -> str:
    return "agent-" + "".join(secrets.choice(_LOGIN_ALPHABET) for _ in range(6))

def _random_password(length: int=20) -> str:
    return "".join(secrets.choice(_PASSWORD_ALPHABET) for _ in range(length))

class AccountService:

    def __init__(self, accounts: AccountRepository, sessions: SessionRepository, hasher: PasswordHasher) -> None:
        self._accounts = accounts
        self._sessions = sessions
        self._hasher = hasher

    async def create(self, *, login: str | None=None, password: str | None=None) -> CreatedAccount:
        login = login or _random_login()
        password = password or _random_password()
        if await self._accounts.get_by_login(login) is not None:
            raise LoginTakenError(f"login '{login}' already exists")
        account = await self._accounts.add(Account(login=login, password_hash=self._hasher.hash(password), must_change_password=True))
        return CreatedAccount(login=login, password=password, account_id=account.id)

    async def reset_password(self, login: str, *, password: str | None=None) -> str | None:
        account = await self._accounts.get_by_login(login)
        if account is None:
            return None
        new_password = password or _random_password()
        account.password_hash = self._hasher.hash(new_password)
        account.must_change_password = True
        account.failed_attempts = 0
        account.locked_until = None
        await self._sessions.delete_for_account(account.id)
        return new_password

    async def change_credentials(self, account: Account, *, new_login: str | None=None, new_password: str | None=None) -> None:
        if new_login and new_login != account.login:
            if await self._accounts.get_by_login(new_login) is not None:
                raise LoginTakenError(f"login '{new_login}' already exists")
            account.login = new_login
        if new_password:
            account.password_hash = self._hasher.hash(new_password)
            account.must_change_password = False
            await self._sessions.delete_for_account(account.id)

    async def list_all(self) -> list[Account]:
        return await self._accounts.list_all()
