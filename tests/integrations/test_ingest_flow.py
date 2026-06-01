from datetime import UTC, datetime

import pytest
from dishka import Scope

from oopsys_server.application.accounts import AccountService
from oopsys_server.application.ingest import IngestService
from oopsys_server.application.tokens import AgentTokenService
from oopsys_server.domain.enums import Source
from oopsys_server.domain.envelope import Envelope
from oopsys_server.infrastructure.persistence.repositories import (
    AgentRepository,
    ContainerRepository,
    ErrorRepository,
    MetricsRepository,
)
from oopsys_server.infrastructure.security import generate_token

pytestmark = pytest.mark.asyncio

AGENT_ID = "11111111-1111-1111-1111-111111111111"


def _error_envelope(message: str) -> Envelope:
    return Envelope(
        agent_id=AGENT_ID,
        source=Source.PROJECTS,
        occurred_at=datetime.now(tz=UTC),
        payload={
            "severity": "error",
            "service": "cryptobot",
            "environment": "production",
            "exception_type": "ValueError",
            "message": message,
            "traceback": "Traceback...\n  File 'x.py', line 1, in f",
            "timestamp": datetime.now(tz=UTC).isoformat(),
            "context": {},
        },
    )


async def _bind(container, raw_token: str) -> None:
    async with container(scope=Scope.REQUEST) as request:
        account_service = await request.get(AccountService)
        token_service = await request.get(AgentTokenService)
        from sqlalchemy.ext.asyncio import AsyncSession

        session = await request.get(AsyncSession)
        created = await account_service.create(login=f"acc-{raw_token[:6]}")
        await token_service.bind(created.account_id, raw_token, label="test")
        await session.commit()


async def test_ingest_error_creates_group(container) -> None:
    raw_token = generate_token()
    await _bind(container, raw_token)

    async with container(scope=Scope.REQUEST) as request:
        from sqlalchemy.ext.asyncio import AsyncSession

        session = await request.get(AsyncSession)
        token_service = await request.get(AgentTokenService)
        ingest = await request.get(IngestService)

        token = await token_service.authenticate(raw_token)
        assert token is not None
        await token_service.link_agent(token, AGENT_ID)

        await ingest.handle(_error_envelope("boom 42"))
        await ingest.handle(_error_envelope("boom 99"))
        await session.commit()

        errors = ErrorRepository(session)
        groups = await errors.list_groups(agent_ids=[AGENT_ID])
        assert len(groups) == 1
        assert groups[0].count == 2

        agents = AgentRepository(session)
        agent = await agents.get(AGENT_ID)
        assert agent is not None


async def test_ingest_metric_and_container(container) -> None:
    raw_token = generate_token()
    await _bind(container, raw_token)

    async with container(scope=Scope.REQUEST) as request:
        from sqlalchemy.ext.asyncio import AsyncSession

        session = await request.get(AsyncSession)
        ingest = await request.get(IngestService)

        await ingest.handle(
            Envelope(
                agent_id=AGENT_ID,
                source=Source.SERVER,
                occurred_at=datetime.now(tz=UTC),
                payload={
                    "cpu_percent": 12.5,
                    "mem_percent": 40.0,
                    "mem_used": 100,
                    "mem_total": 200,
                    "net_bytes_sent": 1,
                    "net_bytes_recv": 2,
                    "load_1": 0.5,
                    "load_5": 0.4,
                    "load_15": 0.3,
                    "disk_percent": 50.0,
                    "captured_at": datetime.now(tz=UTC).isoformat(),
                },
            )
        )
        await ingest.handle(
            Envelope(
                agent_id=AGENT_ID,
                source=Source.DOCKER,
                occurred_at=datetime.now(tz=UTC),
                payload={
                    "container_id": "abc123",
                    "name": "web",
                    "image": "nginx",
                    "status": "running",
                    "labels": {"com.docker.compose.service": "web"},
                    "captured_at": datetime.now(tz=UTC).isoformat(),
                },
            )
        )
        await session.commit()

        metrics = MetricsRepository(session)
        latest = await metrics.latest(AGENT_ID)
        assert latest is not None
        assert latest.cpu_percent == 12.5

        containers = ContainerRepository(session)
        rows = await containers.list_for_agents([AGENT_ID])
        assert len(rows) == 1
        assert rows[0].name == "web"
