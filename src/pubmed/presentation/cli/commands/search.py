"""Search command implementation."""

from __future__ import annotations

import typer

from pubmed.search.parser import PubmedXmlParseError
from pubmed.usecases.search import run_search_sync

app = typer.Typer()


@app.command()
def run(
    term: str = typer.Argument(..., help="Search query to submit to PubMed"),
    retmax: int = typer.Option(20, help="Maximum records to retrieve"),
    mindate: str | None = typer.Option(None, help="Minimum publication date (YYYY/MM/DD)"),
    maxdate: str | None = typer.Option(None, help="Maximum publication date (YYYY/MM/DD)"),
    save_db: bool = typer.Option(False, help="Persist results to the database"),
) -> None:
    """Execute the PubMed search workflow and display a summary."""

    try:
        records = run_search_sync(
            term=term,
            retmax=retmax,
            mindate=mindate,
            maxdate=maxdate,
            save_db=save_db,
        )
    except PubmedXmlParseError as exc:
        typer.secho(str(exc), fg=typer.colors.RED)
        raise typer.Exit(code=1) from exc

    if not records:
        typer.echo("No records found.")
        raise typer.Exit(code=0)

    typer.echo(f"Fetched {len(records)} records.")
    for record in records:
        pmid = record.get("pmid", "?")
        title = record.get("title") or "(no title)"
        typer.echo(f"- {pmid}: {title}")
