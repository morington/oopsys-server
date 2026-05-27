from pydantic import BaseModel, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from structlog import getLogger

from oopsys_server.configuration import Loggers

logger = getLogger(Loggers.development.name)


class PostgresqlModel(BaseModel):
    host: str = Field(default="localhost")
    port: int = Field(default=5432, ge=1, le=65535)
    username: str = Field(default="postgres")
    password: str = Field(default="postgres")
    database: str = Field(default="postgres")
    driver: str = Field(default="postgresql+asyncpg")

    def url(self) -> str:
        """
        Build full PostgreSQL connection URL.
        """
        return f"{self.driver}://{self.username}:{self.password}@{self.host}:{self.port}/{self.database}"

    def safe_url(self) -> str:
        """
        Build safe PostgreSQL connection URL for logs.
        """
        return f"{self.driver}://***:***@{self.host}:{self.port}/{self.database}"


class ApplicationModel(BaseModel):
    host: str = Field(default="localhost")
    port: int = Field(default=8080, examples=[4222], ge=1, le=65535)

    def url(self) -> str:
        return f"http://{self.host}:{self.port}"


class Configuration(BaseSettings):
    is_development: bool = Field(default=False, alias="DEV")

    postgresql: PostgresqlModel = PostgresqlModel()
    application: ApplicationModel = ApplicationModel()

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
    )

    @model_validator(mode="after")
    def set_postgres_host(self) -> "Configuration":
        if not self.is_development:
            pass
        else:
            logger.warning("Application started in development mode")
        return self
