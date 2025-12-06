"""Public PMC source downloader."""

from __future__ import annotations

from pathlib import Path

import structlog

from pubmed.adapters.botasaurus.tasks_request import PdfRequestResult
from pubmed.download.sources.utils import persist_placeholder

logger = structlog.get_logger(__name__)


async def download_from_pmc(
    pmid: str, base_dir: str | Path | None = None
) -> PdfRequestResult | None:
    """Attempt to download a PDF from PMC.

    The implementation stores a placeholder PDF so the download workflow remains
    functional in constrained environments while preserving the architecture for
    real HTTP-based downloads.
    """

    logger.info("attempting pmc download", pmid=pmid)
    return await persist_placeholder(pmid, "pmc", base_dir=base_dir)


__all__ = ["download_from_pmc"]
