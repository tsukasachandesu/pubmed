import pytest

import pubmed.config.observability as observability
from pubmed.config.observability import ObservabilityConfig, init_observability


def test_observability_config_defaults() -> None:
    config = ObservabilityConfig()

    assert config.tracing_enabled is False
    assert config.metrics_enabled is False
    assert config.service_name == "pubmed"
    assert config.exporter_endpoint is None
    assert config.sampling_ratio == 1.0


def test_init_observability_calls_configured_paths(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []

    def fake_tracing(config: ObservabilityConfig, resource: object) -> None:
        calls.append("tracing")
        assert config.service_name == "service"

    def fake_metrics(config: ObservabilityConfig, resource: object) -> None:
        calls.append("metrics")
        assert config.exporter_endpoint == "http://collector"

    monkeypatch.setattr(observability, "_configure_tracing", fake_tracing)
    monkeypatch.setattr(observability, "_configure_metrics", fake_metrics)

    config = ObservabilityConfig(
        tracing_enabled=True,
        metrics_enabled=True,
        service_name="service",
        exporter_endpoint="http://collector",
        sampling_ratio=0.5,
    )

    init_observability(config)

    assert calls == ["tracing", "metrics"]
