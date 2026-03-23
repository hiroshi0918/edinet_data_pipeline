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
]

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
        ]
    ),
}


def _frame_from_rows(rows: list[dict], columns: list[str]) -> pd.DataFrame:
    return pd.DataFrame(rows, columns=columns)


def build_company_year_metrics_frame(settings: Settings) -> pd.DataFrame:
    with db_connection(settings.database_url) as connection:
        repository = PipelineRepository(connection)
        rows = repository.fetch_company_year_metrics_rows()
    return _frame_from_rows(rows, COMPANY_YEAR_METRICS_COLUMNS)


def build_metric_evidence_frame(settings: Settings) -> pd.DataFrame:
    with db_connection(settings.database_url) as connection:
        repository = PipelineRepository(connection)
        rows = repository.fetch_metric_evidence_rows()
    return _frame_from_rows(rows, METRIC_EVIDENCE_COLUMNS)


def load_analytics_frames(settings: Settings) -> dict[str, pd.DataFrame]:
    return {
        COMPANY_YEAR_METRICS_DATASET: build_company_year_metrics_frame(settings),
        METRIC_EVIDENCE_DATASET: build_metric_evidence_frame(settings),
    }


def _empty_table(dataset_name: str) -> pa.Table:
    schema = DATASET_SCHEMAS[dataset_name]
    arrays = [pa.array([], type=field.type) for field in schema]
    return pa.Table.from_arrays(arrays, schema=schema)


def _frame_to_table(dataset_name: str, frame: pd.DataFrame) -> pa.Table:
    if frame.empty:
        return _empty_table(dataset_name)
    return pa.Table.from_pandas(
        frame,
        schema=DATASET_SCHEMAS[dataset_name],
        preserve_index=False,
    )


def write_partitioned_parquet(dataset_name: str, frame: pd.DataFrame, root_dir: Path) -> int:
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


def export_duckdb_snapshot(settings: Settings, frames: dict[str, pd.DataFrame]) -> dict[str, int]:
    output_root = settings.analytics_output_root
    output_root.mkdir(parents=True, exist_ok=True)

    tmp_path = output_root / f"{settings.analytics_duckdb_path.name}.tmp"
    target_path = settings.analytics_duckdb_path
    if tmp_path.exists():
        tmp_path.unlink()

    summary: dict[str, int] = {}
    connection = duckdb.connect(str(tmp_path))
    try:
        connection.execute("CREATE SCHEMA IF NOT EXISTS analytics")
        for dataset_name in DATASET_ORDER:
            frame = frames[dataset_name]
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

    tmp_path.replace(target_path)
    return summary


def export_analytics(settings: Settings, output_format: str) -> dict[str, dict[str, int]]:
    frames = load_analytics_frames(settings)
    summary: dict[str, dict[str, int]] = {}

    if output_format in {"parquet", "both"}:
        summary["parquet"] = export_parquet_snapshot(settings, frames)
    if output_format in {"duckdb", "both"}:
        summary["duckdb"] = export_duckdb_snapshot(settings, frames)

    return summary
