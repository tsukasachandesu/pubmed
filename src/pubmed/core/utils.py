"""Utility helpers shared across the codebase."""

from __future__ import annotations

import random
import re
import unicodedata
from typing import Callable, Tuple

from tenacity import (
    AsyncRetrying,
    Retrying,
    RetryCallState,
    retry_if_exception_type,
    stop_after_attempt,
    wait_random_exponential,
)

from .types import RetryPolicy


def slugify(value: str, *, separator: str = "-") -> str:
    """Convert an arbitrary string into a filesystem- and URL-friendly slug."""

    normalized = unicodedata.normalize("NFKD", value)
    ascii_text = normalized.encode("ascii", "ignore").decode().lower()
    slug = re.sub(r"[^a-z0-9]+", separator, ascii_text).strip(separator)
    slug = re.sub(fr"{re.escape(separator)}+", separator, slug)
    return slug


def _with_jitter(
    wait_strategy: Callable[[RetryCallState], float], jitter: float, maximum: float
) -> Callable[[RetryCallState], float]:
    def wrapper(retry_state: RetryCallState) -> float:
        base = wait_strategy(retry_state)
        delay = base + random.uniform(0, jitter)
        return min(delay, maximum)

    return wrapper


ExceptionTypes = Tuple[type[BaseException], ...]


def build_retry(
    policy: RetryPolicy,
    *,
    is_async: bool = True,
    retry_exceptions: ExceptionTypes = (Exception,),
    reraise: bool = True,
) -> Retrying | AsyncRetrying:
    """Create a configured tenacity retrying object.

    The helper centralises the retry configuration so callers only need to provide a
    :class:`RetryPolicy`. It returns either :class:`~tenacity.AsyncRetrying` or
    :class:`~tenacity.Retrying` depending on ``is_async``.
    """

    wait_strategy = wait_random_exponential(
        multiplier=policy.wait_min_seconds, max=policy.wait_max_seconds
    )
    wait = (
        _with_jitter(wait_strategy, jitter=policy.jitter, maximum=policy.wait_max_seconds)
        if policy.jitter > 0
        else wait_strategy
    )

    retry_condition = retry_if_exception_type(retry_exceptions)
    retry_class: type[Retrying | AsyncRetrying] = AsyncRetrying if is_async else Retrying

    return retry_class(
        stop=stop_after_attempt(policy.attempts),
        wait=wait,
        retry=retry_condition,
        reraise=reraise,
    )
