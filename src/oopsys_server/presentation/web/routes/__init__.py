from fastapi import FastAPI

from oopsys_server.presentation.web.routes.agents import router as agents_router
from oopsys_server.presentation.web.routes.auth import router as auth_router
from oopsys_server.presentation.web.routes.bots import router as bots_router
from oopsys_server.presentation.web.routes.containers import router as containers_router
from oopsys_server.presentation.web.routes.dashboard import router as dashboard_router
from oopsys_server.presentation.web.routes.errors import router as errors_router
from oopsys_server.presentation.web.routes.notifications import router as notifications_router
from oopsys_server.presentation.web.routes.projects import router as projects_router
from oopsys_server.presentation.web.routes.servers import router as servers_router
from oopsys_server.presentation.web.routes.settings import router as settings_router
from oopsys_server.presentation.web.routes.stream import router as stream_router
from oopsys_server.presentation.web.routes.system import router as system_router


def include_web_routers(app: FastAPI) -> None:
    app.include_router(auth_router)
    app.include_router(dashboard_router)
    app.include_router(agents_router)
    app.include_router(servers_router)
    app.include_router(projects_router)
    app.include_router(errors_router)
    app.include_router(notifications_router)
    app.include_router(containers_router)
    app.include_router(bots_router)
    app.include_router(system_router)
    app.include_router(settings_router)
    app.include_router(stream_router)


__all__ = ["include_web_routers"]
