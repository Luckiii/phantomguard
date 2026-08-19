import httpx

from phantomguard.registry.npm import NpmClient


def client_with(handler) -> NpmClient:
    return NpmClient(client=httpx.Client(transport=httpx.MockTransport(handler)))


def test_check_exists_true_on_200():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/lodash"
        return httpx.Response(200, json={"name": "lodash", "time": {"created": "2012-04-23T16:37:11.912Z"}})

    result = client_with(handler).check_exists("lodash")
    assert result.exists is True
    assert result.status_code == 200


def test_check_exists_false_on_404():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404)

    result = client_with(handler).check_exists("definitely-not-a-real-npm-pkg-xyz123")
    assert result.exists is False
    assert result.status_code == 404


def test_check_exists_none_on_unexpected_status():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500)

    result = client_with(handler).check_exists("react")
    assert result.exists is None
    assert result.error is not None


def test_check_exists_none_on_timeout():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("timed out", request=request)

    result = client_with(handler).check_exists("react")
    assert result.exists is None
    assert "timeout" in result.error.lower()


def test_check_exists_parses_created_date():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"name": "lodash", "time": {"created": "2012-04-23T16:37:11.912Z"}})

    result = client_with(handler).check_exists("lodash")
    assert result.first_release_at is not None
    assert result.first_release_at.year == 2012


def test_check_exists_first_release_at_none_when_time_missing():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"name": "lodash"})

    result = client_with(handler).check_exists("lodash")
    assert result.first_release_at is None


def test_check_exists_tags_result_with_npm_ecosystem():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"name": "lodash", "time": {"created": "2012-04-23T16:37:11.912Z"}})

    result = client_with(handler).check_exists("lodash")
    assert result.ecosystem == "npm"


def test_check_exists_handles_scoped_package_name():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/@angular%2fcore" or request.url.path == "/@angular/core"
        return httpx.Response(200, json={"name": "@angular/core", "time": {"created": "2016-09-14T00:00:00.000Z"}})

    result = client_with(handler).check_exists("@angular/core")
    assert result.exists is True
