from dishka.integrations.fastapi import DishkaRoute, FromDishka
from fastapi import APIRouter, Form, Request
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import RedirectResponse, Response

from oopsys_server.application.auth import AuthService, AuthStatus
from oopsys_server.configuration import Configuration
from oopsys_server.infrastructure.security.captcha import generate_captcha, verify_captcha
from oopsys_server.presentation.web.deps import load_account
from oopsys_server.presentation.web.templating import render

router = APIRouter(route_class=DishkaRoute, tags=["web-auth"])

def _client_ip(request: Request) -> str:
    return request.headers.get("X-Forwarded-For", request.client.host if request.client else "?").split(",")[0].strip()

def _render_login(request: Request, *, error: str | None=None, login_value: str="", force_captcha: bool=False):
    ip = _client_ip(request)
    guard = request.app.state.login_guard
    captcha_required = force_captcha or guard.needs_captcha(ip)
    ctx = {"error": error, "login_value": login_value, "captcha_required": captcha_required}
    if captcha_required:
        challenge = generate_captcha()
        captcha_id = request.app.state.captcha_store.put(challenge.answer_hash)
        ctx["captcha_data_uri"] = challenge.data_uri
        ctx["captcha_id"] = captcha_id
    return render(request, "login.html", ctx)

@router.get("/login")
async def login_form(request: Request) -> Response:
    if await load_account(request) is not None:
        return RedirectResponse("/", status_code=303)
    return _render_login(request)

@router.post("/login")
async def login_submit(request: Request, auth: FromDishka[AuthService], configuration: FromDishka[Configuration], session: FromDishka[AsyncSession], login: str=Form(...), password: str=Form(...), remember: str | None=Form(None), captcha: str | None=Form(None), captcha_id: str | None=Form(None)) -> Response:
    ip = _client_ip(request)
    guard = request.app.state.login_guard
    if guard.needs_captcha(ip):
        expected = request.app.state.captcha_store.take(captcha_id or "")
        if expected is None or not verify_captcha(expected, captcha or ""):
            return _render_login(request, error="Неверная капча", login_value=login, force_captcha=True)
    result = await auth.authenticate(login, password)
    await session.commit()
    if result.status is AuthStatus.OK and result.account is not None:
        issued = await auth.issue_session(result.account, remember=bool(remember), ip=ip, user_agent=request.headers.get("User-Agent"))
        await session.commit()
        guard.reset(ip)
        target = "/settings" if result.account.must_change_password else "/"
        response = RedirectResponse(target, status_code=303)
        max_age = configuration.security.remember_ttl_seconds if remember else configuration.security.session_ttl_seconds
        response.set_cookie(configuration.security.cookie_name, issued.raw_token, max_age=max_age if remember else None, httponly=True, secure=configuration.security.cookie_secure, samesite="lax", path="/")
        return response
    guard.record_failure(ip)
    if result.status is AuthStatus.LOCKED:
        return _render_login(request, error=f"Слишком много попыток. Повторите через {result.retry_after} с.", login_value=login)
    return _render_login(request, error="Неверный логин или пароль", login_value=login)

@router.post("/logout")
async def logout(request: Request, auth: FromDishka[AuthService], configuration: FromDishka[Configuration], session: FromDishka[AsyncSession]) -> Response:
    token = request.cookies.get(configuration.security.cookie_name)
    if token:
        await auth.revoke_session(token)
        await session.commit()
    response = RedirectResponse("/login", status_code=303)
    response.delete_cookie(configuration.security.cookie_name, path="/")
    return response
