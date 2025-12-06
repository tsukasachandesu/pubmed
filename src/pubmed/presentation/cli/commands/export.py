"""Export helpers for persisted search results."""

from __future__ import annotations

import json

import typer
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from pubmed.adapters.storage import save_export
from pubmed.config.settings import load_settings
from pubmed.search.ingest import Download, Paper, get_engine, init_db

app = typer.Typer()


def _prepare_sessionmaker(db_url: str | None) -> sessionmaker:
    engine = get_engine(db_url)
    init_db(engine)
    return sessionmaker(bind=engine, future=True)


@app.command()
def papers(
    filename: str = typer.Option("papers.jsonl", help="Export file name (JSON Lines)"),
    include_raw: bool = typer.Option(False, help="Include raw API payloads if available"),
    db_url: str | None = typer.Option(None, help="Override database connection URL"),
) -> None:
    """Export stored papers and download metadata to a JSONL artifact."""

    session_factory = _prepare_sessionmaker(db_url)
    with session_factory() as session:
        records = list(session.scalars(select(Paper).order_by(Paper.id)))

    if not records:
        typer.echo("No papers available to export.")
        raise typer.Exit(code=0)

    payload: list[dict[str, object]] = []
    for paper in records:
        downloads = [
            {
                "source": download.source,
                "status": download.status,
                "error": download.error,
                "path": download.path,
                "attempted_at": download.attempted_at.isoformat() if download.attempted_at else None,
                "meta": download.raw_http_meta,
            }
            for download in paper.downloads
        ]

        payload.append(
            {
                "pmid": paper.pmid,
                "doi": paper.doi,
                "title": paper.title,
                "journal": paper.journal,
                "publication_year": paper.publication_year,
                "downloads": downloads,
                "raw_pubmed_xml": paper.raw_pubmed_xml if include_raw else None,
            }
        )

    content = "\n".join(json.dumps(item, ensure_ascii=False) for item in payload).encode()
    settings = load_settings()
    path = save_export(filename, content, base_dir=settings.app.data_dir)
    typer.echo(f"Exported {len(payload)} papers to {path}")
