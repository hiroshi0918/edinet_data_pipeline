from __future__ import annotations

import io
import zipfile
from decimal import Decimal

import pandas as pd
import psycopg2
import pytest

from edinet_pipeline.cli import main
from edinet_pipeline.client import CsvUnavailableError, EdinetApiError


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
    interrupt_after: int | None = None
    download_calls: int = 0

    def __init__(self, settings) -> None:
        self.settings = settings

    @classmethod
    def reset(cls) -> None:
        cls.documents_by_date = {}
        cls.downloads = {}
        cls.interrupt_after = None
        cls.download_calls = 0

    def close(self) -> None:
        return None

    def fetch_documents(self, target_date: str) -> dict[str, object]:
        documents = self.documents_by_date.get(target_date, [])
        return {
            "metadata": {"resultset": {"count": len(documents)}},
            "results": documents,
        }

    def download_document_csv(self, doc_id: str) -> bytes:
        type(self).download_calls += 1
        if self.interrupt_after is not None and type(self).download_calls > self.interrupt_after:
            raise KeyboardInterrupt()

        payload = self.downloads[doc_id]
        if isinstance(payload, Exception):
            raise payload
        return payload


@pytest.fixture(autouse=True)
def reset_fake_client() -> None:
    FakeClient.reset()


def fetch_one(connection: psycopg2.extensions.connection, query: str, params: tuple = ()) -> tuple:
    with connection.cursor() as cursor:
        cursor.execute(query, params)
        return cursor.fetchone()


