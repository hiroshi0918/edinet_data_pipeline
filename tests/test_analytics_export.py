from __future__ import annotations

import io
import zipfile
from pathlib import Path

import duckdb
import pandas as pd
import psycopg2
import pytest

from edinet_pipeline.cli import main


def build_document(
    *, doc_id: str, edinet_code: str, submit_date: str, csv_flag: str = "1"
) -> dict[str, str]:
    return {
        "docID": doc_id,
        "edinetCode": edinet_code,
        "filerName": f"Company {edinet_code}",
        "submitDateTime": f"{submit_date} 09:00",
        "periodEnd": "2024-03-31",
        "csvFlag": csv_flag,
        "ordinanceCode": "010",
        "formCode": "030000",
        "docDescription": "有価証券報告書－第10期(2023/04/01－2024/03/31)",
    }


def build_csv_zip(rows: list[dict[str, object]]) -> bytes:
    frame = pd.DataFrame(rows)
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(
            "XBRL_TO_CSV/jpcrp_sample.csv",
            frame.to_csv(index=False, sep="\t").encode("utf-16le"),
        )
    return buffer.getvalue()


class FakeClient:
    documents_by_date: dict[str, list[dict[str, str]]] = {}
    downloads: dict[str, bytes | Exception] = {}

    def __init__(self, settings) -> None:
        self.settings = settings

    @classmethod
    def reset(cls) -> None:
        cls.documents_by_date = {}
        cls.downloads = {}

    def close(self) -> None:
        return None

    def fetch_documents(self, target_date: str) -> dict[str, object]:
        documents = self.documents_by_date.get(target_date, [])
        return {
            "metadata": {"resultset": {"count": len(documents)}},
            "results": documents,
        }

    def download_document_csv(self, doc_id: str) -> bytes:
        return self.downloads[doc_id]


@pytest.fixture(autouse=True)
def reset_fake_client() -> None:
    FakeClient.reset()


def fetch_one(connection: psycopg2.extensions.connection, query: str) -> tuple:
    with connection.cursor() as cursor:
        cursor.execute(query)
        return cursor.fetchone()


def seed_processed_dataset(monkeypatch: pytest.MonkeyPatch) -> None:
    FakeClient.documents_by_date["2024-03-29"] = [
        build_document(doc_id="S100PROC1", edinet_code="E00001", submit_date="2024-03-29"),
        build_document(doc_id="S100PROC2", edinet_code="E00002", submit_date="2024-03-29"),
    ]
    FakeClient.downloads = {
        "S100PROC1": build_csv_zip(
            [
                {"項目名": "売上高", "値": "1,234", "相対年度": "当期"},
                {"項目名": "営業利益", "値": "234", "相対年度": "当期"},
                {"項目名": "当期純利益", "値": "123", "相対年度": "当期"},
                {"項目名": "従業員数", "値": "50", "相対年度": "提出者"},
                {"項目名": "管理職に占める女性労働者の割合", "値": "12.5", "相対年度": "提出者"},
                {"項目名": "男性労働者の育児休業取得率", "値": "80.0", "相対年度": "提出者"},
                {"項目名": "男女の賃金の差異", "値": "75.5", "相対年度": "提出者"},
            ]
        ),
        "S100PROC2": build_csv_zip(
            [
                {"項目名": "売上高", "値": "2,468", "相対年度": "当期"},
                {"項目名": "営業利益", "値": "468", "相対年度": "当期"},
                {"項目名": "当期純利益", "値": "246", "相対年度": "当期"},
                {"項目名": "従業員数", "値": "75", "相対年度": "提出者"},
                {"項目名": "管理職に占める女性労働者の割合", "値": "22.5", "相対年度": "提出者"},
                {"項目名": "男性労働者の育児休業取得率", "値": "70.0", "相対年度": "提出者"},
                {"項目名": "男女の賃金の差異", "値": "78.5", "相対年度": "提出者"},
            ]
        ),
    }
    monkeypatch.setattr("edinet_pipeline.jobs.EdinetClient", FakeClient)
    assert main(["fetch", "--date", "2024-03-29"]) == 0
    assert main(["process", "--limit", "10"]) == 0


def parquet_row_count(dataset_path: Path) -> int:
    frame = pd.read_parquet(dataset_path)
    return int(len(frame))


