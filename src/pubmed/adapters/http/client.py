"""Shared HTTP client utilities built on top of httpx.AsyncClient."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, cast

import httpx
from httpx import _types as httpx_types
from tenacity import AsyncRetrying

from pubmed.config.settings import load_settings
from pubmed.core.types import RetryPolicy
from pubmed.core.utils import build_retry


DEFAULT_TIMEOUT = httpx.Timeout(10.0)


def _default_client() -> httpx.AsyncClient:
    """Create a preconfigured :class:`httpx.AsyncClient` instance."""

    settings = load_settings().app
    timeout = DEFAULT_TIMEOUT
    proxy: httpx_types.ProxyTypes | None = (
        cast(httpx_types.ProxyTypes, str(settings.proxy_url))
        if settings.proxy_url
        else None
    )
    headers = {"User-Agent": f"{settings.tool_name}/0.1 (+{settings.email or 'unknown'})"}
    return httpx.AsyncClient(timeout=timeout, proxy=proxy, headers=headers)


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


async def get_with_retry(
    url: str, *, retry_policy: RetryPolicy | None = None, **kwargs: Any
) -> httpx.Response:
    """Perform a GET request with tenacity-based retries."""

    policy = retry_policy or RetryPolicy()
    retry = cast(AsyncRetrying, build_retry(policy, is_async=True))
    async for attempt in retry:
        with attempt:
            async with http_client() as client:
                return await client.get(url, **kwargs)
    raise RuntimeError("Retry loop exited unexpectedly")
