"""CLI entrypoints for PDF downloads."""

from __future__ import annotations

import typer

from pubmed.download import run_downloads_sync

app = typer.Typer()


@app.command()
def run(
    sources: str = typer.Option("pmc,unpaywall", help="Comma-separated download sources"),
    max_workers: int = typer.Option(2, help="Maximum concurrent downloads"),
    output: str = typer.Option("data/papers", help="Directory for downloaded PDFs"),
    enable_scihub: bool = typer.Option(False, help="Allow Sci-Hub access when opted in"),
    db_url: str | None = typer.Option(None, help="Override database connection URL"),
) -> None:
    """Execute the download workflow for pending papers."""

    selected_sources = [source.strip() for source in sources.split(",") if source.strip()]
    jobs = run_downloads_sync(
        sources=selected_sources,
        max_concurrency=max_workers,
        db_url=db_url,
        allow_scihub=enable_scihub,
    )

    if not jobs:
        typer.echo("No pending downloads found.")
        raise typer.Exit(code=0)

    typer.echo(f"Triggered downloads for {len(jobs)} jobs in {output}.")
