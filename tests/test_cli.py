import sqlite3
from pathlib import Path

import httpx
import pytest
from typer.testing import CliRunner

import phantomguard.cli as cli_module
from phantomguard.cli import app
from phantomguard.db.known_hallucinations import HallucinatedName, seed
from phantomguard.db.models import connect
from phantomguard.registry.npm import NpmClient
from phantomguard.registry.pypi import PyPiClient

FIXTURES = Path(__file__).parent / "fixtures"

runner = CliRunner()


@pytest.fixture(autouse=True)
def mock_registry_and_db(monkeypatch):
    def pypi_handler(request: httpx.Request) -> httpx.Response:
        name = request.url.path.split("/")[2]
        if name == "requests":
            return httpx.Response(200, json={"info": {"name": "requests"}, "releases": {}})
        return httpx.Response(404)

    def npm_handler(request: httpx.Request) -> httpx.Response:
        name = request.url.path.lstrip("/")
        if name == "react":
            return httpx.Response(200, json={"time": {"created": "2013-05-29T00:00:00.000Z"}})
        return httpx.Response(404)

    def fake_pypi_client_factory() -> PyPiClient:
        return PyPiClient(client=httpx.Client(transport=httpx.MockTransport(pypi_handler)))

    def fake_npm_client_factory() -> NpmClient:
        return NpmClient(client=httpx.Client(transport=httpx.MockTransport(npm_handler)))

    def fake_db_factory() -> sqlite3.Connection:
        return connect(":memory:")

    monkeypatch.setattr(cli_module, "_make_pypi_client", fake_pypi_client_factory)
    monkeypatch.setattr(cli_module, "_make_npm_client", fake_npm_client_factory)
    monkeypatch.setattr(cli_module, "_make_db_connection", fake_db_factory)


def test_scan_blocks_hallucinated_fixture():
    result = runner.invoke(app, ["scan", str(FIXTURES / "hallucinated_example.py")])
    assert "BLOCK" in result.stdout
    assert result.exit_code == 1


def test_scan_allows_clean_fixture():
    result = runner.invoke(app, ["scan", str(FIXTURES / "clean_example.py")])
    assert "ALLOW" in result.stdout
    assert "BLOCK" not in result.stdout
    assert result.exit_code == 0


def test_scan_directory_does_not_crash():
    result = runner.invoke(app, ["scan", str(FIXTURES)])
    assert result.exit_code in (0, 1)
    assert "ALLOW" in result.stdout
    assert "BLOCK" in result.stdout


def test_scan_explain_shows_signal_breakdown():
    result = runner.invoke(app, ["scan", str(FIXTURES / "hallucinated_example.py"), "--explain"])
    assert "not_in_registry" in result.stdout
    assert "+100" in result.stdout


def test_scan_without_explain_omits_signal_breakdown():
    result = runner.invoke(app, ["scan", str(FIXTURES / "hallucinated_example.py")])
    assert "not_in_registry" not in result.stdout


def test_scan_blocks_hallucinated_js_fixture():
    result = runner.invoke(app, ["scan", str(FIXTURES / "hallucinated_example.js")])
    assert "BLOCK" in result.stdout
    assert "[npm]" in result.stdout
    assert result.exit_code == 1


def test_scan_allows_clean_js_fixture():
    result = runner.invoke(app, ["scan", str(FIXTURES / "clean_example.js")])
    assert "ALLOW" in result.stdout
    assert "BLOCK" not in result.stdout
    assert result.exit_code == 0


def test_scan_accepts_multiple_paths():
    result = runner.invoke(
        app,
        [
            "scan",
            str(FIXTURES / "clean_example.py"),
            str(FIXTURES / "hallucinated_example.js"),
        ],
    )
    assert "ALLOW" in result.stdout
    assert "BLOCK" in result.stdout
    assert result.exit_code == 1
