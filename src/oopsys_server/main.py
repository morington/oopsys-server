import asyncio

from dishka.integrations.fastapi import FastapiProvider
from structlog import getLogger
from uvicorn import Config, Server

from oopsys_server.configuration import Configuration, Loggers
from oopsys_server.dependency_injection import build_container
from oopsys_server.presentation.app import create_app

logger = getLogger(Loggers.main.name)

async def main() -> None:
    container = build_container(FastapiProvider())
    configuration: Configuration = await container.get(Configuration)
    Loggers(developer_mode=configuration.is_development)
    app = create_app(container, configuration)
    server = Server(config=Config(app=app, host=configuration.application.host, port=configuration.application.port, log_config=None, proxy_headers=True, forwarded_allow_ips="*"))
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
