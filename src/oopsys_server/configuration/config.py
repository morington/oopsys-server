from pydantic import BaseModel, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from structlog import getLogger

from oopsys_server.configuration.loggers import Loggers

logger = getLogger(Loggers.development.name)


class PostgresqlModel(BaseModel):
    host: str = Field(default="localhost")
    port: int = Field(default=5432, ge=1, le=65535)
    username: str = Field(default="postgres")
    password: str = Field(default="postgres")
    database: str = Field(default="postgres")
    driver: str = Field(default="postgresql+asyncpg")

    def url(self) -> str:
        return f"{self.driver}://{self.username}:{self.password}@{self.host}:{self.port}/{self.database}"

    def safe_url(self) -> str:
        return f"{self.driver}://***:***@{self.host}:{self.port}/{self.database}"


class ApplicationModel(BaseModel):
    host: str = Field(default="0.0.0.0")  # noqa: S104
    port: int = Field(default=8000, ge=1, le=65535)

    def url(self) -> str:
        return f"http://{self.host}:{self.port}"


class NatsModel(BaseModel):
    enabled: bool = Field(default=True)
    servers: list[str] = Field(default_factory=lambda: ["nats://localhost:4222"])
    stream: str = Field(default="OOPSYS_SERVER")
    subject_prefix: str = Field(default="oopsys")
    connect_timeout: float = Field(default=5.0, gt=0)


class SecurityModel(BaseModel):
    secret_key: str = Field(default="dev-insecure-change-me")
    cookie_name: str = Field(default="oopsys_session")
    cookie_secure: bool = Field(default=True)
    session_ttl_seconds: int = Field(default=43200, gt=0)
    remember_ttl_seconds: int = Field(default=2592000, gt=0)
    max_failed_attempts: int = Field(default=5, ge=1)
    lockout_base_seconds: int = Field(default=5, ge=1)
    lockout_max_seconds: int = Field(default=900, ge=1)
    captcha_after_attempts: int = Field(default=3, ge=1)
    bot_token_key: str = Field(default="dev-insecure-bot-key-change-me")


class NotificationsModel(BaseModel):
    quiet_gap_seconds: int = Field(default=120, ge=1)
    renotify_window_seconds: int = Field(default=600, ge=1)


class LivenessModel(BaseModel):
    stale_seconds: int = Field(default=90, ge=1)
    scan_interval_seconds: int = Field(default=30, ge=1)
    poll_enabled: bool = Field(default=False)
    poll_timeout: float = Field(default=10.0, gt=0)


class Configuration(BaseSettings):
    is_development: bool = Field(default=False, alias="DEV")
    postgresql: PostgresqlModel = PostgresqlModel()
    application: ApplicationModel = ApplicationModel()
    nats: NatsModel = NatsModel()
    security: SecurityModel = SecurityModel()
    notifications: NotificationsModel = NotificationsModel()
    liveness: LivenessModel = LivenessModel()
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", env_nested_delimiter="__", extra="ignore"
    )

    @model_validator(mode="after")
    def warn_development(self) -> "Configuration":
        if self.is_development:
            logger.warning("Application started in development mode")
        return self
