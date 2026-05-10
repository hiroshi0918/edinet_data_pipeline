"""分析レイヤー — PostgreSQL のスナップショットを Parquet / DuckDB へエクスポート.

出力先 (デフォルト):
  artifacts/analytics/parquet/  — fiscal_year でパーティション分割された Parquet ファイル
  artifacts/analytics/edinet_analytics.duckdb — 全データを格納した DuckDB ファイル

データセット:
  company_year_metrics : 企業×年度ごとの財務・人的資本指標 (vw_company_year_metrics ビュー)
  metric_evidence      : 指標抽出の根拠・監査証跡
"""

from __future__ import annotations

import logging
import shutil
import time
from pathlib import Path

import duckdb
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from edinet_pipeline.config import Settings
from edinet_pipeline.db import PipelineRepository, db_connection
from edinet_pipeline.logging_utils import log_event

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------ #
#  データセット名とカラム定義
# ------------------------------------------------------------------ #

ANALYTICS_SCHEMA = "analytics"
COMPANY_YEAR_METRICS_DATASET = "company_year_metrics"
METRIC_EVIDENCE_DATASET = "metric_evidence"
DATASET_ORDER = (COMPANY_YEAR_METRICS_DATASET, METRIC_EVIDENCE_DATASET)

COMPANY_YEAR_METRICS_COLUMNS = [
    "edinet_code",
    "company_name",
    "fiscal_year",
    "doc_id",
    "submitted_date",
    "status",
    "sales",
    "operating_profit",
    "net_profit",
    "employee_count",
    "scope",
    "worker_type",
    "female_manager_ratio",
    "male_childcare_leave_ratio",
    "gender_wage_gap",
    "source_name",
]

METRIC_EVIDENCE_COLUMNS = [
    "doc_id",
    "edinet_code",
    "company_name",
    "fiscal_year",
    "submitted_date",
    "report_status",
    "metric_name",
    "item_name",
    "raw_value",
    "relative_year",
    "source_file",
    "matched_by",
    "element_id",
    "scope",
    "worker_type",
]

# PyArrow スキーマ — Parquet 出力時の型を明示的に指定
DATASET_SCHEMAS = {
    COMPANY_YEAR_METRICS_DATASET: pa.schema(
        [
            ("edinet_code", pa.string()),
            ("company_name", pa.string()),
            ("fiscal_year", pa.int64()),
            ("doc_id", pa.string()),
            ("submitted_date", pa.date32()),
            ("status", pa.string()),
            ("sales", pa.int64()),
            ("operating_profit", pa.int64()),
            ("net_profit", pa.int64()),
            ("employee_count", pa.int64()),
            ("scope", pa.string()),
            ("worker_type", pa.string()),
            ("female_manager_ratio", pa.decimal128(5, 2)),
            ("male_childcare_leave_ratio", pa.decimal128(5, 2)),
            ("gender_wage_gap", pa.decimal128(5, 2)),
            ("source_name", pa.string()),
        ]
    ),
    METRIC_EVIDENCE_DATASET: pa.schema(
        [
            ("doc_id", pa.string()),
            ("edinet_code", pa.string()),
            ("company_name", pa.string()),
            ("fiscal_year", pa.int64()),
            ("submitted_date", pa.date32()),
            ("report_status", pa.string()),
            ("metric_name", pa.string()),
            ("item_name", pa.string()),
            ("raw_value", pa.string()),
            ("relative_year", pa.string()),
            ("source_file", pa.string()),
            ("matched_by", pa.string()),
            ("element_id", pa.string()),
            ("scope", pa.string()),
            ("worker_type", pa.string()),
        ]
    ),
}


# ------------------------------------------------------------------ #
#  DataFrame ↔ PyArrow 変換
# ------------------------------------------------------------------ #

def _frame_from_rows(rows: list[dict], columns: list[str]) -> pd.DataFrame:
    """dict のリストを指定カラム順の DataFrame に変換する."""
    return pd.DataFrame(rows, columns=columns)


def build_company_year_metrics_frame(settings: Settings) -> pd.DataFrame:
    """PostgreSQL から企業×年度メトリクスを取得し DataFrame で返す."""
    with db_connection(settings.database_url) as connection:
        repository = PipelineRepository(connection)
        rows = repository.fetch_company_year_metrics_rows()
    return _frame_from_rows(rows, COMPANY_YEAR_METRICS_COLUMNS)


def build_metric_evidence_frame(settings: Settings) -> pd.DataFrame:
    """PostgreSQL から抽出根拠データを取得し DataFrame で返す."""
    with db_connection(settings.database_url) as connection:
        repository = PipelineRepository(connection)
        rows = repository.fetch_metric_evidence_rows()
    return _frame_from_rows(rows, METRIC_EVIDENCE_COLUMNS)


def load_analytics_frames(settings: Settings) -> dict[str, pd.DataFrame]:
    """全データセットの DataFrame をまとめて取得する."""
    return {
        COMPANY_YEAR_METRICS_DATASET: build_company_year_metrics_frame(settings),
        METRIC_EVIDENCE_DATASET: build_metric_evidence_frame(settings),
    }


def _empty_table(dataset_name: str) -> pa.Table:
    """スキーマのみ・レコード 0 件の空 PyArrow テーブルを生成する."""
    schema = DATASET_SCHEMAS[dataset_name]
    arrays = [pa.array([], type=field.type) for field in schema]
    return pa.Table.from_arrays(arrays, schema=schema)


