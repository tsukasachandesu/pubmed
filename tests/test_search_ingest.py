from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from pubmed.config.settings import load_settings
from pubmed.search.ingest import Download, get_engine, upsert_papers


def test_upsert_papers_omits_scihub_when_disabled(tmp_path, monkeypatch):
    monkeypatch.setenv("PUBMED_ENABLE_SCIHUB", "false")
    load_settings.cache_clear()

    try:
        db_url = f"sqlite:///{tmp_path/'papers.sqlite'}"
        records = [
            {
                "pmid": "12345",
                "doi": "10.5555/example",
                "title": "Testing opt-in sources",
                "journal": "Journal of Tests",
                "publication_year": 2024,
            }
        ]

        upsert_papers(records, db_url=db_url, default_sources=("pmc", "unpaywall", "scihub"))

        engine = get_engine(db_url)
        SessionLocal = sessionmaker(bind=engine, future=True)
        with SessionLocal() as session:
            sources = session.execute(select(Download.source)).scalars().all()

        assert set(sources) == {"pmc", "unpaywall"}
        assert "scihub" not in sources
    finally:
        load_settings.cache_clear()
