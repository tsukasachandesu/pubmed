"""Unpaywall-backed PDF downloads."""

from __future__ import annotations

import structlog

from pubmed.adapters.botasaurus.tasks_request import PdfRequestResult
from pubmed.download.sources.utils import persist_placeholder

logger = structlog.get_logger(__name__)


async def download_from_unpaywall(pmid: str) -> PdfRequestResult | None:
    """Persist a placeholder PDF to simulate an Unpaywall fetch."""

    logger.info("attempting unpaywall download", pmid=pmid)
    return await persist_placeholder(pmid, "unpaywall")


__all__ = ["download_from_unpaywall"]
