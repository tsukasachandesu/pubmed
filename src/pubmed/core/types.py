"""Common type aliases and lightweight data containers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

JSONMapping = Mapping[str, Any]


@dataclass(slots=True)
class RetryPolicy:
    """Configuration for retry behaviour used by :func:`pubmed.core.utils.build_retry`."""

    attempts: int = 3
    """Maximum number of retry attempts."""

    wait_min_seconds: float = 0.5
    """Initial wait before the first retry attempt."""

    wait_max_seconds: float = 5.0
    """Maximum delay between attempts when using exponential backoff."""

    jitter: float = 0.1
    """Random jitter factor to avoid thundering herds."""
