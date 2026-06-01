from urllib.parse import parse_qs

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import PlainTextResponse, Response
from starlette.types import ASGIApp, Receive, Scope, Send

from oopsys_server.presentation.web.csrf import CSRF_COOKIE, CSRF_FIELD, CSRF_HEADER, CsrfProtection

_CSP = "default-src 'self'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'; object-src 'none'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; script-src 'self'; connect-src 'self'"
_SAFE_METHODS = {"GET", "HEAD", "OPTIONS", "TRACE"}
_CSRF_EXEMPT = {"/agents/ingest"}

class SecurityHeadersMiddleware(BaseHTTPMiddleware):

    def __init__(self, app: ASGIApp, *, csrf: CsrfProtection, cookie_secure: bool) -> None:
        super().__init__(app)
        self._csrf = csrf
        self._cookie_secure = cookie_secure

    async def dispatch(self, request: Request, call_next) -> Response:
        existing_cookie = request.cookies.get(CSRF_COOKIE)
        if existing_cookie is None:
            cookie_value, raw = self._csrf.issue()
        else:
            cookie_value, raw = (None, self._csrf.unsign(existing_cookie))
        request.state.csrf_value = raw or ""
        response = await call_next(request)
        response.headers.setdefault("Content-Security-Policy", _CSP)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault("Cross-Origin-Opener-Policy", "same-origin")
        if self._cookie_secure:
            response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
        if cookie_value is not None:
            response.set_cookie(CSRF_COOKIE, cookie_value, httponly=False, secure=self._cookie_secure, samesite="lax", path="/")
        return response

def _cookie_from_scope(scope: Scope, name: str) -> str | None:
    for key, value in scope.get("headers", ()):
        if key == b"cookie":
            for pair in value.decode("latin-1").split(";"):
                if "=" in pair:
                    k, v = pair.split("=", 1)
                    if k.strip() == name:
                        return v.strip()
    return None

class CsrfMiddleware:

    def __init__(self, app: ASGIApp, *, csrf: CsrfProtection) -> None:
        self._app = app
        self._csrf = csrf

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope["method"] in _SAFE_METHODS or scope["path"] in _CSRF_EXEMPT:
            await self._app(scope, receive, send)
            return
        body = b""
        more_body = True
        while more_body:
            message = await receive()
            if message["type"] != "http.request":
                break
            body += message.get("body", b"")
            more_body = message.get("more_body", False)
        headers = dict(scope.get("headers", ()))
        submitted = (headers.get(CSRF_HEADER.lower().encode(), b"") or b"").decode("latin-1") or None
        content_type = headers.get(b"content-type", b"").decode("latin-1")
        if submitted is None and content_type.startswith("application/x-www-form-urlencoded"):
            parsed = parse_qs(body.decode("utf-8", "ignore"))
            values = parsed.get(CSRF_FIELD)
            submitted = values[0] if values else None
        cookie = _cookie_from_scope(scope, CSRF_COOKIE)
        if not self._csrf.validate(cookie, submitted):
            await PlainTextResponse("CSRF validation failed", status_code=403)(scope, receive, send)
            return
        replayed = False

        async def replay_receive():
            nonlocal replayed
            if not replayed:
                replayed = True
                return {"type": "http.request", "body": body, "more_body": False}
            return await receive()
        await self._app(scope, replay_receive, send)
