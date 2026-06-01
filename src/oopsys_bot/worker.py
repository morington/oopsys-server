import asyncio
import contextlib

from aiogram import Bot, Dispatcher
from aiogram.filters import CommandObject, CommandStart
from aiogram.types import Message
from faststream.nats import NatsBroker, PullSub
from faststream.nats.annotations import NatsMessage
from structlog import getLogger

from oopsys_bot.registry import BotRegistry
from oopsys_server.application.bot_notify import bot_accepts_notification
from oopsys_server.application.bots import BotService
from oopsys_server.configuration import Configuration, Loggers
from oopsys_server.domain.enums import BotStatus
from oopsys_server.infrastructure.persistence.engine import standalone_session
from oopsys_server.infrastructure.persistence.repositories import BotRepository
from oopsys_server.infrastructure.security import TokenCipher

logger = getLogger(Loggers.notifier.name)

_POLL_RECONCILE_SECONDS = 60

_LINK_PROMPT = (
    "Отправьте код привязки из раздела «Боты» в личном кабинете oopsys.\n"
    "Можно просто вставить код следующим сообщением."
)
_LINKED_ACK = "Бот уже подключён. Уведомления oopsys приходят в этот чат автоматически."
_LINK_OK = "Готово! Уведомления oopsys будут приходить в этот чат."


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

        @self._dispatcher.message(CommandStart())
        async def on_start(message: Message, command: CommandObject) -> None:
            if message.bot is None:
                return
            invite_key = (command.args or "").strip()
            if invite_key:
                await self._try_link(message, invite_key)
                return
            chat_id = str(message.chat.id)
            if self._registry.linked_entry_for_chat(message.bot, chat_id):
                await message.answer(_LINKED_ACK)
            elif self._registry.has_pending_for_bot(message.bot):
                await message.answer(_LINK_PROMPT)

        @self._dispatcher.message()
        async def on_message(message: Message) -> None:
            if message.bot is None or not message.text or message.text.startswith("/"):
                return
            chat_id = str(message.chat.id)
            if self._registry.linked_entry_for_chat(message.bot, chat_id):
                return
            if self._registry.has_pending_for_bot(message.bot):
                await self._try_link(message, message.text.strip())

        notify_subject = f"{self._cfg.nats.subject_prefix}.notify.>"

        @self._broker.subscriber(
            notify_subject,
            stream=self._cfg.nats.stream,
            durable="oopsys-bot",
            pull_sub=PullSub(batch_size=10, timeout=5.0),
        )
        async def on_notify(body: dict, msg: NatsMessage) -> None:
            subject = msg.raw_message.subject
            account_id = subject.rsplit(".", 1)[-1]
            await self._dispatch_notification(account_id, body)

    async def _try_link(self, message: Message, invite_key: str) -> None:
        if not invite_key or message.bot is None:
            return
        chat_id = str(message.chat.id)
        token = self._registry.token_for_bot(message.bot)
        if token is None:
            return

        async with standalone_session() as session:
            repo = BotRepository(session)
            service = BotService(repo, self._registry.cipher)
            row = await repo.get_by_invite(invite_key)
            if row is None:
                await message.answer("Неверный код привязки. Скопируйте код из раздела «Боты» в личном кабинете.")
                return
            row_token = service.decrypt_token(row)
            if row_token != token:
                await message.answer("Этот код не подходит к этому боту.")
                return
            if row.status is BotStatus.LINKED and row.chat_id == chat_id:
                await message.answer(_LINKED_ACK)
                return
            username = (await message.bot.me()).username if message.bot else None
            await service.link_by_invite(invite_key, chat_id, bot_username=username)
            await session.commit()

        await message.answer(_LINK_OK)
        pending = await self._registry.reload()
        await self._restart_polling(pending)

    async def _dispatch_notification(self, account_id: str, body: dict) -> None:
        import uuid

        try:
            account_uuid = uuid.UUID(account_id)
        except ValueError:
            await logger.awarning("bot notification skipped", account_id=account_id, reason="invalid account id")
            return

        await self._registry.reload()
        entries = self._registry.entries_for_account(account_uuid)
        if not entries:
            await logger.awarning(
                "bot notification skipped",
                account_id=account_id,
                title=body.get("title"),
                reason="no linked bot for account",
            )
            return

        text = self._format(body)
        for entry in entries:
            if not bot_accepts_notification(entry.notify_kinds, body):
                await logger.ainfo(
                    "telegram notification skipped",
                    account_id=account_id,
                    chat_id=entry.chat_id,
                    title=body.get("title"),
                    reason="disabled in bot settings",
                )
                continue
            try:
                client = self._registry.client_for(entry.token)
                await client.send_message(entry.chat_id, text)
                await logger.ainfo(
                    "telegram notification sent",
                    account_id=account_id,
                    chat_id=entry.chat_id,
                    title=body.get("title"),
                )
            except Exception as exc:
                await logger.aerror(
                    "telegram send failed",
                    account_id=account_id,
                    chat_id=entry.chat_id,
                    title=body.get("title"),
                    reason=str(exc),
                )

    @staticmethod
    def _format(body: dict) -> str:
        severity = body.get("severity", "error").upper()
        title = body.get("title", "Уведомление")
        detail = body.get("body", "")
        return f"[{severity}] {title}\n{detail}".strip()

    async def _reconcile_polling(self) -> None:
        while True:
            pending = await self._registry.reload()
            if pending != self._polling_tokens:
                await self._restart_polling(pending)
            await asyncio.sleep(_POLL_RECONCILE_SECONDS)

    async def _stop_polling(self) -> None:
        if self._polling_task is None:
            return
        await self._dispatcher.stop_polling()
        with contextlib.suppress(asyncio.CancelledError, Exception):
            await self._polling_task
        self._polling_task = None

    async def _restart_polling(self, tokens: frozenset[str]) -> None:
        await self._stop_polling()
        self._polling_tokens = tokens
        bots: list[Bot] = self._registry.bots_for_polling()
        if not bots:
            await logger.ainfo("bot polling stopped", reason="no pending bots")
            return
        self._polling_task = asyncio.create_task(
            self._dispatcher.start_polling(*bots, handle_signals=False),
            name="oopsys-bot-polling",
        )
        await logger.ainfo("bot polling started", count=len(bots))

    async def run(self) -> None:
        await self._broker.connect()
        await self._broker.start()
        pending = await self._registry.reload()
        await self._restart_polling(pending)
        await logger.ainfo("bot worker ready", pending_bots=len(pending))
        try:
            await self._reconcile_polling()
        finally:
            await self._stop_polling()
            await self._broker.stop()
            await self._registry.close()
