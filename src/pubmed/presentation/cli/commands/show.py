"""Commands for inspecting stored papers and downloads."""

from __future__ import annotations

import typer
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from pubmed.search.ingest import Download, Paper, get_engine, init_db

app = typer.Typer()


def _prepare_sessionmaker(db_url: str | None) -> sessionmaker:
    engine = get_engine(db_url)
    init_db(engine)
    return sessionmaker(bind=engine, future=True)


@app.command()
def papers(
    limit: int = typer.Option(10, help="Maximum number of papers to display"),
    download_status: str | None = typer.Option(
        None, help="Filter papers by download status (pending/succeeded/failed/skipped)"
    ),
    db_url: str | None = typer.Option(None, help="Override database connection URL"),
) -> None:
    """Display stored papers with their download status."""

    session_factory = _prepare_sessionmaker(db_url)
    stmt = select(Paper).order_by(Paper.id.desc()).limit(limit)
    if download_status:
        stmt = (
            select(Paper)
            .join(Download)
            .where(Download.status == download_status)
            .distinct()
            .order_by(Paper.id.desc())
            .limit(limit)
        )

    with session_factory() as session:
        records = list(session.scalars(stmt))

    if not records:
        typer.echo("No papers found.")
        raise typer.Exit(code=0)

    for paper in records:
        title = (paper.title or "(no title)").replace("\n", " ")
        typer.echo(f"{paper.pmid} - {title}")
        if paper.downloads:
            summary = ", ".join(f"{d.source}:{d.status}" for d in paper.downloads)
            typer.echo(f"  downloads: {summary}")
