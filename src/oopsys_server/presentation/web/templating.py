from pathlib import Path
from typing import Any

from fastapi import Request
from fastapi.templating import Jinja2Templates
from starlette.responses import HTMLResponse

from oopsys_server.presentation.web.csrf import CSRF_COOKIE, CsrfProtection

_TEMPLATES_DIR = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))

def _csrf_token(request: Request) -> str:
    cached = getattr(request.state, "csrf_value", None)
    if cached:
        return cached
    csrf: CsrfProtection | None = getattr(request.app.state, "csrf", None)
    if csrf is None:
        return ""
    return csrf.unsign(request.cookies.get(CSRF_COOKIE)) or ""

def render(request: Request, template: str, context: dict[str, Any] | None=None, *, status_code: int=200) -> HTMLResponse:
    account = getattr(request.state, "account", None)
    merged: dict[str, Any] = {"request": request, "account": account, "csrf_token": _csrf_token(request), "active": ""}
    if context:
        merged.update(context)
    return templates.TemplateResponse(request, template, merged, status_code=status_code)
