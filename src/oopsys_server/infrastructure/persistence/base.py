from datetime import UTC, datetime
from enum import Enum
from typing import Any

from sqlalchemy import String, TypeDecorator
from sqlalchemy.orm import DeclarativeBase


def utc_now() -> datetime:
    return datetime.now(tz=UTC)


class EnumValue(TypeDecorator):
    impl = String
    cache_ok = True

    def __init__(self, enum_cls: type[Enum], length: int = 32) -> None:
        self._enum = enum_cls
        super().__init__(length)

    def process_bind_param(self, value: Any, dialect: Any) -> str | None:
        if value is None:
            return None
        if isinstance(value, self._enum):
            return value.value
        return str(value)

    def process_result_value(self, value: Any, dialect: Any) -> Enum | None:
        if value is None:
            return None
        return self._enum(value)


class Base(DeclarativeBase):
    pass
