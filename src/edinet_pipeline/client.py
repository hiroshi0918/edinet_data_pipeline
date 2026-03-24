"""EDINET API v2 クライアント — 書類一覧の取得と CSV ZIP ダウンロードを担当."""

from __future__ import annotations

import io
import time
import zipfile
from typing import Any

import requests

from edinet_pipeline.config import Settings


class EdinetApiError(RuntimeError):
    """API 通信の失敗 (リトライ上限超過・予期しないレスポンス等)."""


class CsvUnavailableError(RuntimeError):
    """書類に CSV データが存在しない場合のエラー (status 404 など)."""


class EdinetClient:
    """EDINET API v2 の HTTP クライアント.

    リトライ・バックオフ・タイムアウトの制御は Settings の値に従う。
    """

    # サーバー側の一時障害で再試行するステータスコード
    RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}

    def __init__(self, settings: Settings, session: requests.Session | None = None) -> None:
        self.settings = settings
        self.session = session or requests.Session()

    def close(self) -> None:
        self.session.close()

    # ------------------------------------------------------------------ #
    #  公開 API メソッド
    # ------------------------------------------------------------------ #

    def fetch_documents(self, target_date: str) -> dict[str, Any]:
        """指定日付の書類一覧を取得する (type=2: 有価証券報告書等)."""
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
        """書類の CSV ZIP をダウンロードし、バイナリで返す.

        ZIP でないレスポンスが返った場合:
          - API が 404 相当を返す → CsvUnavailableError
          - それ以外 → EdinetApiError
        """
        response = self._request(
            f"https://api.edinet-fsa.go.jp/api/v2/documents/{doc_id}",
            params={"type": 5, "Subscription-Key": self.settings.edinet_api_key},
        )
        if response.status_code != 200:
            raise EdinetApiError(
                f"EDINET document download failed for {doc_id} with status {response.status_code}"
            )

        # 正常な ZIP であればそのまま返す
        if zipfile.is_zipfile(io.BytesIO(response.content)):
            return response.content

        # ZIP でない場合は JSON ペイロードを確認して原因を判定
        payload = self._safe_json(response)
        metadata = payload.get("metadata", {})
        if str(metadata.get("status")) == "404":
            raise CsvUnavailableError(f"CSV not available from EDINET for {doc_id}")

        content_type = response.headers.get("content-type", "unknown")
        raise EdinetApiError(f"Unexpected non-ZIP response for {doc_id}: {content_type}")

    # ------------------------------------------------------------------ #
    #  内部ユーティリティ
    # ------------------------------------------------------------------ #

    def _request(self, url: str, *, params: dict[str, Any]) -> requests.Response:
        """リトライ付き GET リクエスト — 指数バックオフで再試行する."""
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

            # リトライ対象のステータスコードなら待機して再試行
            if response.status_code in self.RETRYABLE_STATUS_CODES and attempt < max_attempts:
                self._sleep(attempt)
                continue
            return response

        raise EdinetApiError(f"Request failed after {max_attempts} attempts: {last_error}")

    def _sleep(self, attempt: int) -> None:
        """線形バックオフ: backoff_seconds × attempt 秒だけ待機."""
        time.sleep(self.settings.backoff_seconds * attempt)

    @staticmethod
    def _safe_json(response: requests.Response) -> dict[str, Any]:
        """レスポンスボディの JSON パースを試み、失敗時は空 dict を返す."""
        try:
            return response.json()
        except ValueError:
            return {}
