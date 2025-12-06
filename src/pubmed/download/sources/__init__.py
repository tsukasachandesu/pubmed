"""Source-specific download helpers."""

from __future__ import annotations

from pubmed.adapters.botasaurus.tasks_request import PdfRequestResult

from . import pmc, scihub, unpaywall

__all__ = ["PdfRequestResult", "pmc", "unpaywall", "scihub"]
