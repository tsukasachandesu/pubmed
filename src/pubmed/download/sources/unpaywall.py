"""Unpaywall-backed PDF downloads."""

from __future__ import annotations

from pathlib import Path

import structlog

from pubmed.adapters.botasaurus.tasks_request import PdfRequestResult
from pubmed.download.sources.utils import persist_placeholder

logger = structlog.get_logger(__name__)


async def download_from_unpaywall(
    pmid: str, base_dir: str | Path | None = None
) -> PdfRequestResult | None:
    """Persist a placeholder PDF to simulate an Unpaywall fetch."""

    logger.info("attempting unpaywall download", pmid=pmid)
    return await persist_placeholder(pmid, "unpaywall", base_dir=base_dir)


__all__ = ["download_from_unpaywall"]
