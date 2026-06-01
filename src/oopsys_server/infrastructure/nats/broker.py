import contextlib
from typing import Any

from faststream.nats import JStream, NatsBroker
from structlog import getLogger

from oopsys_server.configuration import Loggers
from oopsys_server.configuration.config import NatsModel

logger = getLogger(Loggers.notifier.name)

def notify_subject(prefix: str, account_id: str) -> str:
    return f"{prefix}.notify.{account_id}"

class NotificationGateway:

    def __init__(self, config: NatsModel) -> None:
        self._config = config
        self._broker: NatsBroker | None = None
        self._connected = False

    @property
    def connected(self) -> bool:
        return self._connected

    def _stream(self) -> JStream:
        return JStream(name=self._config.stream, subjects=[f"{self._config.subject_prefix}.notify.>"], declare=True)

    async def start(self) -> bool:
        if not self._config.enabled:
            await logger.ainfo("nats disabled, notifications stay local")
            return False
        broker = NatsBroker(self._config.servers, connect_timeout=int(self._config.connect_timeout))
        broker.publisher(f"{self._config.subject_prefix}.notify._declare", stream=self._stream())
        try:
            await broker.connect()
            await broker.start()
        except Exception as exc:
            with contextlib.suppress(Exception):
                await broker.stop()
            await logger.awarning("nats connect failed", reason=str(exc))
            return False
        self._broker = broker
        self._connected = True
        await logger.ainfo("nats notification gateway ready", servers=self._config.servers)
        return True

    async def publish(self, account_id: str, payload: dict[str, Any]) -> bool:
        if self._broker is None or not self._connected:
            return False
        subject = notify_subject(self._config.subject_prefix, account_id)
        try:
            await self._broker.publish(payload, subject, stream=self._config.stream)
        except Exception as exc:
            await logger.aerror("nats publish failed", subject=subject, reason=str(exc))
            return False
        return True

    async def close(self) -> None:
        if self._broker is not None:
            with contextlib.suppress(Exception):
                await self._broker.stop()
        self._broker = None
        self._connected = False
