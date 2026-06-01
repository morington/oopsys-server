import os

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from oopsys_server.dependency_injection import build_container
from oopsys_server.infrastructure.persistence import Base

os.environ.setdefault("POSTGRESQL__HOST", "localhost")
os.environ.setdefault("POSTGRESQL__PORT", "55432")
os.environ.setdefault("NATS__ENABLED", "false")
os.environ.setdefault("SECURITY__COOKIE_SECURE", "false")


@pytest_asyncio.fixture(autouse=True)
async def _clean_db():
    from oopsys_server.configuration import Configuration

    engine = create_async_engine(Configuration().postgresql.url(), connect_args={"ssl": "disable"})
    tables = ", ".join(t.name for t in Base.metadata.sorted_tables)
    async with engine.begin() as conn:
        await conn.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))
    await engine.dispose()
    yield


@pytest_asyncio.fixture
async def container():
    container = build_container()
    yield container
    await container.close()


@pytest_asyncio.fixture
async def session_factory(container) -> async_sessionmaker[AsyncSession]:
    return await container.get(async_sessionmaker[AsyncSession])


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"
