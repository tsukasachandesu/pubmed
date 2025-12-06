import re

import pytest
from tenacity import AsyncRetrying, Retrying, stop_after_attempt

from pubmed.core.types import RetryPolicy
from pubmed.core.utils import build_retry, slugify


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("Hello, World!", "hello-world"),
        ("NFKD café", "nfkd-cafe"),
        ("multi---separator__test", "multi-separator-test"),
        (" custom  separator ", "custom-separator"),
    ],
)
def test_slugify_normalizes_and_trims(value: str, expected: str) -> None:
    assert slugify(value) == expected


@pytest.mark.parametrize("separator", ["-", "_"])
def test_slugify_respects_separator(separator: str) -> None:
    result = slugify("a b c", separator=separator)
    assert re.fullmatch(r"a[\-\_]b[\-\_]c", result)


@pytest.mark.parametrize("is_async", [True, False])
def test_build_retry_respects_policy(is_async: bool) -> None:
    policy = RetryPolicy(attempts=4, wait_min_seconds=0.1, wait_max_seconds=0.5, jitter=0.0)

    retry = build_retry(policy, is_async=is_async)

    assert isinstance(retry, AsyncRetrying if is_async else Retrying)
    assert isinstance(retry.stop, stop_after_attempt)
    assert retry.stop.max_attempt_number == policy.attempts


def test_build_retry_wraps_wait_with_jitter() -> None:
    base_policy = RetryPolicy(attempts=2, wait_min_seconds=0.1, wait_max_seconds=0.2, jitter=0.0)
    jittered_policy = RetryPolicy(
        attempts=2, wait_min_seconds=0.1, wait_max_seconds=0.2, jitter=0.5
    )

    base_retry = build_retry(base_policy, is_async=False)
    retry = build_retry(jittered_policy, is_async=False)

    assert callable(retry.wait)
    assert retry.wait.__name__ == "wrapper"
    assert retry.wait != base_retry.wait
