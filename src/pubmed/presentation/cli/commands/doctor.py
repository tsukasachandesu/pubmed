"""Doctor/health checks."""

from __future__ import annotations

import typer

from pubmed.config.settings import load_settings
from pubmed.usecases.maintenance import run_doctor

app = typer.Typer()


@app.command()
def run() -> None:
    """Perform lightweight consistency checks."""

    settings = load_settings()
    issues = run_doctor(settings)

    if issues:
        typer.echo("Doctor found issues:")
        for issue in issues:
            typer.echo(f"- {issue}")
        raise typer.Exit(code=1)

    typer.echo("All checks passed.")
