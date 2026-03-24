"""アプリケーション設定 — 環境変数からパイプラインの動作パラメータを読み込む."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from edinet_pipeline.models import FilingFilters


def _get_env(name: str, *, default: str | None = None, required: bool = False) -> str:
    """環境変数を取得する. required=True かつ未設定なら ValueError を送出."""
    value = os.getenv(name, default)
    if required and not value:
        raise ValueError(f"Environment variable {name} is required.")
    if value is None:
        raise ValueError(f"Environment variable {name} is required.")
    return value


@dataclass(frozen=True)
class Settings:
    """パイプライン全体の設定値を保持するイミュータブルなデータクラス.

    Attributes:
        edinet_api_key:        EDINET API のサブスクリプションキー
        database_url:          PostgreSQL 接続文字列
        request_timeout:       HTTP リクエストのタイムアウト (秒)
        retry_count:           API リトライ回数
        backoff_seconds:       リトライ間隔の基準秒数 (線形バックオフ)
        process_sleep_seconds: 各書類処理間のスリープ (API レートリミット対策)
        log_level:             ログレベル (INFO / DEBUG 等)
        analytics_output_dir:  分析スナップショットの出力ディレクトリ
        filing_filters:        対象書類のフィルタ条件 (有価証券報告書のみ等)
    """

    edinet_api_key: str
    database_url: str
    request_timeout: int = 30
    retry_count: int = 3
    backoff_seconds: float = 2.0
    process_sleep_seconds: float = 1.0
    log_level: str = "INFO"
    analytics_output_dir: str = "artifacts/analytics"
    filing_filters: FilingFilters = field(default_factory=FilingFilters)

    @classmethod
    def from_env(cls) -> Settings:
        """環境変数から Settings インスタンスを生成するファクトリメソッド."""
        return cls(
            edinet_api_key=_get_env("EDINET_API_KEY", required=True),
            database_url=_get_env("DATABASE_URL", required=True),
            request_timeout=int(_get_env("EDINET_REQUEST_TIMEOUT", default="30")),
            retry_count=int(_get_env("EDINET_RETRY_COUNT", default="3")),
            backoff_seconds=float(_get_env("EDINET_BACKOFF_SECONDS", default="2")),
            process_sleep_seconds=float(_get_env("PROCESS_SLEEP_SECONDS", default="1")),
            log_level=_get_env("LOG_LEVEL", default="INFO").upper(),
            analytics_output_dir=_get_env(
                "ANALYTICS_OUTPUT_DIR", default="artifacts/analytics"
            ),
        )

    @property
    def analytics_output_root(self) -> Path:
        """分析出力ルートディレクトリの Path."""
        return Path(self.analytics_output_dir)

    @property
    def analytics_parquet_root(self) -> Path:
        """Parquet ファイルの出力先ディレクトリ."""
        return self.analytics_output_root / "parquet"

    @property
    def analytics_duckdb_path(self) -> Path:
        """DuckDB データベースファイルのフルパス."""
        return self.analytics_output_root / "edinet_analytics.duckdb"
