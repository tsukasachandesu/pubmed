from typer.testing import CliRunner

from pubmed.presentation.cli.app import app
from pubmed.config.settings import AppSettings, Settings, load_settings
from pubmed.search.parser import PubmedXmlParseError

runner = CliRunner()


def test_download_cli_uses_scihub_setting_when_flag_missing(monkeypatch) -> None:
    captured: dict[str, object] = {}

    settings = Settings(app=AppSettings(enable_scihub=True))

    def fake_run_downloads_sync(*_: object, allow_scihub: bool, **__: object):
        captured["allow_scihub"] = allow_scihub
        return [{"id": 1}]

    monkeypatch.setattr("pubmed.config.settings.load_settings", lambda: settings)
    monkeypatch.setattr("pubmed.presentation.cli.app.load_settings", lambda: settings)
    monkeypatch.setattr(
        "pubmed.presentation.cli.commands.download.run_downloads_sync",
        fake_run_downloads_sync,
    )

    result = runner.invoke(app, ["download", "run", "--sources", "pmc"])

    assert result.exit_code == 0
    assert captured["allow_scihub"] is True


def test_cli_help() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "Search PubMed" in result.output


def test_config_set_scihub_updates_env(tmp_path) -> None:
    env_file = tmp_path / ".env"

    result = runner.invoke(
        app, ["config", "set-scihub", "--enable", "--env-file", str(env_file)]
    )

    assert result.exit_code == 0
    assert "PUBMED_ENABLE_SCIHUB=true" in env_file.read_text()


def test_config_set_botasaurus_updates_env(tmp_path) -> None:
    env_file = tmp_path / ".env"

    result = runner.invoke(
        app,
        [
            "config",
            "set-botasaurus",
            "--profile",
            "default",
            "--max-browsers",
            "3",
            "--proxy",
            "http://localhost:8080",
            "--env-file",
            str(env_file),
        ],
    )

    contents = env_file.read_text()
    assert result.exit_code == 0
    assert "BOTASAURUS_PROFILE=default" in contents
    assert "BOTASAURUS_MAX_BROWSERS=3" in contents
    assert "BOTASAURUS_PROXY=http://localhost:8080" in contents


def test_search_cli_handles_parse_errors(monkeypatch) -> None:
    def fake_run_search_sync(*_: object, **__: object):
        raise PubmedXmlParseError("Failed to parse test payload")

    monkeypatch.setattr(
        "pubmed.presentation.cli.commands.search.run_search_sync", fake_run_search_sync
    )

    result = runner.invoke(app, ["search", "run", "test-query"])

    assert result.exit_code == 1
    assert "Failed to parse test payload" in result.output


def test_cli_uses_observability_settings_when_flags_missing(monkeypatch) -> None:
    captured: dict[str, object] = {}

    monkeypatch.setattr("pubmed.presentation.cli.app.configure_logging", lambda *_: None)

    def fake_init(config: object) -> None:
        captured["config"] = config

    monkeypatch.setattr("pubmed.presentation.cli.app.init_observability", fake_init)

    load_settings.cache_clear()
    monkeypatch.setenv("OBS_ENABLED", "true")
    monkeypatch.setenv("OBS_SERVICE_NAME", "cli-service")
    monkeypatch.setenv("OBS_OTLP_ENDPOINT", "http://collector")
    monkeypatch.setenv("OBS_SAMPLING_RATIO", "0.25")

    try:
        result = runner.invoke(app, ["config", "show"])
    finally:
        load_settings.cache_clear()

    assert result.exit_code == 0
    config = captured["config"]

    assert config.tracing_enabled is True
    assert config.metrics_enabled is True
    assert config.service_name == "cli-service"
    assert config.exporter_endpoint == "http://collector"
    assert config.sampling_ratio == 0.25
