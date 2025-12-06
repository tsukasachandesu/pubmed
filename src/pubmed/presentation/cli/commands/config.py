"""Configuration utilities."""

from __future__ import annotations

import json

import typer

from pubmed.config.settings import load_settings

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
    if strict and not settings.app.email:
        raise typer.Exit(code=1, message="PUBMED_EMAIL is required in strict mode")
    typer.echo("Configuration validated")
