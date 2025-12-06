"""Utility helpers shared by download sources."""

from __future__ import annotations

from pathlib import Path

from pubmed.adapters.botasaurus.tasks_browser import BrowserDownloadTask, download_pdf_browser
from pubmed.adapters.botasaurus.tasks_request import PDF_MAGIC, PdfRequestResult


def placeholder_pdf(pmid: str, source: str) -> bytes:
    """Return a small placeholder PDF payload."""

    footer = f"Downloaded via {source} for PMID {pmid}".encode()
    return PDF_MAGIC + b"-1.4\n%placeholder\n" + footer


async def persist_placeholder(
    pmid: str, source: str, *, base_dir: str | Path | None = None
) -> PdfRequestResult:
    """Persist a placeholder PDF using the browser download task."""

    content = placeholder_pdf(pmid, source)
    return await download_pdf_browser(
        BrowserDownloadTask(pmid=pmid, url=f"{source}://{pmid}", content=content),
        base_dir=base_dir,
    )


__all__ = ["placeholder_pdf", "persist_placeholder"]
