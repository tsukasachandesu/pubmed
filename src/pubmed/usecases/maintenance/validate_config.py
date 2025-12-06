"""Use case for validating configuration settings."""

from __future__ import annotations

from pubmed.config.settings import Settings


def validate_config(settings: Settings, *, strict: bool = False) -> list[str]:
    """Validate configuration and return any issues found."""

    issues: list[str] = []

    if strict and not settings.app.email:
        issues.append("PUBMED_EMAIL is required in strict mode")

    return issues
