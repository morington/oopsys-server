import secrets
import uuid

from oopsys_server.domain.enums import BotStatus
from oopsys_server.infrastructure.persistence.models import Bot
from oopsys_server.infrastructure.persistence.repositories import BotRepository
from oopsys_server.infrastructure.security import TokenCipher


class BotService:

    def __init__(self, bots: BotRepository, cipher: TokenCipher) -> None:
        self._bots = bots
        self._cipher = cipher

    async def register(self, account_id: uuid.UUID, raw_bot_token: str) -> Bot:
        invite_key = secrets.token_urlsafe(16)
        return await self._bots.add(Bot(account_id=account_id, bot_token_encrypted=self._cipher.encrypt(raw_bot_token.strip()), invite_key=invite_key, status=BotStatus.PENDING))

    async def list_for_account(self, account_id: uuid.UUID) -> list[Bot]:
        return await self._bots.list_for_account(account_id)

    async def link_by_invite(self, invite_key: str, chat_id: str, bot_username: str | None=None) -> Bot | None:
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
