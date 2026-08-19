import httpx

from phantomguard.registry.pypi import PyPiClient


def client_with(handler) -> PyPiClient:
    return PyPiClient(client=httpx.Client(transport=httpx.MockTransport(handler)))


def test_check_exists_true_on_200():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/pypi/requests/json"
        return httpx.Response(200, json={"info": {"name": "requests"}, "releases": {}})

    result = client_with(handler).check_exists("requests")
    assert result.exists is True
    assert result.status_code == 200
    assert result.error is None


def test_check_exists_false_on_404():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404)

    result = client_with(handler).check_exists("definitely-not-a-real-package-xyz123")
    assert result.exists is False
    assert result.status_code == 404
    assert result.error is None


def test_check_exists_none_on_unexpected_status():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500)

    result = client_with(handler).check_exists("numpy")
    assert result.exists is None
    assert result.status_code == 500
    assert result.error is not None


def test_check_exists_none_on_timeout():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("timed out", request=request)

    result = client_with(handler).check_exists("numpy")
    assert result.exists is None
    assert result.status_code is None
    assert "timeout" in result.error.lower()


def test_check_exists_none_on_request_error():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection failed", request=request)

    result = client_with(handler).check_exists("numpy")
    assert result.exists is None
    assert result.status_code is None
    assert result.error is not None


def test_check_exists_parses_earliest_release_date():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "info": {"name": "requests"},
                "releases": {
                    "1.0.0": [{"upload_time_iso_8601": "2020-06-15T10:00:00.000000Z"}],
                    "2.0.0": [
                        {"upload_time_iso_8601": "2021-01-01T00:00:00.000000Z"},
                        {"upload_time_iso_8601": "2021-01-02T00:00:00.000000Z"},
                    ],
                },
            },
        )

    result = client_with(handler).check_exists("requests")
    assert result.first_release_at is not None
    assert result.first_release_at.year == 2020
    assert result.first_release_at.month == 6
    assert result.first_release_at.day == 15


def test_check_exists_first_release_at_none_when_no_releases():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"info": {"name": "requests"}, "releases": {}})

    result = client_with(handler).check_exists("requests")
    assert result.first_release_at is None


def test_check_exists_false_has_no_first_release_at():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404)

    result = client_with(handler).check_exists("nope")
    assert result.first_release_at is None


def test_check_exists_tags_result_with_pypi_ecosystem():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"info": {"name": "requests"}, "releases": {}})

    result = client_with(handler).check_exists("requests")
    assert result.ecosystem == "pypi"
