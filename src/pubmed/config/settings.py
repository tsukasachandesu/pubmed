"""Application settings loaded from environment variables or .env files."""

from __future__ import annotations

from functools import lru_cache
from typing import Optional

from pydantic import Field, HttpUrl, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppSettings(BaseSettings):
    """Core configuration for the PubMed tool."""

    api_key: Optional[str] = Field(default=None, description="NCBI API key")
    tool_name: str = Field(default="pubmed-cli", description="NCBI tool identifier")
    email: Optional[str] = Field(default=None, description="Contact email for NCBI API")

    unpaywall_email: Optional[str] = Field(default=None, description="Contact email for Unpaywall")
    proxy_url: Optional[HttpUrl] = Field(default=None, description="Proxy URL for HTTP requests")
    data_dir: str = Field(default="data/papers", description="Directory to store downloaded PDFs")

    log_level: str = Field(default="INFO", description="Logging level (DEBUG, INFO, ...)")
    log_format: str = Field(default="console", description="Logging output format (console/json)")

    enable_scihub: bool = Field(default=False, description="Allow Sci-Hub downloads")

    model_config = SettingsConfigDict(
        env_prefix="PUBMED_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @field_validator("log_format")
    @classmethod
    def validate_log_format(cls, value: str) -> str:
        value_lower = value.lower()
        if value_lower not in {"console", "json"}:
            raise ValueError("log_format must be either 'console' or 'json'")
        return value_lower


class BotasaurusSettings(BaseSettings):
    """Settings dedicated to Botasaurus browser automation."""

    profile: Optional[str] = Field(default=None, description="Botasaurus profile name")
    max_browsers: int = Field(default=2, description="Maximum concurrent browsers")
    proxy: Optional[HttpUrl] = Field(default=None, description="Proxy for Botasaurus")

    model_config = SettingsConfigDict(env_prefix="BOTASAURUS_", env_file=".env", extra="ignore")


class ObservabilitySettings(BaseSettings):
    """Settings for tracing and metrics."""

    enabled: bool = Field(default=False, description="Enable OpenTelemetry tracing/metrics")
    service_name: str = Field(default="pubmed", description="Service name for telemetry")
    otlp_endpoint: Optional[str] = Field(default=None, description="OTLP endpoint for exporters")
    sampling_ratio: float = Field(default=1.0, description="Trace sampling ratio (0-1)")

    model_config = SettingsConfigDict(env_prefix="OBS_", env_file=".env", extra="ignore")

    @field_validator("sampling_ratio")
    @classmethod
    def validate_ratio(cls, value: float) -> float:
        if not 0 <= value <= 1:
            raise ValueError("sampling_ratio must be between 0 and 1")
        return value


class Settings(BaseSettings):
    """Aggregate application settings."""

    app: AppSettings = AppSettings()
    botasaurus: BotasaurusSettings = BotasaurusSettings()
    observability: ObservabilitySettings = ObservabilitySettings()

    model_config = SettingsConfigDict(extra="ignore")


@lru_cache(maxsize=1)
def load_settings() -> Settings:
    """Load settings eagerly so CLI commands can share configuration."""

    return Settings()
