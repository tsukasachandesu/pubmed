"""Pytest configuration for the project."""
from __future__ import annotations

import sys
from pathlib import Path

# Ensure the src/ directory is on sys.path so the pubmed package is importable
PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = PROJECT_ROOT / "src"
if SRC_DIR.exists():
    sys.path.insert(0, str(SRC_DIR))
