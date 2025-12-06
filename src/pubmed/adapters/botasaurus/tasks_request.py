"""Botasaurus ``@request`` tasks for lightweight HTTP PDF downloads."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

import httpx
import structlog

from pubmed.adapters.storage.filesystem import save_pdf
from pubmed.config.settings import load_settings

from .client import BotasaurusConfig, request_task

logger = structlog.get_logger(__name__)

PDF_MAGIC = b"%PDF"


@dataclass(slots=True)
class PdfRequestTask:
    """Minimal payload for requesting a PDF via HTTP."""

    pmid: str
    url: str
    headers: Mapping[str, str] | None = None


@dataclass(slots=True)
class PdfRequestResult:
    """Information returned after a PDF download task completes."""

    pmid: str
    url: str
    path: Path
    status_code: int
    content_type: str | None


async def _fetch_pdf(task: PdfRequestTask) -> tuple[bytes, httpx.Response]:
    headers = dict(task.headers or {})
    async with httpx.AsyncClient(follow_redirects=True, timeout=30.0) as client:
        response = await client.get(task.url, headers=headers)
    response.raise_for_status()
    return response.content, response


def _validate_pdf(content: bytes) -> None:
    if not content.startswith(PDF_MAGIC):
        raise ValueError("Response does not appear to be a PDF")


@request_task()
async def download_pdf_request(task: PdfRequestTask) -> PdfRequestResult:
    """Download a PDF over HTTP and persist it to disk.

    The function is compatible with Botasaurus' ``@request`` decorator but can
    also be invoked directly in environments without Botasaurus installed.
    """

    content, response = await _fetch_pdf(task)
    _validate_pdf(content)

    settings = load_settings().app
    path = save_pdf(task.pmid, content, base_dir=settings.data_dir)

    logger.info(
        "pdf downloaded",
        pmid=task.pmid,
        url=task.url,
        status=response.status_code,
        path=str(path),
    )

    return PdfRequestResult(
        pmid=task.pmid,
        url=task.url,
        path=path,
        status_code=response.status_code,
        content_type=response.headers.get("content-type"),
    )


__all__ = ["BotasaurusConfig", "PdfRequestResult", "PdfRequestTask", "download_pdf_request"]
