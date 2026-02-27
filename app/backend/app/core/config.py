"""Application configuration."""

from functools import lru_cache
from typing import Annotated

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings loaded from environment variables."""

    app_name: str = "PPLAN Backend"
    app_env: str = "development"
    api_prefix: str = "/api/v1"

    database_url: str = "postgresql+psycopg://pplan:pplan@localhost:5432/pplan"
    microsoft_tenant_id: str = "00000000-0000-0000-0000-000000000000"
    # Development fallback principal (for local MVP and tests).
    # Must be disabled in production environments.
    auth_allow_dev_principal: bool = True
    auth_dev_microsoft_oid: str = "dev-user-oid"
    auth_dev_email: str = "dev.user@local.test"
    auth_dev_display_name: str = "Dev User"
    cost_fte_month_working_days: int = Field(default=20, ge=1)
    # Keep .env support for comma-separated values (non-JSON).
    allowed_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: [
            "http://localhost:5173",
            "http://127.0.0.1:5173",
        ]
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    @field_validator("allowed_origins", mode="before")
    @classmethod
    def parse_origins(cls, value: str | list[str]) -> list[str]:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""

    return Settings()

