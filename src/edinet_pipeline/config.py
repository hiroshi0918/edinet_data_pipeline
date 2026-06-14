"""アプリケーション設定 — 環境変数からパイプラインの動作パラメータを読み込む."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from edinet_pipeline.models import FilingFilters

DEFAULT_ANALYTICS_OUTPUT_DIR = "artifacts/analytics"
DEFAULT_DUCKDB_FILENAME = "edinet_analytics.duckdb"
DEFAULT_DUCKDB_PATH = f"{DEFAULT_ANALYTICS_OUTPUT_DIR}/{DEFAULT_DUCKDB_FILENAME}"

# 人的資本指標 (割合) として受け入れる上限値 (%)。
# 例: 男女間賃金格差は 100% を超える事例があるが、200% を超える値は
# 本文中の別の数字 (注釈番号など) を誤検知している可能性が高いため既定で除外する。
DEFAULT_HUMAN_METRIC_MAX_RATIO = 200.0


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
        edinet_api_key:          EDINET API のサブスクリプションキー
        database_url:            PostgreSQL 接続文字列
        request_timeout:         HTTP リクエストのタイムアウト (秒)
        retry_count:             API リトライ回数
        backoff_seconds:         リトライ間隔の基準秒数 (線形バックオフ)
        process_sleep_seconds:   各書類処理間のスリープ (API レートリミット対策)
        log_level:               ログレベル (INFO / DEBUG 等)
        analytics_output_dir:    分析スナップショットの出力ディレクトリ
        filing_filters:          対象書類のフィルタ条件 (有価証券報告書のみ等)
        human_metric_max_ratio:  人的資本指標として受け入れる最大値 (%)
        db_pool_min_size:        DB 接続プールの最小接続数
        db_pool_max_size:        DB 接続プールの最大接続数
        stale_processing_minutes: processing のまま放置された行を pending へ戻す閾値 (分)
    """

    edinet_api_key: str
    database_url: str
    request_timeout: int = 30
    retry_count: int = 3
    backoff_seconds: float = 2.0
    process_sleep_seconds: float = 1.0
    log_level: str = "INFO"
    analytics_output_dir: str = DEFAULT_ANALYTICS_OUTPUT_DIR
    filing_filters: FilingFilters = field(default_factory=FilingFilters)
    human_metric_max_ratio: float = DEFAULT_HUMAN_METRIC_MAX_RATIO
    db_pool_min_size: int = 1
    db_pool_max_size: int = 5
    # processing のまま停滞した行を pending へ自動回収する経過時間の閾値 (分)。
    # kill / OOM / 電源断などで死んだプロセスの残骸を無人運用でも自己回復させる。
    stale_processing_minutes: int = 60
    # --- LLM フォールバック (Ollama) ---
    llm_enabled: bool = False
    llm_endpoint: str = "http://localhost:11434/api/generate"
    llm_model: str = "qwen3.5:9b"
    llm_timeout: int = 120

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
                "ANALYTICS_OUTPUT_DIR", default=DEFAULT_ANALYTICS_OUTPUT_DIR
            ),
            human_metric_max_ratio=float(
                _get_env("HUMAN_METRIC_MAX_RATIO", default=str(DEFAULT_HUMAN_METRIC_MAX_RATIO))
            ),
            db_pool_min_size=int(_get_env("DB_POOL_MIN_SIZE", default="1")),
            db_pool_max_size=int(_get_env("DB_POOL_MAX_SIZE", default="5")),
            stale_processing_minutes=int(
                _get_env("STALE_PROCESSING_MINUTES", default="60")
            ),
            llm_enabled=_get_env("LLM_FALLBACK_ENABLED", default="false").lower() == "true",
            llm_endpoint=_get_env(
                "LLM_ENDPOINT", default="http://localhost:11434/api/generate"
            ),
            llm_model=_get_env("LLM_MODEL", default="qwen3.5:9b"),
            llm_timeout=int(_get_env("LLM_TIMEOUT", default="120")),
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
        return self.analytics_output_root / DEFAULT_DUCKDB_FILENAME
