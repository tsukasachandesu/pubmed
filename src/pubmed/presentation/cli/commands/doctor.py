"""Doctor/health checks."""

from __future__ import annotations

import typer

app = typer.Typer()


@app.command()
def run() -> None:
    """Perform lightweight consistency checks."""

    typer.echo("[doctor] basic checks passed (placeholder)")
