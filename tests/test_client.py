from __future__ import annotations

import io
import zipfile
from typing import Any

import pytest
import requests

from edinet_pipeline.client import CsvUnavailableError, EdinetApiError, EdinetClient
from edinet_pipeline.config import Settings


def make_settings(**overrides: Any) -> Settings:
    values = {
        "edinet_api_key": "dummy-edinet-key",
        "database_url": "postgresql://user:password@localhost:5432/edinet_db",
        "request_timeout": 7,
        "retry_count": 2,
        "backoff_seconds": 0.5,
        "process_sleep_seconds": 0.0,
        "log_level": "INFO",
        "analytics_output_dir": "artifacts/analytics",
    }
    values.update(overrides)
    return Settings(**values)


def build_zip_bytes() -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("XBRL_TO_CSV/jpcrp_sample.csv", "ok")
    return buffer.getvalue()


class FakeResponse:
    def __init__(
        self,
        *,
        status_code: int,
        json_data: dict[str, Any] | None = None,
        json_error: Exception | None = None,
        content: bytes = b"",
        headers: dict[str, str] | None = None,
    ) -> None:
        self.status_code = status_code
        self._json_data = json_data or {}
        self._json_error = json_error
        self.content = content
        self.headers = headers or {}

    def json(self) -> dict[str, Any]:
        if self._json_error is not None:
            raise self._json_error
        return self._json_data


class FakeSession:
    def __init__(self, outcomes: list[FakeResponse | Exception]) -> None:
        self.outcomes = list(outcomes)
        self.calls: list[dict[str, Any]] = []
        self.closed = False

    def get(self, url: str, *, params: dict[str, Any], timeout: int) -> FakeResponse:
        self.calls.append({"url": url, "params": params, "timeout": timeout})
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    def close(self) -> None:
        self.closed = True


def test_fetch_documents_returns_json_payload_and_uses_expected_params() -> None:
    session = FakeSession(
        [
            FakeResponse(
                status_code=200,
                json_data={"metadata": {"resultset": {"count": 1}}, "results": [{"docID": "S100"}]},
            )
        ]
    )
    client = EdinetClient(make_settings(), session=session)

    payload = client.fetch_documents("2024-03-29")

    assert payload["results"] == [{"docID": "S100"}]
    assert session.calls == [
        {
            "url": "https://api.edinet-fsa.go.jp/api/v2/documents.json",
            "params": {
                "date": "2024-03-29",
                "type": 2,
                "Subscription-Key": "dummy-edinet-key",
            },
            "timeout": 7,
        }
    ]


def test_fetch_documents_retries_request_exceptions(monkeypatch: pytest.MonkeyPatch) -> None:
    session = FakeSession(
        [
            requests.Timeout("temporary timeout"),
            FakeResponse(status_code=200, json_data={"results": []}),
        ]
    )
    client = EdinetClient(make_settings(), session=session)
    sleep_calls: list[int] = []
    monkeypatch.setattr(client, "_sleep", lambda attempt: sleep_calls.append(attempt))

    payload = client.fetch_documents("2024-03-29")

    assert payload == {"results": []}
    assert len(session.calls) == 2
    assert sleep_calls == [1]


def test_fetch_documents_raises_after_retry_limit_for_request_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = FakeSession(
        [
            requests.Timeout("timeout-1"),
            requests.Timeout("timeout-2"),
            requests.Timeout("timeout-3"),
        ]
    )
    client = EdinetClient(make_settings(retry_count=2), session=session)
    sleep_calls: list[int] = []
    monkeypatch.setattr(client, "_sleep", lambda attempt: sleep_calls.append(attempt))

    with pytest.raises(EdinetApiError, match="after 3 attempts"):
        client.fetch_documents("2024-03-29")

    assert len(session.calls) == 3
    assert sleep_calls == [1, 2]


def test_download_document_csv_retries_retryable_status_codes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    zip_bytes = build_zip_bytes()
    session = FakeSession(
        [
            FakeResponse(status_code=503),
            FakeResponse(status_code=200, content=zip_bytes),
        ]
    )
    client = EdinetClient(make_settings(), session=session)
    sleep_calls: list[int] = []
    monkeypatch.setattr(client, "_sleep", lambda attempt: sleep_calls.append(attempt))

    payload = client.download_document_csv("S100AAAA")

    assert payload == zip_bytes
    assert len(session.calls) == 2
    assert session.calls[0]["url"].endswith("/S100AAAA")
    assert sleep_calls == [1]


def test_download_document_csv_raises_csv_unavailable_for_404_metadata() -> None:
    session = FakeSession(
        [
            FakeResponse(
                status_code=200,
                content=b'{"metadata":{"status":"404"}}',
                json_data={"metadata": {"status": "404"}},
                headers={"content-type": "application/json"},
            )
        ]
    )
    client = EdinetClient(make_settings(), session=session)

    with pytest.raises(CsvUnavailableError, match="CSV not available"):
        client.download_document_csv("S100AAAA")


def test_download_document_csv_falls_back_when_json_is_invalid() -> None:
    session = FakeSession(
        [
            FakeResponse(
                status_code=200,
                content=b"not-a-zip",
                json_error=ValueError("invalid json"),
                headers={"content-type": "text/plain"},
            )
        ]
    )
    client = EdinetClient(make_settings(), session=session)

    with pytest.raises(EdinetApiError, match="Unexpected non-ZIP response"):
        client.download_document_csv("S100AAAA")
