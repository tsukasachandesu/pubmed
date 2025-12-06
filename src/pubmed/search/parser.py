"""Parsing helpers for PubMed XML responses."""

from __future__ import annotations

import logging
import xml.etree.ElementTree as ET
from typing import Any


class PubmedXmlParseError(Exception):
    """Raised when a PubMed XML payload cannot be parsed."""


logger = logging.getLogger(__name__)


def _text(element: ET.Element | None) -> str | None:
    return element.text.strip() if element is not None and element.text else None


def parse_pubmed_xml(xml: str) -> list[dict[str, Any]]:
    """Extract a minimal set of metadata fields from an EFetch XML payload."""

    try:
        root = ET.fromstring(xml)
    except ET.ParseError as exc:
        logger.error("Failed to parse PubMed XML response: %s", exc)
        raise PubmedXmlParseError("Unable to parse PubMed XML response.") from exc
    articles = []
    for article in root.findall(".//PubmedArticle"):
        pmid = _text(article.find(".//PMID"))
        title = _text(article.find(".//ArticleTitle"))
        journal = _text(article.find(".//Journal/Title"))
        doi = _text(article.find(".//ArticleId[@IdType='doi']"))
        pub_year = _text(article.find(".//PubDate/Year"))

        articles.append(
            {
                "pmid": pmid,
                "title": title,
                "journal": journal,
                "doi": doi,
                "publication_year": int(pub_year) if pub_year and pub_year.isdigit() else None,
                "raw_pubmed_xml": ET.tostring(article, encoding="unicode"),
            }
        )
    return articles
