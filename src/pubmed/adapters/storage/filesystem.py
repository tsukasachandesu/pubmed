"""Filesystem utilities for reading and writing paper assets."""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from .paths import export_path, paper_pdf_path


def atomic_write_bytes(target: Path, data: bytes) -> Path:
    """Write ``data`` to ``target`` atomically.

    The file is first written to a temporary location in the same directory and
    then moved into place with :meth:`Path.replace`.
    """

    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(delete=False, dir=target.parent) as tmp:
        tmp.write(data)
        temp_path = Path(tmp.name)

    temp_path.replace(target)
    return target


def save_pdf(pmid: str, content: bytes, *, base_dir: str | Path | None = None) -> Path:
    """Persist a PDF for ``pmid`` using an atomic write."""

    path = paper_pdf_path(pmid, base_dir=base_dir, mkdir=True)
    return atomic_write_bytes(path, content)


def save_export(filename: str, content: bytes, *, base_dir: str | Path | None = None) -> Path:
    """Persist an export artifact under the exports directory."""

    path = export_path(filename, base_dir=base_dir, mkdir=True)
    return atomic_write_bytes(path, content)


def read_bytes(path: Path) -> bytes:
    """Read the bytes from ``path``.

    Provided for symmetry with :func:`atomic_write_bytes`.
    """

    return path.read_bytes()


def file_exists(path: Path) -> bool:
    """Return whether ``path`` exists and is a file."""

    return path.is_file()


def remove_file(path: Path) -> None:
    """Remove ``path`` if it exists."""

    try:
        path.unlink()
    except FileNotFoundError:
        return


def copy_file(source: Path, destination: Path) -> Path:
    """Copy ``source`` to ``destination`` preserving metadata."""

    destination.parent.mkdir(parents=True, exist_ok=True)
    return Path(shutil.copy2(source, destination))
