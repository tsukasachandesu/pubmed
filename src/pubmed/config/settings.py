"""Application settings loaded from environment variables or .env files."""

from __future__ import annotations

from typing import Optional

from pydantic import Field, HttpUrl
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppSettings(BaseSettings):
    """Core configuration for the PubMed tool."""

    api_key: Optional[str] = Field(default=None, description="NCBI API key")
    tool_name: str = Field(default="pubmed-cli", description="NCBI tool identifier")
    email: Optional[str] = Field(default=None, description="Contact email for NCBI API")

    unpaywall_email: Optional[str] = Field(default=None, description="Contact email for Unpaywall")
    proxy_url: Optional[HttpUrl] = Field(default=None, description="Proxy URL for HTTP requests")
    data_dir: str = Field(default="data/papers", description="Directory to store downloaded PDFs")

    log_level: str = Field(default="INFO", description="Logging level")
    log_format: str = Field(default="console", description="Logging output format")

    enable_scihub: bool = Field(default=False, description="Allow Sci-Hub downloads")

    model_config = SettingsConfigDict(
        env_prefix="PUBMED_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


class BotasaurusSettings(BaseSettings):
    """Settings dedicated to Botasaurus browser automation."""

    profile: Optional[str] = Field(default=None, description="Botasaurus profile name")
    max_browsers: int = Field(default=2, description="Maximum concurrent browsers")
    proxy: Optional[HttpUrl] = Field(default=None, description="Proxy for Botasaurus")

    model_config = SettingsConfigDict(env_prefix="BOTASAURUS_", env_file=".env", extra="ignore")


class Settings(BaseSettings):
    """Aggregate application settings."""

    app: AppSettings = AppSettings()
    botasaurus: BotasaurusSettings = BotasaurusSettings()

    model_config = SettingsConfigDict(extra="ignore")


def load_settings() -> Settings:
    """Load settings eagerly so CLI commands can share configuration."""

    return Settings()
