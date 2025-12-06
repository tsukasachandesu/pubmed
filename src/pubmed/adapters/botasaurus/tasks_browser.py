"""Botasaurus ``@browser`` task definitions for sites requiring automation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

import structlog

from pubmed.adapters.storage.filesystem import save_pdf
from pubmed.config.settings import load_settings

from .client import BotasaurusConfig, browser_task
from .tasks_request import PDF_MAGIC, PdfRequestResult

logger = structlog.get_logger(__name__)


@dataclass(slots=True)
class BrowserDownloadTask:
    """Payload representing a browser-driven PDF fetch."""

    pmid: str
    url: str
    headers: Mapping[str, str] | None = None
    content: bytes | None = None


def _validate_pdf(content: bytes) -> None:
    if not content.startswith(PDF_MAGIC):
        raise ValueError("Browser response does not appear to be a PDF")


@browser_task()
async def download_pdf_browser(task: BrowserDownloadTask) -> PdfRequestResult:
    """Persist a PDF obtained via a browser automation session.

    The function intentionally avoids Botasaurus-specific types so it can be
    invoked directly in environments where Botasaurus is not installed yet. It
    expects ``task.content`` to contain the PDF bytes retrieved by a preceding
    browser action.
    """

    if task.content is None:
        raise ValueError("task.content is required for browser PDF downloads")

    _validate_pdf(task.content)

    settings = load_settings().app
    path = save_pdf(task.pmid, task.content, base_dir=settings.data_dir)

    logger.info("browser pdf saved", pmid=task.pmid, url=task.url, path=str(path))

    return PdfRequestResult(
        pmid=task.pmid,
        url=task.url,
        path=path,
        status_code=200,
        content_type="application/pdf",
    )


__all__ = ["BotasaurusConfig", "BrowserDownloadTask", "download_pdf_browser"]
