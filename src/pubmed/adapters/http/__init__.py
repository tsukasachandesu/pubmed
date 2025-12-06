"""HTTP adapters for external services."""

from .client import get_with_retry, http_client
from .entrez import EntrezClient

__all__ = ["EntrezClient", "get_with_retry", "http_client"]
