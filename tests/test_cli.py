from typer.testing import CliRunner

from pubmed.presentation.cli.app import app

runner = CliRunner()


def test_cli_help() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "Search PubMed" in result.output
