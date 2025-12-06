"""Doctor/health checks."""

from __future__ import annotations

from pathlib import Path

import typer
from sqlalchemy import text

from pubmed.config.settings import load_settings
from pubmed.search.ingest import get_engine, init_db

app = typer.Typer()


@app.command()
def run() -> None:
    """Perform lightweight consistency checks."""

    settings = load_settings()
    checks: list[str] = []

    if not settings.app.email:
        checks.append("Missing PUBMED_EMAIL; set it for NCBI compliance.")

    data_dir = Path(settings.app.data_dir).expanduser()
    try:
        data_dir.mkdir(parents=True, exist_ok=True)
        test_file = data_dir / ".write_test"
        test_file.write_text("ok")
        test_file.unlink()
    except OSError as exc:
        checks.append(f"Cannot write to data directory {data_dir}: {exc}")

    try:
        engine = get_engine()
        init_db(engine)
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except Exception as exc:  # pragma: no cover - defensive
        checks.append(f"Database connectivity failed: {exc}")

    if checks:
        typer.echo("Doctor found issues:")
        for check in checks:
            typer.echo(f"- {check}")
        raise typer.Exit(code=1)

    typer.echo("All checks passed.")
