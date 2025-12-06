"""Use case for running lightweight doctor checks."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import text

from pubmed.config.settings import Settings
from pubmed.search.ingest import get_engine, init_db


def run_doctor(settings: Settings) -> list[str]:
    """Return a list of issues detected by doctor checks."""

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

    return checks
