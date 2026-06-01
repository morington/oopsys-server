import uuid
from dataclasses import dataclass, field

from aiogram import Bot
from aiogram.client.session.aiohttp import AiohttpSession

from oopsys_server.application.bot_notify import merge_notify_kinds
from oopsys_server.domain.enums import BotStatus
from oopsys_server.infrastructure.persistence.engine import standalone_session
from oopsys_server.infrastructure.persistence.repositories import AccountRepository, BotRepository
from oopsys_server.infrastructure.security import TokenCipher
from oopsys_server.infrastructure.telegram import fetch_bot_username


def _make_bot(token: str) -> Bot:
    return Bot(token=token, session=AiohttpSession())


@dataclass
class BotEntry:
    db_id: uuid.UUID
    account_id: uuid.UUID
    token: str
    chat_id: str | None
    status: BotStatus
    notify_kinds: dict[str, bool]


@dataclass
class BotRegistry:
    """One Telegram client per token; many oopsys accounts may share the same token."""

    cipher: TokenCipher
    entries: dict[uuid.UUID, BotEntry] = field(default_factory=dict)
    clients: dict[str, Bot] = field(default_factory=dict)

    async def reload(self) -> frozenset[str]:
        async with standalone_session() as session:
            repo = BotRepository(session)
            accounts = await AccountRepository(session).list_all()
            rows = []
            for account in accounts:
                rows.extend(await repo.list_for_account(account.id))
            live_ids: set[uuid.UUID] = set()
            live_tokens: set[str] = set()
            updated = False
            for row in rows:
                token = self.cipher.decrypt(row.bot_token_encrypted)
                if not token:
                    continue
                if not row.bot_username:
                    username = await fetch_bot_username(token)
                    if username:
                        row.bot_username = username
                        updated = True
                live_ids.add(row.id)
                live_tokens.add(token)
                if token not in self.clients:
                    self.clients[token] = _make_bot(token)
                self.entries[row.id] = BotEntry(
                    db_id=row.id,
                    account_id=row.account_id,
                    token=token,
                    chat_id=row.chat_id,
                    status=row.status,
                    notify_kinds=merge_notify_kinds(row.notify_kinds),
                )
            for db_id in list(self.entries):
                if db_id not in live_ids:
                    self.entries.pop(db_id, None)
            for token in list(self.clients):
                if token not in live_tokens:
                    await self.clients.pop(token).session.close()
            if updated:
                await session.commit()
        return self.pending_tokens()

    def pending_tokens(self) -> frozenset[str]:
        return frozenset(entry.token for entry in self.entries.values() if entry.status is BotStatus.PENDING)

    def token_for_bot(self, bot: Bot) -> str | None:
        for token, client in self.clients.items():
            if client is bot:
                return token
        return None

    def client_for(self, token: str) -> Bot:
        return self.clients[token]

    def linked_entry_for_chat(self, bot: Bot, chat_id: str) -> BotEntry | None:
        token = self.token_for_bot(bot)
        if token is None:
            return None
        for entry in self.entries.values():
            if entry.token == token and entry.status is BotStatus.LINKED and entry.chat_id == chat_id:
                return entry
        return None

    def has_pending_for_bot(self, bot: Bot) -> bool:
        token = self.token_for_bot(bot)
        if token is None:
            return False
        return any(entry.token == token and entry.status is BotStatus.PENDING for entry in self.entries.values())

    def entries_for_account(self, account_id: uuid.UUID) -> list[BotEntry]:
        return [
            entry
            for entry in self.entries.values()
            if entry.account_id == account_id and entry.status is BotStatus.LINKED and entry.chat_id
        ]

    def bots_for_polling(self) -> list[Bot]:
        return [self.clients[token] for token in self.pending_tokens() if token in self.clients]

    async def close(self) -> None:
        for bot in self.clients.values():
            await bot.session.close()
