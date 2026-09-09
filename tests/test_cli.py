from pathlib import Path

from typer.testing import CliRunner

from polybench.cli.main import app

runner = CliRunner()

PROJECT = Path(__file__).parent / "java_project"


def test_list_text(monkeypatch) -> None:
    monkeypatch.chdir(PROJECT)
    result = runner.invoke(app, ["list"])
    assert result.exit_code == 0
    assert "physics-step" in result.stdout
    assert "check-collisions" in result.stdout


def test_list_json(monkeypatch) -> None:
    monkeypatch.chdir(PROJECT)
    result = runner.invoke(app, ["list", "--format", "json"])
    assert result.exit_code == 0
    assert '"benchmarks"' in result.stdout


def test_list_no_project(monkeypatch, tmp_path) -> None:
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["list"])
    assert result.exit_code == 1
    assert "No Java project" in result.stdout


def test_run_requires_name() -> None:
    result = runner.invoke(app, ["run"])
    assert result.exit_code != 0


def test_run_unknown_benchmark(monkeypatch) -> None:
    monkeypatch.chdir(PROJECT)
    result = runner.invoke(app, ["run", "does-not-exist"])
    assert result.exit_code == 1
    assert "not found" in result.stdout


def test_run_unknown_format(monkeypatch) -> None:
    monkeypatch.chdir(PROJECT)
    result = runner.invoke(app, ["run", "physics-step", "--format", "xml"])
    assert result.exit_code != 0
