import re
from datetime import UTC, datetime

import pytest
from dishka.integrations.fastapi import FastapiProvider
from httpx import ASGITransport, AsyncClient
from oopsys_server.configuration import Configuration
from oopsys_server.dependency_injection import build_container
from oopsys_server.infrastructure.security import generate_token
from oopsys_server.presentation.app import create_app

pytestmark = pytest.mark.asyncio

_CSRF_RE = re.compile(r'name="csrf-token" content="([^"]+)"')
_FIELD_RE = re.compile(r'name="csrf_token" value="([^"]+)"')


def _csrf(html: str) -> str:
    m = _CSRF_RE.search(html) or _FIELD_RE.search(html)
    return m.group(1) if m else ""


@pytest.fixture
async def client():
    import os

    os.environ["SECURITY__COOKIE_SECURE"] = "false"
    os.environ["NATS__ENABLED"] = "false"
    container = build_container(FastapiProvider())
    configuration = await container.get(Configuration)
    app = create_app(container, configuration)
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport, base_url="http://test", follow_redirects=False
    ) as c:
        yield c
    await container.close()


async def _make_account(login: str, password: str) -> None:
    from oopsys_server.application.accounts import AccountService
    from oopsys_server.infrastructure.persistence.engine import standalone_session
    from oopsys_server.infrastructure.persistence.repositories import (
        AccountRepository,
        SessionRepository,
    )
    from oopsys_server.infrastructure.security import PasswordHasher

    async with standalone_session() as session:
        service = AccountService(
            AccountRepository(session), SessionRepository(session), PasswordHasher()
        )
        await service.create(login=login, password=password)
        await session.commit()


async def test_login_required_redirects(client: AsyncClient) -> None:
    resp = await client.get("/")
    assert resp.status_code == 303
    assert resp.headers["location"] == "/login"


async def test_full_login_bind_ingest_flow(client: AsyncClient) -> None:
    login = f"web-{generate_token(4)[:8]}"
    password = "supersecret123"
    await _make_account(login, password)

    page = await client.get("/login")
    assert page.status_code == 200
    token = _csrf(page.text)
    assert token

    resp = await client.post(
        "/login", data={"csrf_token": token, "login": login, "password": password}
    )
    assert resp.status_code == 303, resp.text[:300]
    assert client.cookies.get("oopsys_session")

    agents_page = await client.get("/agents")
    token = _csrf(agents_page.text)
    raw_token = generate_token()
    resp = await client.post(
        "/agents/bind", data={"csrf_token": token, "token": raw_token, "label": "ci"}
    )
    assert resp.status_code == 303

    envelope = {
        "agent_id": "33333333-3333-3333-3333-333333333333",
        "source": "projects",
        "occurred_at": datetime.now(tz=UTC).isoformat(),
        "payload": {
            "severity": "critical",
            "service": "ci-svc",
            "environment": "production",
            "exception_type": "RuntimeError",
            "message": "ci boom",
            "traceback": "Traceback...\n  File 'a.py', line 1, in f",
            "timestamp": datetime.now(tz=UTC).isoformat(),
            "context": {},
        },
    }
    ok = await client.post(
        "/agents/ingest",
        json=envelope,
        headers={"Authorization": f"Bearer {raw_token}"},
    )
    assert ok.status_code == 202, ok.text

    bad = await client.post(
        "/agents/ingest", json=envelope, headers={"Authorization": "Bearer nope"}
    )
    assert bad.status_code == 401

    unbound = generate_token()
    not_bound = await client.post(
        "/agents/ingest", json=envelope, headers={"Authorization": f"Bearer {unbound}"}
    )
    assert not_bound.status_code == 401

    errors_page = await client.get("/errors")
    assert errors_page.status_code == 200
    assert "RuntimeError" in errors_page.text


async def test_csrf_rejected_without_token(client: AsyncClient) -> None:
    resp = await client.post("/login", data={"login": "x", "password": "y"})
    assert resp.status_code == 403


async def test_pages_render_after_login(client: AsyncClient) -> None:
    login = f"web-{generate_token(4)[:8]}"
    password = "supersecret123"
    await _make_account(login, password)
    page = await client.get("/login")
    token = _csrf(page.text)
    await client.post(
        "/login", data={"csrf_token": token, "login": login, "password": password}
    )

    for path in (
        "/",
        "/agents",
        "/servers",
        "/projects",
        "/errors",
        "/containers",
        "/bots",
        "/system",
        "/settings",
    ):
        resp = await client.get(path)
        assert resp.status_code == 200, (path, resp.status_code)
