from fastapi import HTTPException, Request, status

from oopsys_server.application.auth import AuthService
from oopsys_server.infrastructure.persistence.models import Account


async def load_account(request: Request) -> Account | None:
    cached = getattr(request.state, "account", None)
    if cached is not None:
        return cached
    cookie_name = request.app.state.cookie_name
    token = request.cookies.get(cookie_name)
    if not token:
        return None
    container = request.state.dishka_container
    auth = await container.get(AuthService)
    account = await auth.resolve_session(token)
    request.state.account = account
    return account

async def require_account(request: Request) -> Account:
    account = await load_account(request)
    if account is None:
        headers = {"Location": "/login"}
        if request.headers.get("HX-Request"):
            headers["HX-Redirect"] = "/login"
        raise HTTPException(status_code=status.HTTP_303_SEE_OTHER, headers=headers)
    return account