@pytest.mark.integration
def test_fetch_is_idempotent(
    db_connection: psycopg2.extensions.connection,
    pipeline_env: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    FakeClient.documents_by_date["2024-03-29"] = [
        build_document(doc_id="S100AAAA", edinet_code="E00001", submit_date="2024-03-29"),
        {
            **build_document(
                doc_id="S100IGNORED",
                edinet_code="E99999",
                submit_date="2024-03-29",
            ),
            "formCode": "043000",
            "docDescription": "四半期報告書－第1四半期",
        },
    ]
    monkeypatch.setattr("edinet_pipeline.jobs.EdinetClient", FakeClient)

    assert main(["fetch", "--date", "2024-03-29"]) == 0
    assert main(["fetch", "--date", "2024-03-29"]) == 0

    assert fetch_one(db_connection, "SELECT COUNT(*) FROM financial_reports")[0] == 1
    assert fetch_one(db_connection, "SELECT COUNT(*) FROM companies")[0] == 1
    assert (
        fetch_one(
            db_connection, "SELECT status FROM financial_reports WHERE doc_id = %s", ("S100AAAA",)
        )[0]
        == "pending"
    )


@pytest.mark.integration
def test_process_sets_processed_skipped_failed_and_upserts_human_metrics(
    db_connection: psycopg2.extensions.connection,
    pipeline_env: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    document_date = "2024-03-29"
    documents = [
        build_document(doc_id="S100PROC1", edinet_code="E00001", submit_date=document_date),
        build_document(doc_id="S100SKIP1", edinet_code="E00002", submit_date=document_date),
        build_document(doc_id="S100FAIL1", edinet_code="E00003", submit_date=document_date),
    ]
    FakeClient.documents_by_date[document_date] = documents
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
        "S100SKIP1": CsvUnavailableError("CSV not available from EDINET for S100SKIP1"),
        "S100FAIL1": EdinetApiError("download exploded"),
    }
    monkeypatch.setattr("edinet_pipeline.jobs.EdinetClient", FakeClient)

    assert main(["fetch", "--date", document_date]) == 0
    assert main(["process", "--limit", "10"]) == 0

    assert (
        fetch_one(
            db_connection, "SELECT status FROM financial_reports WHERE doc_id = %s", ("S100PROC1",)
        )[0]
        == "processed"
    )
    assert (
        fetch_one(
            db_connection, "SELECT status FROM financial_reports WHERE doc_id = %s", ("S100SKIP1",)
        )[0]
        == "skipped"
    )
    assert fetch_one(
        db_connection,
        "SELECT status, retry_count FROM financial_reports WHERE doc_id = %s",
        ("S100FAIL1",),
    ) == ("failed", 1)
    assert fetch_one(db_connection, "SELECT COUNT(*) FROM human_capital_metrics")[0] == 1
    assert (
        fetch_one(
            db_connection, "SELECT COUNT(*) FROM metric_evidence WHERE doc_id = %s", ("S100PROC1",)
        )[0]
        >= 3
    )
    assert fetch_one(
        db_connection,
        "SELECT COUNT(*) FROM raw_edinet_facts WHERE doc_id = %s",
        ("S100PROC1",),
    ) == (7,)
    assert fetch_one(
        db_connection,
        """
        SELECT row_number, item_name, relative_year, raw_value
        FROM raw_edinet_facts
        WHERE doc_id = %s
        ORDER BY row_number
        LIMIT 1
        """,
        ("S100PROC1",),
    ) == (1, "売上高", "当期", "1,234")

    with db_connection.cursor() as cursor:
        cursor.execute(
            "UPDATE financial_reports SET status = 'failed' WHERE doc_id = %s",
            ("S100PROC1",),
        )
    db_connection.commit()

    FakeClient.downloads["S100PROC1"] = build_csv_zip(
        [
            {"項目名": "売上高", "値": "2,000", "相対年度": "当期"},
            {"項目名": "管理職に占める女性労働者の割合", "値": "22.0", "相対年度": "提出者"},
            {"項目名": "男性労働者の育児休業取得率", "値": "82.0", "相対年度": "提出者"},
            {"項目名": "男女の賃金の差異", "値": "76.0", "相対年度": "提出者"},
        ]
    )
    FakeClient.downloads["S100FAIL1"] = build_csv_zip(
        [{"項目名": "売上高", "値": "999", "相対年度": "当期"}]
    )

    assert main(["process", "--limit", "10", "--retry-failed"]) == 0

    human_metrics = fetch_one(
        db_connection,
        """
        SELECT female_manager_ratio, male_childcare_leave_ratio, gender_wage_gap
        FROM human_capital_metrics
        WHERE edinet_code = %s
        """,
        ("E00001",),
    )
    assert human_metrics == (Decimal("22.00"), Decimal("82.00"), Decimal("76.00"))
    assert fetch_one(db_connection, "SELECT COUNT(*) FROM human_capital_metrics")[0] == 1
    assert fetch_one(
        db_connection,
        "SELECT COUNT(*) FROM raw_edinet_facts WHERE doc_id = %s",
        ("S100PROC1",),
    ) == (4,)


def _register_pending_doc(
    monkeypatch: pytest.MonkeyPatch, *, doc_id: str, edinet_code: str, submit_date: str
) -> None:
    """fetch 経由で pending 行 (と企業マスタ) を 1 件作る共通ヘルパー.

    financial_reports.edinet_code は companies への FK を持つため、直接 INSERT せず
    fetch の upsert 経路を借りて整合的に行を用意する。
    """
    FakeClient.documents_by_date[submit_date] = [
        build_document(doc_id=doc_id, edinet_code=edinet_code, submit_date=submit_date)
    ]
    monkeypatch.setattr("edinet_pipeline.jobs.EdinetClient", FakeClient)
    assert main(["fetch", "--date", submit_date]) == 0


@pytest.mark.integration
def test_reset_stale_processing_recovers_old_rows(
    db_connection: psycopg2.extensions.connection,
    pipeline_env: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """閾値より古い processing 行だけが pending に戻り、直近の行は維持されること."""
    submit_date = "2024-03-29"
    FakeClient.documents_by_date[submit_date] = [
        build_document(doc_id="S100OLD", edinet_code="E00001", submit_date=submit_date),
        build_document(doc_id="S100NEW", edinet_code="E00002", submit_date=submit_date),
    ]
    monkeypatch.setattr("edinet_pipeline.jobs.EdinetClient", FakeClient)
    assert main(["fetch", "--date", submit_date]) == 0

    # 片方は 2 時間前 (stale)、片方は直近 (in-flight) の processing に仕立てる
    with db_connection.cursor() as cursor:
        cursor.execute(
            """
            UPDATE financial_reports
            SET status = 'processing',
                processing_started_at = CURRENT_TIMESTAMP - INTERVAL '2 hours'
            WHERE doc_id = 'S100OLD'
            """
        )
        cursor.execute(
            """
            UPDATE financial_reports
            SET status = 'processing', processing_started_at = CURRENT_TIMESTAMP
            WHERE doc_id = 'S100NEW'
            """
        )

    # 既定閾値 (STALE_PROCESSING_MINUTES 未設定なら 60 分) で復旧
    assert main(["reset-stale"]) == 0

    old_status, old_started_at, old_error = fetch_one(
        db_connection,
        "SELECT status, processing_started_at, last_error "
        "FROM financial_reports WHERE doc_id = %s",
        ("S100OLD",),
    )
    assert old_status == "pending"
    assert old_started_at is None
    assert old_error.startswith("Auto-recovered from stale processing")

    # 直近の in-flight 行は誤回収されない
    assert (
        fetch_one(
            db_connection, "SELECT status FROM financial_reports WHERE doc_id = %s", ("S100NEW",)
        )[0]
        == "processing"
    )


@pytest.mark.integration
def test_reset_stale_processing_recovers_null_started_at(
    db_connection: psycopg2.extensions.connection,
    pipeline_env: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """processing_started_at が NULL の行 (マイグレーション前の残骸) も回収されること."""
    submit_date = "2024-03-29"
    _register_pending_doc(
        monkeypatch, doc_id="S100NULL", edinet_code="E00001", submit_date=submit_date
    )
    with db_connection.cursor() as cursor:
        cursor.execute(
            """
            UPDATE financial_reports
            SET status = 'processing', processing_started_at = NULL
            WHERE doc_id = 'S100NULL'
            """
        )

    assert main(["reset-stale", "--minutes", "60"]) == 0

    assert fetch_one(
        db_connection,
        "SELECT status, processing_started_at FROM financial_reports WHERE doc_id = %s",
        ("S100NULL",),
    ) == ("pending", None)


@pytest.mark.integration
def test_claim_sets_processing_started_at(
    db_connection: psycopg2.extensions.connection,
    pipeline_env: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """claim_documents_for_processing が processing_started_at を記録すること."""
    from edinet_pipeline.db import PipelineRepository

    _register_pending_doc(
        monkeypatch, doc_id="S100CLAIM", edinet_code="E00001", submit_date="2024-03-29"
    )

    # db_connection は autocommit のため claim の UPDATE は即時反映される
    repository = PipelineRepository(db_connection)
    claimed = repository.claim_documents_for_processing(limit=10, retry_failed=False)
    assert [row["doc_id"] for row in claimed] == ["S100CLAIM"]

    status, started_at = fetch_one(
        db_connection,
        "SELECT status, processing_started_at FROM financial_reports WHERE doc_id = %s",
        ("S100CLAIM",),
    )
    assert status == "processing"
    assert started_at is not None


@pytest.mark.integration
def test_process_auto_recovers_stale_rows(
    db_connection: psycopg2.extensions.connection,
    pipeline_env: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """process が claim 直前に stale 行を回収し、再 claim → 処理まで完遂すること."""
    submit_date = "2024-03-29"
    FakeClient.documents_by_date[submit_date] = [
        build_document(doc_id="S100STALE", edinet_code="E00001", submit_date=submit_date)
    ]
    FakeClient.downloads = {
        "S100STALE": build_csv_zip([{"項目名": "売上高", "値": "100", "相対年度": "当期"}]),
    }
    monkeypatch.setattr("edinet_pipeline.jobs.EdinetClient", FakeClient)
    assert main(["fetch", "--date", submit_date]) == 0

    # 2 時間前から processing のまま停滞している行を仕込む
    with db_connection.cursor() as cursor:
        cursor.execute(
            """
            UPDATE financial_reports
            SET status = 'processing',
                processing_started_at = CURRENT_TIMESTAMP - INTERVAL '2 hours'
            WHERE doc_id = 'S100STALE'
            """
        )

    assert main(["process", "--limit", "10"]) == 0

    status, started_at = fetch_one(
        db_connection,
        "SELECT status, processing_started_at FROM financial_reports WHERE doc_id = %s",
        ("S100STALE",),
    )
    # 復旧 → 再 claim → 処理成功。終端状態では started_at は NULL に戻る
    assert status == "processed"
    assert started_at is None


@pytest.mark.integration
def test_backfill_can_resume_after_interrupt(
    db_connection: psycopg2.extensions.connection,
    pipeline_env: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    FakeClient.documents_by_date = {
        "2024-03-29": [
            build_document(doc_id="S100DAY01", edinet_code="E00011", submit_date="2024-03-29")
        ],
        "2024-03-30": [
            build_document(doc_id="S100DAY02", edinet_code="E00012", submit_date="2024-03-30")
        ],
    }
    FakeClient.downloads = {
        "S100DAY01": build_csv_zip([{"項目名": "売上高", "値": "100", "相対年度": "当期"}]),
        "S100DAY02": build_csv_zip([{"項目名": "売上高", "値": "200", "相対年度": "当期"}]),
    }
    FakeClient.interrupt_after = 1
    monkeypatch.setattr("edinet_pipeline.jobs.EdinetClient", FakeClient)

    with pytest.raises(KeyboardInterrupt):
        main(
            [
                "backfill",
                "--from",
                "2024-03-29",
                "--to",
                "2024-03-30",
                "--process-limit",
                "10",
            ]
        )

    assert (
        fetch_one(
            db_connection, "SELECT status FROM financial_reports WHERE doc_id = %s", ("S100DAY01",)
        )[0]
        == "processed"
    )
    assert (
        fetch_one(
            db_connection, "SELECT status FROM financial_reports WHERE doc_id = %s", ("S100DAY02",)
        )[0]
        == "pending"
    )

    FakeClient.interrupt_after = None
    assert (
        main(
            [
                "backfill",
                "--from",
                "2024-03-29",
                "--to",
                "2024-03-30",
                "--process-limit",
                "10",
            ]
        )
        == 0
    )

    assert (
        fetch_one(
            db_connection, "SELECT COUNT(*) FROM financial_reports WHERE status = 'processed'"
        )[0]
        == 2
    )
