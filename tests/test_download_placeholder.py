"""Coverage for placeholder download paths when Botasaurus is absent."""

from __future__ import annotations

import asyncio
from pathlib import Path

from pubmed.adapters.botasaurus.tasks_request import PDF_MAGIC
from pubmed.download import run_downloads_sync
from pubmed.download.sources.utils import persist_placeholder
from pubmed.search.ingest import Download, get_engine, upsert_papers
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker


def test_persist_placeholder_writes_pdf(tmp_path: Path) -> None:
    """Ensure the placeholder download produces a valid PDF on disk."""

    base_dir = tmp_path / "papers"
    result = asyncio.run(persist_placeholder("123", "pmc", base_dir=base_dir))

    pdf_path = base_dir / "123.pdf"
    assert pdf_path.exists()
    assert pdf_path.read_bytes().startswith(PDF_MAGIC)
    assert result.path == pdf_path
    assert result.status_code == 200
    assert result.content_type == "application/pdf"
    assert result.final_url == "pmc://123"


def test_download_workflow_honors_base_dir(tmp_path: Path) -> None:
    db_url = f"sqlite:///{tmp_path/'downloads.sqlite'}"
    output_dir = tmp_path / "custom-output"

    upsert_papers(
        [
            {
                "pmid": "321", 
                "title": "Example paper",
            }
        ],
        db_url=db_url,
        default_sources=("pmc",),
    )

    jobs = run_downloads_sync(sources=["pmc"], db_url=db_url, base_dir=output_dir)

    pdf_path = output_dir / "321.pdf"
    assert pdf_path.exists()
    assert len(jobs) == 1

    engine = get_engine(db_url)
    SessionLocal = sessionmaker(bind=engine, future=True)
    with SessionLocal() as session:
        download = session.execute(
            select(Download).where(Download.id == jobs[0].download_id)
        ).scalar_one()

    assert download.path == str(pdf_path)
