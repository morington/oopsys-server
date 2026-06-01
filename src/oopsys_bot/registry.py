import uuid
from dataclasses import dataclass, field

from aiogram import Bot

from oopsys_server.domain.enums import BotStatus
from oopsys_server.infrastructure.persistence.engine import standalone_session
from oopsys_server.infrastructure.persistence.repositories import BotRepository
from oopsys_server.infrastructure.security import TokenCipher


@dataclass
class BotEntry:
    db_id: uuid.UUID
    account_id: uuid.UUID
    token: str
    chat_id: str | None
    status: BotStatus
    bot: Bot


@dataclass
class BotRegistry:
    cipher: TokenCipher
    by_token: dict[str, BotEntry] = field(default_factory=dict)

    async def reload(self) -> set[str]:
        async with standalone_session() as session:
            repo = BotRepository(session)
            from oopsys_server.infrastructure.persistence.repositories import AccountRepository

            accounts = await AccountRepository(session).list_all()
            rows = []
            for account in accounts:
                rows.extend(await repo.list_for_account(account.id))
        seen: set[str] = set()
        for row in rows:
            token = self.cipher.decrypt(row.bot_token_encrypted)
            if not token:
                continue
            seen.add(token)
            entry = self.by_token.get(token)
            if entry is None:
                self.by_token[token] = BotEntry(
                    db_id=row.id,
                    account_id=row.account_id,
                    token=token,
                    chat_id=row.chat_id,
                    status=row.status,
                    bot=Bot(token=token),
                )
            else:
                entry.chat_id = row.chat_id
                entry.status = row.status
        for token in list(self.by_token):
            if token not in seen:
                self.by_token.pop(token, None)
        return seen

    def entries_for_account(self, account_id: uuid.UUID) -> list[BotEntry]:
        return [
            e
            for e in self.by_token.values()
            if e.account_id == account_id and e.status is BotStatus.LINKED and e.chat_id
        ]

    def bots(self) -> list[Bot]:
        return [e.bot for e in self.by_token.values()]

    async def close(self) -> None:
        for entry in self.by_token.values():
            await entry.bot.session.close()
