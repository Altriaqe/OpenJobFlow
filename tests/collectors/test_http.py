import pytest
import requests
from jobflow.collectors.http import FetchError, fetch_json


class FakeResponse:
    def __init__(self) -> None:
        self.status_checked = False

    def raise_for_status(self) -> None:
        self.status_checked = True

    def json(self) -> dict[str, object]:
        return {"jobs": [{"id": "job-1"}]}


class FakeHttpErrorResponse:
    def raise_for_status(self) -> None:
        raise requests.HTTPError("HTTP 错误")


class FakeInvalidJsonResponse:
    def raise_for_status(self) -> None:
        pass

    def json(self) -> dict[str, object]:
        raise requests.JSONDecodeError("无效的 JSON", "", 0)


def test_fetch_json_returns_json_data(monkeypatch) -> None:
    request_args = {}
    response = FakeResponse()
    url = "http://example.com/api/jobs"

    def fake_get(url: str, *, timeout: int) -> FakeResponse:
        request_args["url"] = url
        request_args["timeout"] = timeout

        return response

    monkeypatch.setattr("jobflow.collectors.http.requests.get", fake_get)

    result = fetch_json(url)

    assert request_args["url"] == url
    assert request_args["timeout"] == 10
    assert response.status_checked is True
    assert result == {"jobs": [{"id": "job-1"}]}


def test_fetch_json_converts_timeout_error_to_fetch_error(monkeypatch) -> None:
    url = "http://example.com/api/jobs"

    def fake_get(request_url: str, *, timeout: int) -> None:
        raise requests.Timeout("请求超时")

    monkeypatch.setattr("jobflow.collectors.http.requests.get", fake_get)

    with pytest.raises(FetchError) as exc_info:
        fetch_json(url)

    assert url in str(exc_info.value)


def test_fetch_json_converts_http_error_to_fetch_error(monkeypatch) -> None:
    url = "http://example.com/api/jobs"

    def fake_get(request_url: str, *, timeout: int) -> FakeHttpErrorResponse:
        return FakeHttpErrorResponse()

    monkeypatch.setattr("jobflow.collectors.http.requests.get", fake_get)

    with pytest.raises(FetchError) as exc_info:
        fetch_json(url)

    assert url in str(exc_info.value)


def test_fetch_json_converts_json_decode_error_to_fetch_error(monkeypatch) -> None:
    url = "http://example.com/api/jobs"

    def fake_get(request_url: str, *, timeout: int) -> FakeInvalidJsonResponse:
        return FakeInvalidJsonResponse()

    monkeypatch.setattr("jobflow.collectors.http.requests.get", fake_get)

    with pytest.raises(FetchError) as exc_info:
        fetch_json(url)

    assert url in str(exc_info.value)
