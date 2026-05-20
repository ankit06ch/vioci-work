"""Vioci web server configuration (database + optional cloud file storage)."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class ServerSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="VIOCI_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Local SQLite path (used when database_url is unset)
    sqlite_path: Path | None = Field(
        default=None,
        description="Override for workspace/.index.sqlite (tests only)",
    )

    # Supabase Postgres connection string (Project Settings → Database → URI)
    database_url: str | None = Field(
        default=None,
        description="postgresql://… — enables cloud database (Supabase free tier)",
    )

    # Supabase Storage (Project Settings → API → service_role key)
    supabase_url: str | None = None
    supabase_service_role_key: str | None = None
    supabase_bucket: str = "vioci"

    # Local cache for project files when using Supabase Storage (parse + SheetStore)
    file_cache_dir: Path = Field(
        default=Path.home() / ".cache" / "vioci" / "projects",
    )

    auth_disabled: bool = False


@lru_cache
def get_server_settings() -> ServerSettings:
    return ServerSettings()


def reset_server_settings() -> None:
    get_server_settings.cache_clear()
