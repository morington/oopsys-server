from dishka.integrations.fastapi import DishkaRoute, FromDishka
from fastapi import APIRouter, Depends, Form, Request
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import Response

from oopsys_server.application.accounts import AccountService, LoginTakenError
from oopsys_server.infrastructure.persistence.models import Account
from oopsys_server.presentation.web.deps import require_account
from oopsys_server.presentation.web.templating import render

router = APIRouter(route_class=DishkaRoute, tags=["web-settings"])
_MIN_PASSWORD = 10

@router.get("/settings")
async def settings_page(request: Request, account: Account=Depends(require_account)) -> Response:
    return render(request, "settings.html", {"active": "settings"})

@router.post("/settings")
async def update_settings(request: Request, account_service: FromDishka[AccountService], session: FromDishka[AsyncSession], new_login: str=Form(""), current_password: str=Form(""), new_password: str=Form(""), confirm_password: str=Form(""), account: Account=Depends(require_account)) -> Response:
    from oopsys_server.infrastructure.security import PasswordHasher
    error: str | None = None
    ok: str | None = None
    hasher = PasswordHasher()
    if new_password:
        if not hasher.verify(account.password_hash, current_password):
            error = "Текущий пароль неверен"
        elif len(new_password) < _MIN_PASSWORD:
            error = f"Пароль должен быть не короче {_MIN_PASSWORD} символов"
        elif new_password != confirm_password:
            error = "Пароли не совпадают"
    if error is None:
        try:
            await account_service.change_credentials(account, new_login=new_login.strip() or None, new_password=new_password or None)
            await session.commit()
            ok = "Настройки сохранены"
        except LoginTakenError:
            error = "Такой логин уже занят"
    return render(request, "settings.html", {"active": "settings", "error": error, "ok": ok})
