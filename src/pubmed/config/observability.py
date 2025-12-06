"""Observability helpers (tracing/metrics placeholders)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import structlog

logger = structlog.get_logger(__name__)


@dataclass
class ObservabilityConfig:
    tracing_enabled: bool = False
    metrics_enabled: bool = False
    service_name: str = "pubmed"
    exporter_endpoint: Optional[str] = None


def init_observability(config: ObservabilityConfig) -> None:
    """Initialize observability backends.

    The implementation is intentionally lightweight for the project template.
    Replace this with OpenTelemetry plumbing as the project grows.
    """

    if config.tracing_enabled or config.metrics_enabled:
        logger.info("observability initialized", config=config)
    else:
        logger.debug("observability disabled")
