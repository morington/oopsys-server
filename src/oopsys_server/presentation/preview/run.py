from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from oopsys_server.configuration import Configuration
from oopsys_server.presentation.preview.routes import router
from oopsys_server.presentation.web.csrf import CsrfProtection

_STATIC_DIR = Path(__file__).resolve().parents[1] / "web" / "static"

def create_preview_app() -> FastAPI:
    app = FastAPI(title="oopsys-preview")
    app.state.csrf = CsrfProtection("preview-only")
    app.state.cookie_name = "preview"
    app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")
    app.include_router(router)
    return app

def run_preview() -> None:
    configuration = Configuration()
    if not configuration.is_development:
        print("Preview is only available with DEV=true. Refusing to start.")
        return
    app = create_preview_app()
    print("Preview running at http://127.0.0.1:8001/__preview")
    uvicorn.run(app, host="127.0.0.1", port=8001, log_config=None)
