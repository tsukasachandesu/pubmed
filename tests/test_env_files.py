from pathlib import Path

from pubmed.config.env_files import load_env_file, update_env_file, write_env_file


def test_load_env_file_handles_missing(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"

    assert load_env_file(env_file) == {}


def test_update_env_file_merges_values(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    write_env_file(env_file, {"EXISTING": "1", "SHOULD_REPLACE": "old"})

    merged = update_env_file(env_file, {"NEW": "2", "SHOULD_REPLACE": "new"})

    assert merged == {"EXISTING": "1", "NEW": "2", "SHOULD_REPLACE": "new"}
    assert "EXISTING=1" in env_file.read_text()
    assert "NEW=2" in env_file.read_text()
    assert "SHOULD_REPLACE=new" in env_file.read_text()
