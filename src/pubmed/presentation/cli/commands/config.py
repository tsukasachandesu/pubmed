"""Configuration utilities."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import typer

from pydantic import HttpUrl, TypeAdapter, ValidationError

from pubmed.config.env_files import update_env_file
from pubmed.config.settings import load_settings
from pubmed.usecases.maintenance import validate_config

app = typer.Typer()


@app.command()
def show() -> None:
    """Display the current configuration as JSON."""

    settings = load_settings()
    typer.echo(json.dumps(settings.model_dump(), indent=2, default=str))


@app.command()
def validate(strict: bool = typer.Option(False, help="Fail on missing optional settings.")) -> None:
    """Validate configuration fields are present."""

    settings = load_settings()
    issues = validate_config(settings, strict=strict)
    if issues:
        for issue in issues:
            typer.echo(f"- {issue}")
        raise typer.Exit(code=1)
    typer.echo("Configuration validated")


@app.command(name="set-scihub")
def set_scihub_opt_in(
    enable: bool = typer.Option(
        ..., "--enable/--disable", help="Enable or disable Sci-Hub downloads (opt-in)."
    ),
    env_file: Path = typer.Option(Path(".env"), help="Path to the .env file to update."),
) -> None:
    """Toggle the Sci-Hub opt-in flag and persist it to the .env file."""

    normalized = str(enable).lower()
    update_env_file(env_file, {"PUBMED_ENABLE_SCIHUB": normalized})
    typer.echo(f"Updated {env_file} with PUBMED_ENABLE_SCIHUB={normalized}")


@app.command(name="set-botasaurus")
def set_botasaurus_settings(
    profile: Optional[str] = typer.Option(None, help="Botasaurus profile name to use."),
    max_browsers: Optional[int] = typer.Option(
        None, help="Maximum number of concurrent Botasaurus browsers.", min=1
    ),
    proxy: Optional[str] = typer.Option(None, help="Proxy URL for Botasaurus traffic."),
    env_file: Path = typer.Option(Path(".env"), help="Path to the .env file to update."),
) -> None:
    """Set Botasaurus-related settings in the .env file."""

    updates: dict[str, str] = {}

    if profile is not None:
        updates["BOTASAURUS_PROFILE"] = profile

    if max_browsers is not None:
        updates["BOTASAURUS_MAX_BROWSERS"] = str(max_browsers)

    if proxy is not None:
        try:
            TypeAdapter(HttpUrl).validate_python(proxy)
        except ValidationError as exc:  # pragma: no cover - exercised via Typer error
            raise typer.BadParameter("Proxy must be a valid URL") from exc
        updates["BOTASAURUS_PROXY"] = proxy

    if not updates:
        raise typer.BadParameter("Provide at least one setting to update.")

    update_env_file(env_file, updates)
    formatted_updates = ", ".join(f"{key}={value}" for key, value in sorted(updates.items()))
    typer.echo(f"Updated {env_file} with {formatted_updates}")
