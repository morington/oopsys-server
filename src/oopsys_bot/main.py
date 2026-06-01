import asyncio

from structlog import getLogger

from oopsys_bot.worker import BotWorker
from oopsys_server.configuration import Configuration, Loggers

logger = getLogger(Loggers.notifier.name)

async def _run() -> None:
    configuration = Configuration()
    Loggers(developer_mode=configuration.is_development)
    if not configuration.nats.enabled:
        await logger.awarning("NATS disabled; bot worker has nothing to consume. Exiting.")
        return
    worker = BotWorker(configuration)
    await worker.run()

def main() -> int:
    try:
        asyncio.run(_run())
    except KeyboardInterrupt:
        logger.warning("bot worker interrupted")
    return 0
if __name__ == "__main__":
    raise SystemExit(main())
