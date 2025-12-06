"""Coverage for placeholder download paths when Botasaurus is absent."""

from __future__ import annotations

import asyncio
from pathlib import Path

from pubmed.config import settings
from pubmed.download.sources.utils import persist_placeholder
from pubmed.adapters.botasaurus.tasks_request import PDF_MAGIC


def test_persist_placeholder_writes_pdf(monkeypatch, tmp_path: Path) -> None:
    """Ensure the placeholder download produces a valid PDF on disk."""

    monkeypatch.setenv("PUBMED_DATA_DIR", str(tmp_path / "papers"))
    settings.load_settings.cache_clear()

    try:
        result = asyncio.run(persist_placeholder("123", "pmc"))
    finally:
        settings.load_settings.cache_clear()

    pdf_path = tmp_path / "papers" / "123.pdf"
    assert pdf_path.exists()
    assert pdf_path.read_bytes().startswith(PDF_MAGIC)
    assert result.path == pdf_path
    assert result.status_code == 200
    assert result.content_type == "application/pdf"
    assert result.final_url == "pmc://123"
