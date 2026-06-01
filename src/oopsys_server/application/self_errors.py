import hashlib
import traceback as tb_module

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from structlog import getLogger

from oopsys_server.application.notifications import NotificationService
from oopsys_server.configuration import Loggers
from oopsys_server.domain.enums import NotificationKind, Severity
from oopsys_server.domain.fingerprint import normalize_message
from oopsys_server.infrastructure.nats import NotificationGateway
from oopsys_server.infrastructure.persistence.repositories import (
    AccountRepository,
    NotificationRepository,
    SelfErrorRepository,
)
from oopsys_server.infrastructure.realtime import RealtimeHub

logger = getLogger(Loggers.main.name)


class SelfErrorReporter:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        gateway: NotificationGateway,
        hub: RealtimeHub,
    ) -> None:
        self._session_factory = session_factory
        self._gateway = gateway
        self._hub = hub

    async def capture(self, exc: BaseException, *, component: str, context: dict | None = None) -> None:
        exception_type = type(exc).__name__
        message = str(exc) or exception_type
        traceback = "".join(tb_module.format_exception(type(exc), exc, exc.__traceback__))
        fingerprint = hashlib.sha256(f"{component}|{exception_type}|{normalize_message(message)}".encode()).hexdigest()
        try:
            async with self._session_factory() as session:
                _, is_new = await SelfErrorRepository(session).record(
                    component=component,
                    exception_type=exception_type,
                    message=message,
                    traceback=traceback,
                    fingerprint=fingerprint,
                    context=context or {},
                )
                if is_new:
                    accounts = await AccountRepository(session).list_all()
                    account_ids = [account.id for account in accounts if account.is_active]
                    if account_ids:
                        notifications = NotificationService(NotificationRepository(session), self._gateway, self._hub)
                        await notifications.emit(
                            account_ids,
                            kind=NotificationKind.SERVER_ERROR,
                            severity=Severity.CRITICAL,
                            title=f"Ошибка сервера: {component}",
                            body=f"{exception_type}: {message}"[:240],
                            ref={"component": component, "fingerprint": fingerprint},
                        )
                await session.commit()
        except Exception as inner:
            await logger.aerror("failed to record self error", error=str(inner))
