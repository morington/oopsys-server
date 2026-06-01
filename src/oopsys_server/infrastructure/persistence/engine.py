from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from oopsys_server.configuration import Configuration


@asynccontextmanager
async def standalone_session(configuration: Configuration | None=None) -> AsyncIterator[AsyncSession]:
    configuration = configuration or Configuration()
    engine = create_async_engine(configuration.postgresql.url(), connect_args={"ssl": "disable"})
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with factory() as session:
            yield session
    finally:
        await engine.dispose()
