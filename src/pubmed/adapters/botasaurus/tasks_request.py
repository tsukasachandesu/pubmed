"""Botasaurus-compatible request task for downloading PDFs over HTTP."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, cast

import httpx
import structlog

from httpx import _types as httpx_types

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
    headers: Mapping[str, str]
    final_url: str


async def _fetch_pdf(task: PdfRequestTask) -> tuple[bytes, httpx.Response]:
    settings = load_settings()
    headers = {
        "User-Agent": f"{settings.app.tool_name}/0.1 (+{settings.app.email or 'unknown'})",
        **dict(task.headers or {}),
    }
    proxy = settings.botasaurus.proxy or settings.app.proxy_url
    proxy_config: httpx_types.ProxyTypes | None = (
        cast(httpx_types.ProxyTypes, str(proxy)) if proxy else None
    )

    async with httpx.AsyncClient(
        follow_redirects=True,
        timeout=30.0,
        proxy=proxy_config,
        headers=headers,
    ) as client:
        response = await client.get(task.url)
    response.raise_for_status()
    return response.content, response


def _validate_pdf(content: bytes) -> None:
    if not content.startswith(PDF_MAGIC):
        raise ValueError("Response does not appear to be a PDF")


@request_task()
async def download_pdf_request(
    task: PdfRequestTask, *, base_dir: str | Path | None = None
) -> PdfRequestResult:
    """Download a PDF over HTTP and persist it to disk."""

    content, response = await _fetch_pdf(task)
    _validate_pdf(content)

    settings = load_settings().app
    path = save_pdf(task.pmid, content, base_dir=base_dir or settings.data_dir)

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
        headers=dict(response.headers),
        final_url=str(response.url),
    )


__all__ = ["BotasaurusConfig", "PdfRequestResult", "PdfRequestTask", "download_pdf_request"]
