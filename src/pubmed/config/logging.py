"""Logging configuration built with :func:`logging.config.dictConfig`."""

from __future__ import annotations

import logging
import logging.config
from typing import Literal

import structlog

from .settings import AppSettings

LogFormat = Literal["json", "console"]


def _shared_processors() -> list:
    return [
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
    ]


def _build_logging_config(level: int, log_format: LogFormat) -> dict:
    renderer = (
        structlog.processors.JSONRenderer()
        if log_format == "json"
        else structlog.dev.ConsoleRenderer()
    )

    return {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "structlog": {
                "()": structlog.stdlib.ProcessorFormatter,
                "processor": renderer,
                "foreign_pre_chain": _shared_processors(),
            }
        },
        "handlers": {
            "default": {
                "level": level,
                "class": "logging.StreamHandler",
                "formatter": "structlog",
            }
        },
        "loggers": {
            "": {
                "handlers": ["default"],
                "level": level,
            }
        },
    }


def configure_logging(settings: AppSettings) -> None:
    """Configure structlog and stdlib logging using ``dictConfig``."""

    level = getattr(logging, settings.log_level.upper(), logging.INFO)
    logging.config.dictConfig(_build_logging_config(level, settings.log_format))

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            *_shared_processors(),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )
