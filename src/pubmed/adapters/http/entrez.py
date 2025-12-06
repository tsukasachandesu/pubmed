"""Minimal Entrez client for ESearch and EFetch calls."""

from __future__ import annotations

from typing import Mapping, Sequence

import httpx

from pubmed.config.settings import load_settings
from pubmed.core.types import JSONMapping
from pubmed.adapters.http.client import http_client

ENTREZ_BASE_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"


class EntrezClient:
    """Lightweight async wrapper around the NCBI E-utilities endpoints."""

    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        self.client = client
        self.settings = load_settings().app

    def _auth_params(self) -> dict[str, str]:
        params: dict[str, str] = {
            "tool": self.settings.tool_name,
        }
        if self.settings.email:
            params["email"] = self.settings.email
        if self.settings.api_key:
            params["api_key"] = self.settings.api_key
        return params

    async def esearch(
        self,
        term: str,
        *,
        retmax: int = 20,
        retstart: int = 0,
        mindate: str | None = None,
        maxdate: str | None = None,
        sort: str | None = None,
    ) -> tuple[JSONMapping, str]:
        """Call ESearch and return parsed JSON plus the raw XML body."""

        params: dict[str, str | int] = {
            "db": "pubmed",
            "term": term,
            "retmode": "json",
            "retmax": retmax,
            "retstart": retstart,
            "usehistory": "y",
            **self._auth_params(),
        }
        if mindate:
            params["mindate"] = mindate
        if maxdate:
            params["maxdate"] = maxdate
        if sort:
            params["sort"] = sort

        async with http_client(self.client) as client:
            response = await client.get(f"{ENTREZ_BASE_URL}/esearch.fcgi", params=params)
            response.raise_for_status()
            raw = response.text
            payload = response.json()
        return payload, raw

    async def efetch(self, pmids: Sequence[str], *, rettype: str = "xml") -> str:
        """Fetch PubMed records for ``pmids`` as XML."""

        ids = ",".join(pmids)
        params: Mapping[str, str] = {
            "db": "pubmed",
            "id": ids,
            "rettype": rettype,
            "retmode": "xml",
            **self._auth_params(),
        }
        async with http_client(self.client) as client:
            response = await client.get(f"{ENTREZ_BASE_URL}/efetch.fcgi", params=params)
            response.raise_for_status()
            return response.text
