from typer.testing import CliRunner

from pubmed.presentation.cli.app import app
from pubmed.search.parser import PubmedXmlParseError

runner = CliRunner()


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
