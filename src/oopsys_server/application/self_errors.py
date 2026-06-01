import hashlib
import traceback as tb_module

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from structlog import getLogger

from oopsys_server.configuration import Loggers
from oopsys_server.domain.fingerprint import normalize_message
from oopsys_server.infrastructure.persistence.repositories import SelfErrorRepository

logger = getLogger(Loggers.main.name)

class SelfErrorReporter:

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def capture(self, exc: BaseException, *, component: str, context: dict | None=None) -> None:
        exception_type = type(exc).__name__
        message = str(exc) or exception_type
        traceback = "".join(tb_module.format_exception(type(exc), exc, exc.__traceback__))
        fingerprint = hashlib.sha256(f"{component}|{exception_type}|{normalize_message(message)}".encode()).hexdigest()
        try:
            async with self._session_factory() as session:
                await SelfErrorRepository(session).record(component=component, exception_type=exception_type, message=message, traceback=traceback, fingerprint=fingerprint, context=context or {})
                await session.commit()
        except Exception as inner:
            await logger.aerror("failed to record self error", error=str(inner))
