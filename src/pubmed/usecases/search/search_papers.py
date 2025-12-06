"""Use case for searching PubMed and persisting results."""

from __future__ import annotations

import asyncio
from typing import Iterable

from pubmed.adapters.http import EntrezClient
from pubmed.config.settings import load_settings
from pubmed.search.ingest import upsert_papers
from pubmed.search.parser import parse_pubmed_xml


async def search_papers(
    term: str,
    *,
    retmax: int = 20,
    mindate: str | None = None,
    maxdate: str | None = None,
    save_db: bool = False,
) -> list[dict[str, object]]:
    """Search PubMed for ``term`` and return parsed records."""

    client = EntrezClient()
    search_payload, raw_search = await client.esearch(
        term,
        retmax=retmax,
        mindate=mindate,
        maxdate=maxdate,
    )
    idlist: Iterable[str] = search_payload.get("esearchresult", {}).get("idlist", [])
    pmids = [str(pmid) for pmid in idlist]

    if not pmids:
        return []

    raw_fetch = await client.efetch(pmids)
    records = parse_pubmed_xml(raw_fetch)

    default_sources: tuple[str, ...] = ("pmc", "unpaywall")
    if load_settings().app.enable_scihub:
        default_sources += ("scihub",)

    if save_db:
        upsert_papers(
            records,
            raw_search=raw_search,
            raw_fetch=raw_fetch,
            default_sources=default_sources,
        )

    return records


def run_search_sync(
    *,
    term: str,
    retmax: int = 20,
    mindate: str | None = None,
    maxdate: str | None = None,
    save_db: bool = False,
) -> list[dict[str, object]]:
    """Convenience wrapper to execute :func:`search_papers` synchronously."""

    return asyncio.run(
        search_papers(
            term,
            retmax=retmax,
            mindate=mindate,
            maxdate=maxdate,
            save_db=save_db,
        )
    )
