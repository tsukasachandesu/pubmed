"""Sci-Hub download helper."""

from __future__ import annotations

import structlog

from pubmed.adapters.botasaurus.tasks_request import PdfRequestResult
from pubmed.download.sources.utils import persist_placeholder

logger = structlog.get_logger(__name__)


async def download_from_scihub(pmid: str) -> PdfRequestResult | None:
    """Persist a placeholder PDF representing a Sci-Hub fetch."""

    logger.info("attempting scihub download", pmid=pmid)
    return await persist_placeholder(pmid, "scihub")


__all__ = ["download_from_scihub"]
