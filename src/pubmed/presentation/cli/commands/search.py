"""Search command stubs."""

from __future__ import annotations

import typer

app = typer.Typer()


@app.command()
def run(
    term: str = typer.Argument(..., help="Search query to submit to PubMed"),
    retmax: int = typer.Option(20, help="Maximum records to retrieve"),
    mindate: str = typer.Option(None, help="Minimum publication date (YYYY/MM/DD)"),
    maxdate: str = typer.Option(None, help="Maximum publication date (YYYY/MM/DD)"),
    save_db: bool = typer.Option(False, help="Persist results to the database"),
) -> None:
    """Placeholder search workflow.

    The full implementation will fetch results from ESearch/EFetch and
    persist them through the use case layer. For now we simply echo inputs.
    """

    typer.echo(
        f"[search] term={term} retmax={retmax} mindate={mindate} maxdate={maxdate} save_db={save_db}"
    )
