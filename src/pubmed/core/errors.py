"""Shared exception hierarchy used across the project."""

from __future__ import annotations


class PubMedError(Exception):
    """Base exception for all custom errors in the PubMed toolkit."""


class PubMedValidationError(PubMedError):
    """Raised when input data or configuration fails validation."""


class PubMedRetryError(PubMedError):
    """Raised when an operation exhausts its retry attempts."""

    def __init__(self, message: str, *, attempts: int | None = None) -> None:
        suffix = f" after {attempts} attempts" if attempts is not None else ""
        super().__init__(f"{message}{suffix}")
        self.attempts = attempts
