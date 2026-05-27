import time
from collections.abc import AsyncIterable
from typing import Any

import structlog
from dishka import Provider, Scope, provide
from sqlalchemy import Connection, event, text
from sqlalchemy.engine.url import URL
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from oopsys_server.configuration import Configuration, Loggers

logger = structlog.getLogger(Loggers.providers.name)


async def _check_read_write(engine: AsyncEngine) -> bool:
    try:
        async with engine.connect() as conn:
            result = await conn.execute(text("SHOW transaction_read_only"))
            return result.scalar() == "off"
    except SQLAlchemyError as exc:
        await logger.awarning("Failed to check read-write mode", error=str(exc))
        return False


def before_cursor_execute(
    conn: Connection,
    cursor: Any,
    statement: str,
    parameters: Any,
    context: Any,
    executemany: bool,  # noqa: FBT001
) -> None:
    conn.info["query_start_time"] = time.perf_counter()


def set_query_log(duration: float) -> None:
    logger.debug("SQL Query complete", duration=round(duration, 6))


def after_cursor_execute(
    conn: Connection,
    cursor: Any,
    statement: str,
    parameters: Any,
    context: Any,
    executemany: bool,  # noqa: FBT001
) -> None:
    start = conn.info.pop("query_start_time", None)
    if start is None:
        return
    _duration = time.perf_counter() - start


async def _create_engine(url: str | URL, ssl: str) -> AsyncEngine | None:
    engine = create_async_engine(
        url,
        pool_size=10,
        max_overflow=5,
        pool_recycle=300,
        pool_pre_ping=True,
        pool_timeout=30,
        connect_args={"ssl": ssl},
    )
    event.listen(engine.sync_engine, "before_cursor_execute", before_cursor_execute)
    event.listen(engine.sync_engine, "after_cursor_execute", after_cursor_execute)

    if await _check_read_write(engine):
        return engine

    await engine.dispose()
    return None


async def get_engine(url: str | URL, ssl: str = "disable") -> AsyncEngine:
    engine = await _create_engine(url, ssl)
    if engine:
        return engine

    raise ConnectionError("Could not connect to read-write PostgreSQL host")


class ConnectionProvider(Provider):
    scope = Scope.APP

    @provide
    async def engine(self, configuration: Configuration) -> AsyncIterable[AsyncEngine]:
        await logger.adebug("Create PostgreSQL URL", url=configuration.postgresql.safe_url())

        engine = await get_engine(configuration.postgresql.url())
        yield engine
        await engine.dispose()

    @provide(scope=Scope.APP)
    async def session_factory(
        self,
        engine: AsyncEngine,
    ) -> async_sessionmaker[AsyncSession]:
        return async_sessionmaker(engine, expire_on_commit=False)

    @provide(scope=Scope.REQUEST)
    async def session(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> AsyncIterable[AsyncSession]:
        async with session_factory() as session:
            yield session
