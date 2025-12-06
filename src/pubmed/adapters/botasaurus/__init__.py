"""Botasaurus integration helpers and task definitions."""

from .client import BotasaurusConfig, botasaurus_available, browser_task, request_task
from .tasks_browser import BrowserDownloadTask, download_pdf_browser
from .tasks_request import PdfRequestResult, PdfRequestTask, download_pdf_request

__all__ = [
    "BotasaurusConfig",
    "BrowserDownloadTask",
    "PdfRequestResult",
    "PdfRequestTask",
    "botasaurus_available",
    "browser_task",
    "download_pdf_browser",
    "download_pdf_request",
    "request_task",
]