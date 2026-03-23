from __future__ import annotations

import io
import time
import zipfile
from typing import Any

import requests

from edinet_pipeline.config import Settings


class EdinetApiError(RuntimeError):
    pass


class CsvUnavailableError(RuntimeError):
    pass


class EdinetClient:
    RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}

    def __init__(self, settings: Settings, session: requests.Session | None = None) -> None:
        self.settings = settings
        self.session = session or requests.Session()

    def close(self) -> None:
        self.session.close()

    def fetch_documents(self, target_date: str) -> dict[str, Any]:
        response = self._request(
            "https://api.edinet-fsa.go.jp/api/v2/documents.json",
            params={
                "date": target_date,
                "type": 2,
                "Subscription-Key": self.settings.edinet_api_key,
            },
        )
        if response.status_code != 200:
            raise EdinetApiError(
                f"EDINET document list request failed with status {response.status_code}"
            )
        return response.json()

    def download_document_csv(self, doc_id: str) -> bytes:
        response = self._request(
            f"https://api.edinet-fsa.go.jp/api/v2/documents/{doc_id}",
            params={"type": 5, "Subscription-Key": self.settings.edinet_api_key},
        )
        if response.status_code != 200:
            raise EdinetApiError(
                f"EDINET document download failed for {doc_id} with status {response.status_code}"
            )

        if zipfile.is_zipfile(io.BytesIO(response.content)):
            return response.content

        payload = self._safe_json(response)
        metadata = payload.get("metadata", {})
        if str(metadata.get("status")) == "404":
            raise CsvUnavailableError(f"CSV not available from EDINET for {doc_id}")

        content_type = response.headers.get("content-type", "unknown")
        raise EdinetApiError(f"Unexpected non-ZIP response for {doc_id}: {content_type}")

    def _request(self, url: str, *, params: dict[str, Any]) -> requests.Response:
        last_error: Exception | None = None
        max_attempts = self.settings.retry_count + 1
        for attempt in range(1, max_attempts + 1):
            try:
                response = self.session.get(
                    url,
                    params=params,
                    timeout=self.settings.request_timeout,
                )
            except requests.RequestException as exc:
                last_error = exc
                if attempt == max_attempts:
                    raise EdinetApiError(f"Request failed after {attempt} attempts: {exc}") from exc
                self._sleep(attempt)
                continue

            if response.status_code in self.RETRYABLE_STATUS_CODES and attempt < max_attempts:
                self._sleep(attempt)
                continue
            return response

        raise EdinetApiError(f"Request failed after {max_attempts} attempts: {last_error}")

    def _sleep(self, attempt: int) -> None:
        time.sleep(self.settings.backoff_seconds * attempt)

    @staticmethod
    def _safe_json(response: requests.Response) -> dict[str, Any]:
        try:
            return response.json()
        except ValueError:
            return {}
