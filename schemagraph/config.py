"""Configuration for schemagraph.

Reads from environment variables (prefixed ``SCHEMAGRAPH_``) and from a
``.env`` file in the working directory. Individual API keys for VLM
providers are *not* required at import time — they're only consulted when a
particular provider is actually invoked.
"""

from __future__ import annotations

from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="SCHEMAGRAPH_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # general
    log_level: str = "INFO"
    cache_dir: str = ".schemagraph_cache"
    default_provider: str = "openai"

    # OpenAI
    openai_api_key: Optional[str] = Field(default=None, alias="OPENAI_API_KEY")
    openai_model: str = "gpt-4o"
    openai_base_url: Optional[str] = None

    # Anthropic
    anthropic_api_key: Optional[str] = Field(default=None, alias="ANTHROPIC_API_KEY")
    anthropic_model: str = "claude-3-5-sonnet-latest"

    # Google — two flavors:
    #   1) AI Studio / Developer API (default): set GOOGLE_API_KEY.
    #   2) Vertex AI (consumes GCP credits): set google_use_vertex=true plus
    #      google_project and google_location, and authenticate with
    #      `gcloud auth application-default login`. No API key needed.
    google_api_key: Optional[str] = Field(default=None, alias="GOOGLE_API_KEY")
    google_model: str = "gemini-1.5-pro"
    google_use_vertex: bool = False
    google_project: Optional[str] = Field(
        default=None,
        validation_alias="SCHEMAGRAPH_GOOGLE_PROJECT",
    )
    google_location: str = "us-central1"

    # OCR
    ocr_backend: str = "auto"  # "auto" | "paddle" | "tesseract" | "none"

    # CV thresholds
    cv_canny_low: int = 50
    cv_canny_high: int = 150
    cv_hough_threshold: int = 80
    cv_hough_min_line_length: int = 30
    cv_hough_max_line_gap: int = 8
    cv_min_component_area: int = 200
    cv_max_image_dim_px: int = 2048

    # Fusion
    fusion_snap_radius_px: float = 18.0
    fusion_edge_support_radius_px: float = 12.0


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def reset_settings() -> None:
    """Mostly useful for tests."""
    global _settings
    _settings = None
