"""Helpers for reading and writing simple .env files."""

from __future__ import annotations

from pathlib import Path


def load_env_file(env_file: Path) -> dict[str, str]:
    """Load key/value pairs from a dotenv-style file."""

    if not env_file.exists():
        return {}

    values: dict[str, str] = {}
    for raw_line in env_file.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()

    return values


def write_env_file(env_file: Path, values: dict[str, str]) -> None:
    """Persist key/value pairs to a dotenv-style file."""

    lines = [f"{key}={value}" for key, value in sorted(values.items())]
    trailing_newline = "\n" if lines else ""
    env_file.write_text("\n".join(lines) + trailing_newline)


def update_env_file(env_file: Path, updates: dict[str, str]) -> dict[str, str]:
    """Merge updates into an env file and return the merged mapping."""

    values = load_env_file(env_file)
    values.update(updates)
    write_env_file(env_file, values)
    return values


__all__ = ["load_env_file", "write_env_file", "update_env_file"]
