"""Paths for storing downloaded papers and export artifacts."""

from __future__ import annotations

from pathlib import Path
from pubmed.config.settings import load_settings

DEFAULT_DATA_DIR = Path("data/papers")
EXPORTS_DIRNAME = "exports"


def resolve_data_dir(base_dir: str | Path | None = None) -> Path:
    """Resolve the base directory used to store papers.

    The value defaults to ``PUBMED_APP_DATA_DIR`` from the environment but can be
    overridden per call. ``~`` and relative paths are preserved so callers can
    control when to resolve them to absolute locations.
    """

    if base_dir is None:
        base_dir = load_settings().app.data_dir
    return Path(base_dir).expanduser()


def paper_pdf_path(pmid: str, *, base_dir: str | Path | None = None, mkdir: bool = False) -> Path:
    """Return the expected PDF path for a PubMed ID.

    Examples
    --------
    >>> paper_pdf_path("12345")
    PosixPath('data/papers/12345.pdf')
    """

    data_dir = resolve_data_dir(base_dir)
    if mkdir:
        data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir / f"{pmid}.pdf"


def paper_stem(pmid: str, *, base_dir: str | Path | None = None) -> Path:
    """Return the stem path used for ancillary files associated with a PMID.

    This is useful for sidecar JSON/CSV files that should be co-located with the
    PDF, e.g. ``data/papers/12345.json``.
    """

    return paper_pdf_path(pmid, base_dir=base_dir, mkdir=False).with_suffix("")


def export_path(filename: str, *, base_dir: str | Path | None = None, mkdir: bool = True) -> Path:
    """Return the path for an export artifact.

    Export files live in ``<data_root>/../exports`` so PDFs and exports share the
    top-level ``data`` directory while remaining separated.
    """

    data_dir = resolve_data_dir(base_dir)
    export_dir = data_dir.parent / EXPORTS_DIRNAME
    if mkdir:
        export_dir.mkdir(parents=True, exist_ok=True)
    return export_dir / filename
