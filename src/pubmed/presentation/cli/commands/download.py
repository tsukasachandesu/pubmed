"""Download command stubs."""

from __future__ import annotations

import typer

app = typer.Typer()


@app.command()
def run(
    sources: str = typer.Option("pmc,unpaywall", help="Comma-separated download sources"),
    max_workers: int = typer.Option(2, help="Maximum concurrent downloads"),
    output: str = typer.Option("data/papers", help="Directory for downloaded PDFs"),
    enable_scihub: bool = typer.Option(False, help="Allow Sci-Hub access when opted in"),
) -> None:
    """Placeholder download workflow."""

    typer.echo(
        f"[download] sources={sources} max_workers={max_workers} output={output} enable_scihub={enable_scihub}"
    )
