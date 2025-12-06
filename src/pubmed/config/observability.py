"""Tracing and metrics initialization built on OpenTelemetry."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import structlog
from opentelemetry import metrics, trace
from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.trace.sampling import TraceIdRatioBased

logger = structlog.get_logger(__name__)


@dataclass
class ObservabilityConfig:
    tracing_enabled: bool = False
    metrics_enabled: bool = False
    service_name: str = "pubmed"
    exporter_endpoint: Optional[str] = None
    sampling_ratio: float = 1.0


def _configure_tracing(config: ObservabilityConfig, resource: Resource) -> None:
    provider = TracerProvider(resource=resource, sampler=TraceIdRatioBased(config.sampling_ratio))
    processor = BatchSpanProcessor(OTLPSpanExporter(endpoint=config.exporter_endpoint))
    provider.add_span_processor(processor)
    trace.set_tracer_provider(provider)
    logger.info("tracing enabled", exporter=config.exporter_endpoint, sample=config.sampling_ratio)


def _configure_metrics(config: ObservabilityConfig, resource: Resource) -> None:
    reader = PeriodicExportingMetricReader(
        OTLPMetricExporter(endpoint=config.exporter_endpoint),
    )
    provider = MeterProvider(resource=resource, metric_readers=[reader])
    metrics.set_meter_provider(provider)
    logger.info("metrics enabled", exporter=config.exporter_endpoint)


def init_observability(config: ObservabilityConfig) -> None:
    """Initialize OpenTelemetry tracing and metrics based on configuration."""

    if not (config.tracing_enabled or config.metrics_enabled):
        logger.debug("observability disabled")
        return

    resource = Resource.create({"service.name": config.service_name})

    if config.tracing_enabled:
        _configure_tracing(config, resource)

    if config.metrics_enabled:
        _configure_metrics(config, resource)
