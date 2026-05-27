import asyncio
from contextlib import asynccontextmanager

from dishka.integrations.fastapi import FastapiProvider, setup_dishka
from fastapi import FastAPI
from structlog import getLogger
from uvicorn import Config, Server

from oopsys_server.configuration import Configuration, Loggers
from oopsys_server.dependency_injection import build_container

logger = getLogger(Loggers.main.name)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await logger.awarning("Application starting up...")

    container = app.state.dishka_container

    try:
        yield
    finally:
        await container.close()
        await logger.awarning("Application shut down")


async def main() -> None:
    container = build_container(FastapiProvider())
    configuration: Configuration = await container.get(Configuration)

    Loggers(developer_mode=configuration.is_development)

    docs_kwargs = (
        {}
        if configuration.is_development
        else {
            "docs_url": None,
            "redoc_url": None,
            "openapi_url": None,
        }
    )
    app = FastAPI(lifespan=lifespan, **docs_kwargs)

    setup_dishka(container=container, app=app)

    server = Server(
        config=Config(
            app=app,
            host=configuration.application.host,
            port=configuration.application.port,
            log_config=None,
            reload=configuration.is_development,
        )
    )

    try:
        await logger.ainfo(f"Opening the server {configuration.application.url()}..")
        await server.serve()
    except asyncio.CancelledError:
        await logger.awarning("Uvicorn server task cancelled")
        raise


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.warning("Application interrupted by user")