def _frame_to_table(dataset_name: str, frame: pd.DataFrame) -> pa.Table:
    """DataFrame を明示的なスキーマで PyArrow Table に変換する."""
    if frame.empty:
        return _empty_table(dataset_name)
    return pa.Table.from_pandas(
        frame,
        schema=DATASET_SCHEMAS[dataset_name],
        preserve_index=False,
    )


# ------------------------------------------------------------------ #
#  Parquet 出力 (fiscal_year でパーティション分割)
# ------------------------------------------------------------------ #

def write_partitioned_parquet(dataset_name: str, frame: pd.DataFrame, root_dir: Path) -> int:
    """DataFrame を fiscal_year パーティションで Parquet 出力する.

    Returns:
        書き込んだ行数 (空の場合は 0)
    """
    dataset_root = root_dir / dataset_name
    dataset_root.mkdir(parents=True, exist_ok=True)

    table = _frame_to_table(dataset_name, frame)
    if frame.empty:
        pq.write_table(table, dataset_root / "empty.parquet")
        return 0

    pq.write_to_dataset(
        table,
        root_path=str(dataset_root),
        partition_cols=["fiscal_year"],
    )
    return int(len(frame))


def export_parquet_snapshot(settings: Settings, frames: dict[str, pd.DataFrame]) -> dict[str, int]:
    """Parquet スナップショットをアトミックに出力する.

    手順:
      1. 一時ディレクトリ (.tmp-*) に書き出し
      2. 成功時に本番ディレクトリへ移動 (アトミック replace)
      3. 失敗時は一時ディレクトリをクリーンアップ
    """
    output_root = settings.analytics_output_root
    output_root.mkdir(parents=True, exist_ok=True)
    tmp_root = output_root / f".tmp-{int(time.time() * 1000)}"
    tmp_parquet_root = tmp_root / "parquet"
    tmp_parquet_root.mkdir(parents=True, exist_ok=True)

    summary: dict[str, int] = {}
    try:
        for dataset_name in DATASET_ORDER:
            rows = write_partitioned_parquet(dataset_name, frames[dataset_name], tmp_parquet_root)
            summary[dataset_name] = rows

        # 一時ディレクトリ → 本番ディレクトリへアトミックに入れ替え
        target_root = settings.analytics_parquet_root
        target_root.mkdir(parents=True, exist_ok=True)
        for dataset_name in DATASET_ORDER:
            target_dataset_dir = target_root / dataset_name
            tmp_dataset_dir = tmp_parquet_root / dataset_name
            if target_dataset_dir.exists():
                shutil.rmtree(target_dataset_dir)
            tmp_dataset_dir.replace(target_dataset_dir)
            log_event(
                logger,
                "info",
                "analytics_export_completed",
                format="parquet",
                dataset=dataset_name,
                rows=summary[dataset_name],
                output_path=str(target_dataset_dir),
            )
    finally:
        if tmp_root.exists():
            shutil.rmtree(tmp_root, ignore_errors=True)

    return summary


# ------------------------------------------------------------------ #
#  DuckDB 出力 (analytics スキーマに全テーブルを格納)
# ------------------------------------------------------------------ #

def export_duckdb_snapshot(settings: Settings, frames: dict[str, pd.DataFrame]) -> dict[str, int]:
    """DuckDB スナップショットをアトミックに出力する.

    手順:
      1. .tmp ファイルに全データセットを書き込み
      2. 完了後に本番パスへ rename
    """
    output_root = settings.analytics_output_root
    output_root.mkdir(parents=True, exist_ok=True)

    tmp_path = output_root / f"{settings.analytics_duckdb_path.name}.tmp"
    target_path = settings.analytics_duckdb_path
    if tmp_path.exists():
        tmp_path.unlink()

    summary: dict[str, int] = {}
    connection = duckdb.connect(str(tmp_path))
    try:
        connection.execute(f"CREATE SCHEMA IF NOT EXISTS {ANALYTICS_SCHEMA}")
        for dataset_name in DATASET_ORDER:
            frame = frames[dataset_name]
            # DataFrame を一時リレーション名で登録 → CTAS でテーブル化
            relation_name = f"{dataset_name}_frame"
            connection.register(relation_name, frame)
            connection.execute(
                f"CREATE OR REPLACE TABLE analytics.{dataset_name} AS SELECT * FROM {relation_name}"
            )
            connection.unregister(relation_name)
            summary[dataset_name] = int(len(frame))
            log_event(
                logger,
                "info",
                "analytics_export_completed",
                format="duckdb",
                dataset=dataset_name,
                rows=summary[dataset_name],
                output_path=str(target_path),
            )
    finally:
        connection.close()

    # アトミック rename: tmp → 本番パス
    tmp_path.replace(target_path)
    return summary


# ------------------------------------------------------------------ #
#  エントリポイント: フォーマットに応じてエクスポートを実行
# ------------------------------------------------------------------ #

def export_analytics(settings: Settings, output_format: str) -> dict[str, dict[str, int]]:
    """指定フォーマット (parquet / duckdb / both) でスナップショットを出力する.

    Returns:
        {"parquet": {dataset: rows}, "duckdb": {dataset: rows}} 形式のサマリ
    """
    frames = load_analytics_frames(settings)
    summary: dict[str, dict[str, int]] = {}

    if output_format in {"parquet", "both"}:
        summary["parquet"] = export_parquet_snapshot(settings, frames)
    if output_format in {"duckdb", "both"}:
        summary["duckdb"] = export_duckdb_snapshot(settings, frames)

    return summary
