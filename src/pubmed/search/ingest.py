"""Persist parsed PubMed records into a local database."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Iterable

from sqlalchemy import JSON, Column, DateTime, Integer, String, Text, create_engine, select
from sqlalchemy.orm import Session, declarative_base, sessionmaker

from pubmed.config.settings import load_settings

Base = declarative_base()


class Paper(Base):
    __tablename__ = "papers"

    id = Column(Integer, primary_key=True)
    pmid = Column(String, unique=True, nullable=False)
    doi = Column(String, unique=True, nullable=True)
    title = Column(Text, nullable=True)
    journal = Column(String, nullable=True)
    publication_year = Column(Integer, nullable=True)
    raw_pubmed_xml = Column(Text, nullable=True)


class ApiCallLog(Base):
    __tablename__ = "api_call_logs"

    id = Column(Integer, primary_key=True)
    service = Column(String, nullable=False)
    endpoint = Column(String, nullable=False)
    request_params = Column(JSON, nullable=True)
    response_body = Column(Text, nullable=True)
    status_code = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


def _default_db_url() -> str:
    data_dir = Path(load_settings().app.data_dir).expanduser()
    data_dir.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{data_dir}/pubmed.sqlite"


def get_engine(url: str | None = None):
    db_url = url or _default_db_url()
    return create_engine(db_url, future=True)


def init_db(engine) -> None:
    Base.metadata.create_all(engine)


def upsert_papers(
    records: Iterable[dict[str, object]],
    *,
    raw_search: str | None = None,
    raw_fetch: str | None = None,
    db_url: str | None = None,
) -> None:
    """Upsert parsed records and store raw responses."""

    engine = get_engine(db_url)
    init_db(engine)
    SessionLocal = sessionmaker(bind=engine, future=True)

    with SessionLocal() as session:  # type: Session
        _persist_logs(session, raw_search=raw_search, raw_fetch=raw_fetch)
        for record in records:
            _merge_paper(session, record)
        session.commit()


def _persist_logs(session: Session, *, raw_search: str | None, raw_fetch: str | None) -> None:
    if raw_search:
        session.add(
            ApiCallLog(
                service="entrez",
                endpoint="esearch",
                response_body=raw_search,
            )
        )
    if raw_fetch:
        session.add(
            ApiCallLog(
                service="entrez",
                endpoint="efetch",
                response_body=raw_fetch,
            )
        )


def _merge_paper(session: Session, record: dict[str, object]) -> None:
    pmid = record.get("pmid")
    if pmid is None:
        return

    existing = session.execute(select(Paper).where(Paper.pmid == pmid)).scalar_one_or_none()
    if existing:
        for field in ("doi", "title", "journal", "publication_year", "raw_pubmed_xml"):
            value = record.get(field)
            if value is not None:
                setattr(existing, field, value)
    else:
        session.add(
            Paper(
                pmid=str(pmid),
                doi=record.get("doi"),
                title=record.get("title"),
                journal=record.get("journal"),
                publication_year=record.get("publication_year"),
                raw_pubmed_xml=record.get("raw_pubmed_xml"),
            )
        )