@pytest.mark.integration
def test_export_analytics_writes_both_outputs(
    db_connection: psycopg2.extensions.connection,
    pipeline_env: None,
    analytics_output_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seed_processed_dataset(monkeypatch)

    assert main(["export-analytics", "--format", "both"]) == 0

    parquet_root = analytics_output_dir / "parquet"
    duckdb_path = analytics_output_dir / "edinet_analytics.duckdb"
    assert (parquet_root / "company_year_metrics").is_dir()
    assert (parquet_root / "metric_evidence").is_dir()
    assert duckdb_path.is_file()

    postgres_company_year_count = fetch_one(
        db_connection, "SELECT COUNT(*) FROM vw_company_year_metrics"
    )[0]
    postgres_evidence_count = fetch_one(db_connection, "SELECT COUNT(*) FROM metric_evidence")[0]

    duckdb_connection = duckdb.connect(str(duckdb_path))
    try:
        assert (
            duckdb_connection.execute(
                "SELECT COUNT(*) FROM analytics.company_year_metrics"
            ).fetchone()[0]
            == postgres_company_year_count
        )
        assert (
            duckdb_connection.execute(
                "SELECT COUNT(*) FROM analytics.metric_evidence"
            ).fetchone()[0]
            == postgres_evidence_count
        )
        company_year_columns = [
            row[1]
            for row in duckdb_connection.execute(
                "PRAGMA table_info('analytics.company_year_metrics')"
            ).fetchall()
        ]
    finally:
        duckdb_connection.close()

    assert company_year_columns == [
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


@pytest.mark.integration
def test_export_analytics_is_idempotent(
    pipeline_env: None,
    analytics_output_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seed_processed_dataset(monkeypatch)

    assert main(["export-analytics", "--format", "both"]) == 0
    parquet_root = analytics_output_dir / "parquet"
    duckdb_path = analytics_output_dir / "edinet_analytics.duckdb"

    first_company_year_parquet_rows = parquet_row_count(parquet_root / "company_year_metrics")
    first_evidence_parquet_rows = parquet_row_count(parquet_root / "metric_evidence")
    first_duckdb = duckdb.connect(str(duckdb_path))
    try:
        first_company_year_duckdb_rows = first_duckdb.execute(
            "SELECT COUNT(*) FROM analytics.company_year_metrics"
        ).fetchone()[0]
        first_evidence_duckdb_rows = first_duckdb.execute(
            "SELECT COUNT(*) FROM analytics.metric_evidence"
        ).fetchone()[0]
    finally:
        first_duckdb.close()

    assert main(["export-analytics", "--format", "both"]) == 0

    second_company_year_parquet_rows = parquet_row_count(parquet_root / "company_year_metrics")
    second_evidence_parquet_rows = parquet_row_count(parquet_root / "metric_evidence")
    second_duckdb = duckdb.connect(str(duckdb_path))
    try:
        second_company_year_duckdb_rows = second_duckdb.execute(
            "SELECT COUNT(*) FROM analytics.company_year_metrics"
        ).fetchone()[0]
        second_evidence_duckdb_rows = second_duckdb.execute(
            "SELECT COUNT(*) FROM analytics.metric_evidence"
        ).fetchone()[0]
    finally:
        second_duckdb.close()

    assert first_company_year_parquet_rows == second_company_year_parquet_rows
    assert first_evidence_parquet_rows == second_evidence_parquet_rows
    assert first_company_year_duckdb_rows == second_company_year_duckdb_rows
    assert first_evidence_duckdb_rows == second_evidence_duckdb_rows


@pytest.mark.integration
def test_export_analytics_duckdb_only(
    pipeline_env: None,
    analytics_output_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seed_processed_dataset(monkeypatch)

    assert main(["export-analytics", "--format", "duckdb"]) == 0

    assert (analytics_output_dir / "edinet_analytics.duckdb").is_file()
    assert not (analytics_output_dir / "parquet").exists()


@pytest.mark.integration
def test_export_analytics_parquet_only(
    pipeline_env: None,
    analytics_output_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seed_processed_dataset(monkeypatch)

    assert main(["export-analytics", "--format", "parquet"]) == 0

    assert (analytics_output_dir / "parquet" / "company_year_metrics").is_dir()
    assert (analytics_output_dir / "parquet" / "metric_evidence").is_dir()
    assert not (analytics_output_dir / "edinet_analytics.duckdb").exists()
