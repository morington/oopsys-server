import argparse
import asyncio
import uuid
from pathlib import Path

from oopsys_server.application.accounts import AccountService, LoginTakenError
from oopsys_server.application.tokens import AgentTokenService
from oopsys_server.infrastructure.persistence.engine import standalone_session
from oopsys_server.infrastructure.persistence.repositories import (
    AccountRepository,
    AgentTokenRepository,
    BotRepository,
    SessionRepository,
)
from oopsys_server.infrastructure.security import PasswordHasher

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_MIGRATIONS = Path(__file__).resolve().parent / "infrastructure" / "persistence" / "migrations"

async def _account_create(login: str | None, password: str | None) -> int:
    async with standalone_session() as session:
        service = AccountService(AccountRepository(session), SessionRepository(session), PasswordHasher())
        try:
            created = await service.create(login=login, password=password)
        except LoginTakenError as exc:
            print(f"error: {exc}")
            return 1
        await session.commit()
        print("Account created (credentials shown once, store them now):")
        print(f"  login:    {created.login}")
        print(f"  password: {created.password}")
        return 0

async def _account_list() -> int:
    async with standalone_session() as session:
        accounts = await AccountRepository(session).list_all()
        if not accounts:
            print("no accounts")
            return 0
        for acc in accounts:
            flag = " (must change password)" if acc.must_change_password else ""
            print(f"  {acc.login}  [{acc.id}]  active={acc.is_active}{flag}")
        return 0

async def _account_reset(login: str, password: str | None) -> int:
    async with standalone_session() as session:
        service = AccountService(AccountRepository(session), SessionRepository(session), PasswordHasher())
        new_password = await service.reset_password(login, password=password)
        if new_password is None:
            print(f"error: account '{login}' not found")
            return 1
        await session.commit()
        print(f"Password reset for '{login}' (shown once):")
        print(f"  password: {new_password}")
        return 0

async def _token_list() -> int:
    async with standalone_session() as session:
        tokens = await AgentTokenRepository(session).list_all()
        if not tokens:
            print("no agent tokens bound")
            return 0
        for token in tokens:
            accounts = await AgentTokenRepository(session).accounts_for_agent(token.agent_id) if token.agent_id else []
            logins = ", ".join(a.login for a in accounts) or "-"
            seen = token.last_seen_at.isoformat() if token.last_seen_at else "never"
            print(f"  [{token.id}] label={token.label or '-'} agent_id={token.agent_id or '-'}")
            print(f"        active={token.is_active} last_seen={seen} accounts=[{logins}]")
        return 0

async def _token_revoke(token_id: str) -> int:
    async with standalone_session() as session:
        service = AgentTokenService(AgentTokenRepository(session))
        ok = await service.revoke(uuid.UUID(token_id))
        await session.commit()
        print("token revoked" if ok else "token not found")
        return 0 if ok else 1

async def _bot_list() -> int:
    async with standalone_session() as session:
        accounts = {a.id: a.login for a in await AccountRepository(session).list_all()}
        repo = BotRepository(session)
        any_bot = False
        for account_id, login in accounts.items():
            for bot in await repo.list_for_account(account_id):
                any_bot = True
                print(f"  [{bot.id}] account={login} status={bot.status.value} username={bot.bot_username or '-'}")
        if not any_bot:
            print("no bots")
        return 0

def _migrate() -> int:
    from alembic import command
    from alembic.config import Config
    cfg = Config()
    cfg.set_main_option("script_location", str(_MIGRATIONS))
    cfg.set_main_option("prepend_sys_path", str(_PROJECT_ROOT))
    command.upgrade(cfg, "head")
    return 0

def _run() -> int:
    from oopsys_server.main import main
    asyncio.run(main())
    return 0

def _preview() -> int:
    from oopsys_server.presentation.preview.run import run_preview
    run_preview()
    return 0

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="oopsys-server", description="oopsys monitoring server")
    sub = parser.add_subparsers(dest="command", required=True)
    account = sub.add_parser("account", help="manage web accounts")
    account_sub = account.add_subparsers(dest="account_command", required=True)
    create = account_sub.add_parser("create", help="create an account (random creds if omitted)")
    create.add_argument("--login", default=None)
    create.add_argument("--password", default=None)
    account_sub.add_parser("list", help="list accounts")
    reset = account_sub.add_parser("reset-password", help="reset an account password")
    reset.add_argument("login")
    reset.add_argument("--password", default=None)
    token = sub.add_parser("token", help="inspect bound agent tokens")
    token_sub = token.add_subparsers(dest="token_command", required=True)
    token_sub.add_parser("list", help="list bound agent tokens with labels and accounts")
    revoke = token_sub.add_parser("revoke", help="revoke an agent token by id")
    revoke.add_argument("token_id")
    bot = sub.add_parser("bot", help="inspect bots")
    bot_sub = bot.add_subparsers(dest="bot_command", required=True)
    bot_sub.add_parser("list", help="list bots")
    sub.add_parser("migrate", help="apply database migrations (alembic upgrade head)")
    sub.add_parser("run", help="run the server")
    sub.add_parser("preview", help="run the frontend preview (DEV only)")
    return parser

def main(argv: list[str] | None=None) -> int:
    args = _build_parser().parse_args(argv)
    if args.command == "account":
        if args.account_command == "create":
            return asyncio.run(_account_create(args.login, args.password))
        if args.account_command == "list":
            return asyncio.run(_account_list())
        if args.account_command == "reset-password":
            return asyncio.run(_account_reset(args.login, args.password))
    if args.command == "token":
        if args.token_command == "list":
            return asyncio.run(_token_list())
        if args.token_command == "revoke":
            return asyncio.run(_token_revoke(args.token_id))
    if args.command == "bot" and args.bot_command == "list":
        return asyncio.run(_bot_list())
    if args.command == "migrate":
        return _migrate()
    if args.command == "run":
        return _run()
    if args.command == "preview":
        return _preview()
    return 1
if __name__ == "__main__":
    raise SystemExit(main())
