"""Botasaurus adapter utilities and safe fallbacks."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, TypeVar

import structlog

from pubmed.config.settings import load_settings

logger = structlog.get_logger(__name__)

F = TypeVar("F", bound=Callable[..., object])


@dataclass(slots=True)
class BotasaurusConfig:
    """Runtime configuration for Botasaurus tasks."""

    profile: str | None = None
    proxy: str | None = None
    max_browsers: int = 2

    @classmethod
    def from_settings(cls) -> "BotasaurusConfig":
        settings = load_settings().botasaurus
        proxy = str(settings.proxy) if settings.proxy else None
        return cls(
            profile=settings.profile,
            proxy=proxy,
            max_browsers=settings.max_browsers,
        )

    def to_options(self) -> dict[str, object]:
        options: dict[str, object] = {"max_browsers": self.max_browsers}
        if self.profile:
            options["profile"] = self.profile
        if self.proxy:
            options["proxy"] = self.proxy
        return options


def botasaurus_available() -> bool:
    """Return ``True`` when the Botasaurus package can be imported."""

    try:
        __import__("botasaurus")
    except ImportError:
        return False
    return True


def _maybe_get_decorator(name: str):
    try:
        from botasaurus import browser, request  # type: ignore
    except ImportError:
        return None
    return request if name == "request" else browser


def _passthrough_decorator(message: str) -> Callable[[F], F]:
    def decorator(func: F) -> F:
        logger.debug(message, task=getattr(func, "__name__", "unknown"))
        return func

    return decorator


def request_task(
    config: BotasaurusConfig | None = None, **options: Any
) -> Callable[[F], F]:
    """Return a decorator compatible with :func:`botasaurus.request`."""

    decorator = _maybe_get_decorator("request")
    cfg = config or BotasaurusConfig.from_settings()
    merged_options = {**cfg.to_options(), **options}

    if decorator:
        return decorator(**merged_options)

    return _passthrough_decorator("botasaurus.request not available; using passthrough")


def browser_task(
    config: BotasaurusConfig | None = None, **options: Any
) -> Callable[[F], F]:
    """Return a decorator compatible with :func:`botasaurus.browser`."""

    decorator = _maybe_get_decorator("browser")
    cfg = config or BotasaurusConfig.from_settings()
    merged_options = {**cfg.to_options(), **options}

    if decorator:
        return decorator(**merged_options)

    return _passthrough_decorator("botasaurus.browser not available; using passthrough")


__all__ = [
    "BotasaurusConfig",
    "botasaurus_available",
    "browser_task",
    "request_task",
]
