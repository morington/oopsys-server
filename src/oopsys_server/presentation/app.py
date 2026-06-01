from contextlib import asynccontextmanager
from pathlib import Path

from dishka import AsyncContainer
from dishka.integrations.fastapi import setup_dishka
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from starlette.responses import JSONResponse, Response
from structlog import getLogger

from oopsys_server.application.liveness import LivenessMonitor
from oopsys_server.application.self_errors import SelfErrorReporter
from oopsys_server.configuration import Configuration, Loggers
from oopsys_server.infrastructure.nats import NotificationGateway
from oopsys_server.presentation.api import ingest_router
from oopsys_server.presentation.web.csrf import CsrfProtection
from oopsys_server.presentation.web.middleware import CsrfMiddleware, SecurityHeadersMiddleware
from oopsys_server.presentation.web.routes import include_web_routers
from oopsys_server.presentation.web.state import CaptchaStore, LoginGuard

logger = getLogger(Loggers.main.name)
_STATIC_DIR = Path(__file__).parent / "web" / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    container: AsyncContainer = app.state.dishka_container
    gateway = await container.get(NotificationGateway)
    monitor = await container.get(LivenessMonitor)
    await gateway.start()
    await monitor.start()
    await logger.ainfo("oopsys-server ready")
    try:
        yield
    finally:
        await monitor.stop()
        await gateway.close()
        await container.close()
        await logger.awarning("oopsys-server shut down")


def create_app(container: AsyncContainer, configuration: Configuration) -> FastAPI:
    docs_kwargs = {} if configuration.is_development else {"docs_url": None, "redoc_url": None, "openapi_url": None}
    app = FastAPI(lifespan=lifespan, title="oopsys-server", **docs_kwargs)
    csrf = CsrfProtection(configuration.security.secret_key)
    app.state.csrf = csrf
    app.state.cookie_name = configuration.security.cookie_name
    app.state.cookie_secure = configuration.security.cookie_secure
    app.state.captcha_store = CaptchaStore()
    app.state.login_guard = LoginGuard(captcha_after=configuration.security.captcha_after_attempts)
    app.add_middleware(CsrfMiddleware, csrf=csrf)
    app.add_middleware(SecurityHeadersMiddleware, csrf=csrf, cookie_secure=configuration.security.cookie_secure)
    app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")
    app.include_router(ingest_router)
    include_web_routers(app)

    @app.exception_handler(Exception)
    async def _on_error(request: Request, exc: Exception) -> Response:
        try:
            reporter = await request.state.dishka_container.get(SelfErrorReporter)
            await reporter.capture(exc, component=f"web:{request.url.path}")
        except Exception:  # noqa: S110
            pass
        await logger.aerror("unhandled error", path=request.url.path, error=str(exc))
        return JSONResponse({"detail": "internal server error"}, status_code=500)

    setup_dishka(container=container, app=app)
    return app
