from pathlib import Path

import pytest

from pubmed.adapters.storage.filesystem import (
    atomic_write_bytes,
    save_export,
    save_pdf,
)
from pubmed.adapters.storage.paths import export_path, paper_pdf_path, paper_stem


def test_paper_pdf_path_respects_base_dir(tmp_path: Path) -> None:
    base_dir = tmp_path / "papers"
    path = paper_pdf_path("12345", base_dir=base_dir)

    assert path == base_dir / "12345.pdf"
    assert not path.exists()

    path_with_dir = paper_pdf_path("67890", base_dir=base_dir, mkdir=True)
    assert path_with_dir.parent.exists()


def test_export_path_sits_next_to_papers(tmp_path: Path) -> None:
    base_dir = tmp_path / "papers"
    path = export_path("report.json", base_dir=base_dir)

    assert path.parent == tmp_path / "exports"
    assert path.name == "report.json"
    assert path.parent.exists()


def test_save_pdf_overwrites_atomically(tmp_path: Path) -> None:
    base_dir = tmp_path / "papers"
    first = save_pdf("123", b"v1", base_dir=base_dir)
    second = save_pdf("123", b"v2", base_dir=base_dir)

    assert first == second
    assert second.read_bytes() == b"v2"


def test_save_export_writes_bytes(tmp_path: Path) -> None:
    base_dir = tmp_path / "papers"
    path = save_export("table.csv", b"data,rows", base_dir=base_dir)

    assert path.read_bytes() == b"data,rows"


def test_paper_stem_points_to_base_path(tmp_path: Path) -> None:
    base_dir = tmp_path / "papers"
    stem = paper_stem("555", base_dir=base_dir)

    assert stem == base_dir / "555"
    assert stem.with_suffix(".pdf") == paper_pdf_path("555", base_dir=base_dir)


def test_atomic_write_bytes_replaces_existing(tmp_path: Path) -> None:
    target = tmp_path / "file.bin"
    target.write_bytes(b"old")

    atomic_write_bytes(target, b"new")

    assert target.read_bytes() == b"new"


def test_atomic_write_bytes_cleans_temp_on_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "file.bin"
    existing_files = set(target.parent.iterdir())

    def boom(self: Path, target: Path):
        raise RuntimeError("replace failed")

    monkeypatch.setattr(Path, "replace", boom, raising=True)

    with pytest.raises(RuntimeError, match="replace failed"):
        atomic_write_bytes(target, b"data")

    assert set(target.parent.iterdir()) == existing_files
