"""Application configuration via pydantic-settings.

Secrets come only from the environment; repo keeps just ``.env.example``.
The app must refuse to start without required secrets (test scenario #6).
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- required secrets -----------------------------------------------------
    bot_token: str = Field(validation_alias="BOT_TOKEN")
    database_url: str = Field(
        validation_alias="DATABASE_URL",
        description="postgresql+asyncpg://user:pass@host:5432/dbname",
    )
    redis_url: str = Field(validation_alias="REDIS_URL")

    # --- TTL / sessions -------------------------------------------------------
    role_session_ttl_minutes: int = Field(default=60, validation_alias="ROLE_SESSION_TTL_MINUTES")
    workspace_ttl_hours: int = Field(default=24, validation_alias="WORKSPACE_TTL_HOURS")

    # --- attachment limits (safe demo defaults from AGENTS.md) ----------------
    max_files_per_ticket: int = Field(default=5, validation_alias="MAX_FILES_PER_TICKET")
    max_file_size_bytes: int = Field(
        default=5 * 1024 * 1024, validation_alias="MAX_FILE_SIZE_BYTES"
    )
    max_workspace_total_size_bytes: int = Field(
        default=20 * 1024 * 1024, validation_alias="MAX_WORKSPACE_TOTAL_SIZE_BYTES"
    )
    max_workspace_total_files: int = Field(default=20, validation_alias="MAX_WORKSPACE_TOTAL_FILES")
    allowed_mime_types: str = Field(
        default="image/png,image/jpeg,application/pdf,text/plain",
        validation_alias="ALLOWED_MIME_TYPES",
    )

    # --- misc ------------------------------------------------------------------
    log_level: str = Field(default="INFO", validation_alias="LOG_LEVEL")
    default_language: str = Field(default="ru", validation_alias="DEFAULT_LANGUAGE")
    text_max_length: int = Field(default=4096, validation_alias="TEXT_MAX_LENGTH")

    @field_validator("bot_token")
    @classmethod
    def _bot_token_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("BOT_TOKEN must be set and non-empty")
        return v.strip()

    @field_validator("database_url")
    @classmethod
    def _db_scheme(cls, v: str) -> str:
        if not v.startswith("postgresql+asyncpg://"):
            raise ValueError("DATABASE_URL must use postgresql+asyncpg:// scheme")
        return v

    @field_validator("default_language")
    @classmethod
    def _lang_supported(cls, v: str) -> str:
        if v not in {"ru", "en"}:
            raise ValueError("DEFAULT_LANGUAGE must be 'ru' or 'en'")
        return v

    @property
    def mime_allowlist(self) -> frozenset[str]:
        return frozenset(m.strip() for m in self.allowed_mime_types.split(",") if m.strip())

    @property
    def role_session_ttl_seconds(self) -> float:
        return self.role_session_ttl_minutes * 60.0

    @property
    def workspace_ttl_seconds(self) -> float:
        return self.workspace_ttl_hours * 3600.0


@lru_cache
def get_settings() -> Settings:
    """Cached accessor; raises pydantic.ValidationError if config is invalid/missing."""
    return Settings()  # type: ignore[call-arg]
