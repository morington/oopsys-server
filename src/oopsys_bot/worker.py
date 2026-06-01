import asyncio
import contextlib

from aiogram import Bot, Dispatcher
from aiogram.filters import CommandObject, CommandStart
from aiogram.types import Message
from faststream.nats import NatsBroker
from faststream.nats.annotations import NatsMessage
from structlog import getLogger

from oopsys_bot.registry import BotRegistry
from oopsys_server.configuration import Configuration, Loggers
from oopsys_server.infrastructure.persistence.engine import standalone_session
from oopsys_server.infrastructure.persistence.repositories import BotRepository
from oopsys_server.infrastructure.security import TokenCipher

logger = getLogger(Loggers.notifier.name)

class BotWorker:

    def __init__(self, configuration: Configuration) -> None:
        self._cfg = configuration
        self._registry = BotRegistry(cipher=TokenCipher(configuration.security.bot_token_key))
        self._broker = NatsBroker(configuration.nats.servers)
        self._dispatcher = Dispatcher()
        self._polling_task: asyncio.Task | None = None
        self._polling_tokens: frozenset[str] = frozenset()
        self._register_handlers()

    def _register_handlers(self) -> None:

        @self._dispatcher.message(CommandStart(deep_link=True))
        async def on_start(message: Message, command: CommandObject) -> None:
            invite_key = (command.args or "").strip()
            chat_id = str(message.chat.id)
            username = (await message.bot.me()).username if message.bot else None
            async with standalone_session() as session:
                repo = BotRepository(session)
                bot = await repo.get_by_invite(invite_key)
                if bot is None:
                    await message.answer("Неверный или просроченный ключ привязки.")
                    return
                from oopsys_server.application.bots import BotService
                service = BotService(repo, self._registry.cipher)
                await service.link_by_invite(invite_key, chat_id, bot_username=username)
                await session.commit()
            await message.answer("Бот привязан. Важные уведомления будут приходить в этот чат.")
            await self._registry.reload()
        notify_subject = f"{self._cfg.nats.subject_prefix}.notify.>"

        @self._broker.subscriber(notify_subject, stream=self._cfg.nats.stream, durable="oopsys-bot")
        async def on_notify(body: dict, msg: NatsMessage) -> None:
            subject = msg.raw_message.subject
            account_id = subject.rsplit(".", 1)[-1]
            await self._dispatch_notification(account_id, body)

    async def _dispatch_notification(self, account_id: str, body: dict) -> None:
        import uuid
        try:
            account_uuid = uuid.UUID(account_id)
        except ValueError:
            return
        text = self._format(body)
        for entry in self._registry.entries_for_account(account_uuid):
            with contextlib.suppress(Exception):
                await entry.bot.send_message(entry.chat_id, text)

    @staticmethod
    def _format(body: dict) -> str:
        severity = body.get("severity", "error").upper()
        title = body.get("title", "Уведомление")
        detail = body.get("body", "")
        return f"[{severity}] {title}\n{detail}".strip()

    async def _reconcile_polling(self) -> None:
        while True:
            await self._registry.reload()
            tokens = frozenset(self._registry.by_token)
            if tokens != self._polling_tokens:
                await self._restart_polling(tokens)
            await asyncio.sleep(self._cfg.liveness.scan_interval_seconds)

    async def _restart_polling(self, tokens: frozenset[str]) -> None:
        if self._polling_task is not None:
            self._polling_task.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await self._polling_task
        self._polling_tokens = tokens
        bots: list[Bot] = self._registry.bots()
        if not bots:
            self._polling_task = None
            return
        self._polling_task = asyncio.create_task(self._dispatcher.start_polling(*bots, handle_signals=False), name="oopsys-bot-polling")
        await logger.ainfo("bot polling (re)started", count=len(bots))

    async def run(self) -> None:
        await self._broker.connect()
        await self._broker.start()
        await self._registry.reload()
        await self._restart_polling(frozenset(self._registry.by_token))
        await logger.ainfo("bot worker ready")
        try:
            await self._reconcile_polling()
        finally:
            if self._polling_task is not None:
                self._polling_task.cancel()
            await self._broker.stop()
            await self._registry.close()
