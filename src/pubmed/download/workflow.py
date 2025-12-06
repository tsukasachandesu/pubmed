from __future__ import annotations

"""Orchestrate PDF downloads across multiple sources."""

import asyncio
from dataclasses import dataclass
from datetime import datetime
from typing import Awaitable, Callable, Iterable, Mapping, Sequence

import structlog
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from pubmed.adapters.botasaurus.tasks_request import PdfRequestResult
from pubmed.download.sources import pmc, scihub, unpaywall
from pubmed.search.ingest import Download, Paper, get_engine, init_db

logger = structlog.get_logger(__name__)

DownloadHandler = Callable[[str], Awaitable[PdfRequestResult | None]]


@dataclass(slots=True)
class DownloadJob:
    download_id: int
    pmid: str
    source: str


SOURCE_HANDLERS: dict[str, DownloadHandler] = {
    "pmc": pmc.download_from_pmc,
    "unpaywall": unpaywall.download_from_unpaywall,
    "scihub": scihub.download_from_scihub,
}


def _prepare_sessionmaker(db_url: str | None) -> sessionmaker:
    engine = get_engine(db_url)
    init_db(engine)
    return sessionmaker(bind=engine, future=True)


def _collect_jobs(session_factory: sessionmaker, sources: Sequence[str]) -> list[DownloadJob]:
    jobs: list[DownloadJob] = []
    with session_factory() as session:
        rows = session.execute(
            select(Download.id, Download.source, Paper.pmid)
            .join(Paper, Paper.id == Download.paper_id)
            .where(Download.status == "pending", Download.source.in_(sources))
        )
        for download_id, source, pmid in rows:
            jobs.append(DownloadJob(download_id=download_id, pmid=str(pmid), source=source))
    return jobs


async def _run_job(session_factory: sessionmaker, job: DownloadJob) -> None:
    handler = SOURCE_HANDLERS.get(job.source)
    if handler is None:
        logger.warning("no handler for source", source=job.source)
        _update_status(session_factory, job.download_id, "skipped", error="unknown source")
        return

    try:
        result = await handler(job.pmid)
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.exception("download failed", pmid=job.pmid, source=job.source)
        _update_status(session_factory, job.download_id, "failed", error=str(exc))
        return

    if result is None:
        _update_status(session_factory, job.download_id, "skipped", error="no url available")
        return

    _update_status(
        session_factory,
        job.download_id,
        "succeeded",
        path=str(result.path),
        meta={
            "status_code": result.status_code,
            "content_type": result.content_type,
            "final_url": result.final_url,
        },
        headers=result.headers,
    )


def _update_status(
    session_factory: sessionmaker,
    download_id: int,
    status: str,
    *,
    error: str | None = None,
    path: str | None = None,
    meta: Mapping[str, object] | None = None,
    headers: Mapping[str, str] | None = None,
) -> None:
    with session_factory() as session:
        download = session.get(Download, download_id)
        if not download:
            return
        download.status = status
        download.error = error
        download.path = path
        download.raw_http_meta = dict(meta) if meta else download.raw_http_meta
        download.raw_http_headers = dict(headers) if headers else download.raw_http_headers
        download.attempted_at = datetime.utcnow()
        session.commit()


async def download_pending(
    *,
    sources: Sequence[str] | None = None,
    max_concurrency: int = 3,
    db_url: str | None = None,
    allow_scihub: bool = False,
) -> list[DownloadJob]:
    """Download PDFs for pending entries from the configured sources."""

    allowed_sources: Iterable[str] = sources or list(SOURCE_HANDLERS.keys())
    if not allow_scihub:
        allowed_sources = [source for source in allowed_sources if source != "scihub"]

    session_factory = _prepare_sessionmaker(db_url)
    jobs = _collect_jobs(session_factory, list(allowed_sources))

    if not jobs:
        logger.info("no pending downloads found")
        return []

    semaphore = asyncio.Semaphore(max_concurrency)

    async def runner(job: DownloadJob) -> None:
        async with semaphore:
            await _run_job(session_factory, job)

    await asyncio.gather(*(runner(job) for job in jobs))
    return jobs


def run_downloads_sync(**kwargs: object) -> list[DownloadJob]:
    """Execute :func:`download_pending` synchronously for CLI use."""

    return asyncio.run(download_pending(**kwargs))
