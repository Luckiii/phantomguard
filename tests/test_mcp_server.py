import httpx

from phantomguard.db.models import connect
from phantomguard.registry.npm import NpmClient
from phantomguard.registry.pypi import PyPiClient

from phantomguard.integrations.mcp_server import check_dependency_core


def _pypi_client() -> PyPiClient:
    def handler(request: httpx.Request) -> httpx.Response:
        name = request.url.path.split("/")[2]
        if name == "requests":
            return httpx.Response(200, json={"info": {"name": "requests"}, "releases": {}})
        return httpx.Response(404)

    return PyPiClient(client=httpx.Client(transport=httpx.MockTransport(handler)))


def _npm_client() -> NpmClient:
    def handler(request: httpx.Request) -> httpx.Response:
        name = request.url.path.lstrip("/")
        if name == "react":
            return httpx.Response(200, json={"time": {"created": "2013-05-29T00:00:00.000Z"}})
        return httpx.Response(404)

    return NpmClient(client=httpx.Client(transport=httpx.MockTransport(handler)))


def test_check_dependency_core_allows_real_pypi_package():
    conn = connect(":memory:")
    result = check_dependency_core("requests", "pypi", _pypi_client(), _npm_client(), conn)
    assert result["verdict"] == "ALLOW"
    assert result["ecosystem"] == "pypi"


def test_check_dependency_core_blocks_nonexistent_pypi_package():
    conn = connect(":memory:")
    result = check_dependency_core("definitely-not-real-xyz123", "pypi", _pypi_client(), _npm_client(), conn)
    assert result["verdict"] == "BLOCK"
    assert result["score"] >= 70


def test_check_dependency_core_allows_real_npm_package():
    conn = connect(":memory:")
    result = check_dependency_core("react", "npm", _pypi_client(), _npm_client(), conn)
    assert result["verdict"] == "ALLOW"
    assert result["ecosystem"] == "npm"


def test_check_dependency_core_blocks_nonexistent_npm_package():
    conn = connect(":memory:")
    result = check_dependency_core("evilpkg", "npm", _pypi_client(), _npm_client(), conn)
    assert result["verdict"] == "BLOCK"


def test_check_dependency_core_defaults_to_pypi():
    conn = connect(":memory:")
    result = check_dependency_core("requests", None, _pypi_client(), _npm_client(), conn)
    assert result["ecosystem"] == "pypi"
