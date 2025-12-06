"""Shared HTTP client utilities built on top of httpx.AsyncClient."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

import httpx

from pubmed.config.settings import load_settings
from pubmed.core.types import RetryPolicy
from pubmed.core.utils import build_retry


DEFAULT_TIMEOUT = httpx.Timeout(10.0)


def _default_client() -> httpx.AsyncClient:
    """Create a preconfigured :class:`httpx.AsyncClient` instance."""

    settings = load_settings().app
    timeout = DEFAULT_TIMEOUT
    proxies = settings.proxy_url
    headers = {"User-Agent": f"{settings.tool_name}/0.1 (+{settings.email or 'unknown'})"}
    return httpx.AsyncClient(timeout=timeout, proxies=proxies, headers=headers)


@asynccontextmanager
async def http_client(client: httpx.AsyncClient | None = None) -> AsyncIterator[httpx.AsyncClient]:
    """Yield an :class:`~httpx.AsyncClient`, creating one if necessary."""

    created = client is None
    session = client or _default_client()
    try:
        yield session
    finally:
        if created:
            await session.aclose()


async def get_with_retry(url: str, *, retry_policy: RetryPolicy | None = None, **kwargs: object) -> httpx.Response:
    """Perform a GET request with tenacity-based retries."""

    policy = retry_policy or RetryPolicy()
    async for attempt in build_retry(policy, is_async=True):
        with attempt:
            async with http_client() as client:
                return await client.get(url, **kwargs)
    raise RuntimeError("Retry loop exited unexpectedly")
