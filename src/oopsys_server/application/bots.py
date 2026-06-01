import secrets
import uuid

from oopsys_server.domain.enums import BotStatus
from oopsys_server.infrastructure.persistence.models import Bot
from oopsys_server.infrastructure.persistence.repositories import BotRepository
from oopsys_server.infrastructure.security import TokenCipher
from oopsys_server.infrastructure.telegram import fetch_bot_username


class BotService:
    def __init__(self, bots: BotRepository, cipher: TokenCipher) -> None:
        self._bots = bots
        self._cipher = cipher

    async def register(self, account_id: uuid.UUID, raw_bot_token: str) -> Bot:
        token = raw_bot_token.strip()
        invite_key = secrets.token_urlsafe(16)
        username = await fetch_bot_username(token)
        return await self._bots.add(
            Bot(
                account_id=account_id,
                bot_token_encrypted=self._cipher.encrypt(token),
                invite_key=invite_key,
                bot_username=username,
                status=BotStatus.PENDING,
            )
        )

    async def list_for_account(self, account_id: uuid.UUID) -> list[Bot]:
        return await self._bots.list_for_account(account_id)

    async def ensure_usernames(self, account_id: uuid.UUID) -> bool:
        updated = False
        for bot in await self._bots.list_for_account(account_id):
            if bot.bot_username:
                continue
            token = self.decrypt_token(bot)
            if not token:
                continue
            username = await fetch_bot_username(token)
            if username:
                bot.bot_username = username
                updated = True
        return updated

    async def link_by_invite(self, invite_key: str, chat_id: str, bot_username: str | None = None) -> Bot | None:
        bot = await self._bots.get_by_invite(invite_key)
        if bot is None:
            return None
        bot.chat_id = chat_id
        bot.status = BotStatus.LINKED
        if bot_username:
            bot.bot_username = bot_username
        return bot

    async def delete(self, account_id: uuid.UUID, bot_id: uuid.UUID) -> bool:
        bot = await self._bots.get(bot_id)
        if bot is None or bot.account_id != account_id:
            return False
        await self._bots.delete(bot)
        return True

    def decrypt_token(self, bot: Bot) -> str | None:
        return self._cipher.decrypt(bot.bot_token_encrypted)
