"""CLI entrypoint for the PubMed toolkit."""

from __future__ import annotations

import typer

from pubmed.config.logging import configure_logging
from pubmed.config.observability import ObservabilityConfig, init_observability
from pubmed.config.settings import Settings, load_settings
from pubmed.presentation.cli import commands

app = typer.Typer(help="Search PubMed, store metadata, and download PDFs.")


class AppState:
    """Holds shared state across CLI commands."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings


@app.callback()
def main(
    ctx: typer.Context,
    enable_tracing: bool | None = typer.Option(
        None, is_flag=True, help="Enable tracing backend."
    ),
    enable_metrics: bool | None = typer.Option(
        None, is_flag=True, help="Enable metrics backend."
    ),
) -> None:
    """Initialize shared application state and logging."""

    settings = load_settings()
    configure_logging(settings.app)

    observability_settings = settings.observability
    observability_enabled = observability_settings.enabled
    tracing_enabled = enable_tracing if enable_tracing is not None else observability_enabled
    metrics_enabled = enable_metrics if enable_metrics is not None else observability_enabled

    init_observability(
        ObservabilityConfig(
            tracing_enabled=tracing_enabled,
            metrics_enabled=metrics_enabled,
            service_name=observability_settings.service_name,
            exporter_endpoint=observability_settings.otlp_endpoint,
            sampling_ratio=observability_settings.sampling_ratio,
        )
    )
    ctx.obj = AppState(settings=settings)


app.add_typer(commands.search.app, name="search", help="Search and ingest PubMed metadata.")
app.add_typer(commands.download.app, name="download", help="Download PDFs from multiple sources.")
app.add_typer(commands.show.app, name="show", help="Inspect stored papers and downloads.")
app.add_typer(commands.export.app, name="export", help="Export stored data to files.")
app.add_typer(commands.config.app, name="config", help="Validate and inspect configuration.")
app.add_typer(commands.doctor.app, name="doctor", help="Run consistency checks.")


def run() -> None:
    """Entry point for console scripts."""

    app()


if __name__ == "__main__":
    run()
