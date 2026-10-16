from __future__ import annotations

from contextlib import contextmanager
from datetime import date
from typing import Any

import pytest

import edinet_pipeline.jobs as jobs
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


def build_document_payload(**overrides: Any) -> dict[str, Any]:
    payload = {
        "docID": "S100AAAA",
        "edinetCode": "E00001",
        "filerName": "Example Company",
        "submitDateTime": "2024-03-29 09:00",
        "periodEnd": "2024-03-31",
        "csvFlag": "1",
        "ordinanceCode": "010",
        "formCode": "030000",
        "docDescription": "有価証券報告書－第10期(2023/04/01－2024/03/31)",
    }
    payload.update(overrides)
    return payload


class StubConnection:
    def __init__(self) -> None:
        self.commits = 0

    def commit(self) -> None:
        self.commits += 1


class StubRepository:
    instances: list[StubRepository] = []

    def __init__(self, connection: StubConnection) -> None:
        self.connection = connection
        self.companies: list[tuple[str, str]] = []
        self.documents: list[Any] = []
        type(self).instances.append(self)

    @classmethod
    def reset(cls) -> None:
        cls.instances = []

    def upsert_company(self, edinet_code: str, filer_name: str) -> None:
        self.companies.append((edinet_code, filer_name))

    def upsert_document(self, document: Any) -> None:
        self.documents.append(document)


def test_parse_api_date_extracts_date_from_api_value() -> None:
    assert jobs._parse_api_date("2024-03-29 09:00") == date(2024, 3, 29)


def test_parse_api_date_rejects_invalid_value() -> None:
    with pytest.raises(ValueError, match="Invalid date value"):
        jobs._parse_api_date("not-a-date")


def test_derive_fiscal_year_prefers_period_end() -> None:
    fiscal_year = jobs.derive_fiscal_year(
        build_document_payload(periodEnd="2023-12-31", submitDateTime="2024-03-29 09:00")
    )

    assert fiscal_year == 2023


def test_derive_fiscal_year_falls_back_to_submit_datetime() -> None:
    fiscal_year = jobs.derive_fiscal_year(
        build_document_payload(periodEnd="", submitDateTime="2024-03-29 09:00")
    )

    assert fiscal_year == 2024


def test_derive_fiscal_year_raises_when_dates_are_missing() -> None:
    with pytest.raises(ValueError, match="Could not derive fiscal year"):
        jobs.derive_fiscal_year(build_document_payload(periodEnd="", submitDateTime=""))


def test_derive_submitted_date_requires_submit_datetime() -> None:
    with pytest.raises(ValueError, match="submitDateTime is missing"):
        jobs.derive_submitted_date(build_document_payload(submitDateTime=""))


def test_build_document_record_maps_fields_and_csv_flag() -> None:
    record = jobs.build_document_record(build_document_payload(csvFlag="0"))

    assert record.doc_id == "S100AAAA"
    assert record.edinet_code == "E00001"
    assert record.filer_name == "Example Company"
    assert record.submitted_date == date(2024, 3, 29)
    assert record.fiscal_year == 2024
    assert record.csv_available is False
    assert record.source_metadata["docID"] == "S100AAAA"


def test_fetch_documents_for_date_filters_missing_keys_and_counts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = make_settings()
    connection = StubConnection()
    StubRepository.reset()

    @contextmanager
    def fake_db_connection(database_url: str):
        assert database_url == settings.database_url
        yield connection

    class FakeClient:
        instances: list[FakeClient] = []

        def __init__(self, current_settings: Settings) -> None:
            self.settings = current_settings
            self.closed = False
            type(self).instances.append(self)

        def fetch_documents(self, target_date: str) -> dict[str, Any]:
            assert target_date == "2024-03-29"
            return {
                "metadata": {"resultset": {"count": 4}},
                "results": [
                    build_document_payload(docID="S100PEND", csvFlag="1"),
                    build_document_payload(docID="S100SKIP", csvFlag="0"),
                    build_document_payload(docID="S100MISS", filerName=""),
                    build_document_payload(docID="S100IGNORE", formCode="043000"),
                ],
            }

        def close(self) -> None:
            self.closed = True

    monkeypatch.setattr(jobs, "db_connection", fake_db_connection)
    monkeypatch.setattr(jobs, "PipelineRepository", StubRepository)

    summary = jobs.fetch_documents_for_date(settings, date(2024, 3, 29), client_cls=FakeClient)

    repository = StubRepository.instances[0]
    inserted_doc_ids = [document.doc_id for document in repository.documents]

    assert summary == {
        "total_results": 4,
        "matched_reports": 2,
        "pending_count": 1,
        "skipped_count": 1,
    }
    assert repository.companies == [
        ("E00001", "Example Company"),
        ("E00001", "Example Company"),
    ]
    assert inserted_doc_ids == ["S100PEND", "S100SKIP"]
    assert connection.commits == 1
    assert len(FakeClient.instances) == 1
    assert FakeClient.instances[0].closed is True


def test_fetch_documents_for_date_closes_client_when_fetch_fails() -> None:
    settings = make_settings()

    class FailingClient:
        last_instance: FailingClient | None = None

        def __init__(self, current_settings: Settings) -> None:
            self.settings = current_settings
            self.closed = False
            type(self).last_instance = self

        def fetch_documents(self, target_date: str) -> dict[str, Any]:
            raise RuntimeError("upstream failure")

        def close(self) -> None:
            self.closed = True

    with pytest.raises(RuntimeError, match="upstream failure"):
        jobs.fetch_documents_for_date(settings, date(2024, 3, 29), client_cls=FailingClient)

    assert FailingClient.last_instance is not None
    assert FailingClient.last_instance.closed is True


def test_import_local_document_upserts_without_api(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """手元 ZIP が会社・書類・指標の upsert まで走る (API を呼ばない)."""
    import io
    import zipfile

    import pandas as pd

    frame = pd.DataFrame([{"項目名": "売上高", "値": "1,234", "相対年度": "当期"}])
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr(
            "XBRL_TO_CSV/jpcrp.csv",
            frame.to_csv(index=False, sep="\t").encode("utf-16le"),
        )
    zip_path = tmp_path / "S100LOCAL.zip"
    zip_path.write_bytes(buffer.getvalue())

    settings = make_settings()
    connection = StubConnection()
    StubRepository.reset()

    @contextmanager
    def fake_db_connection(_database_url: str):
        yield connection

    class ImportRepo(StubRepository):
        def __init__(self, conn: StubConnection) -> None:
            super().__init__(conn)
            self.processed: list[str] = []
            self.human: list[str] = []

        def replace_raw_facts(self, doc_id: str, raw_facts: Any) -> None:
            return None

        def mark_processed(self, doc_id: str, parsed: Any) -> None:
            self.processed.append(doc_id)

        def delete_human_metrics_for_doc(
            self, *, doc_id: str, source_name: str = "EDINET_CSV"
        ) -> None:
            return None

        def upsert_human_metrics(
            self,
            *,
            doc_id: str,
            edinet_code: str,
            fiscal_year: int,
            parsed: Any,
            source_name: str = "EDINET_CSV",
        ) -> int:
            self.human.append(doc_id)
            return 0

        def replace_metric_evidence(self, doc_id: str, evidence: Any) -> None:
            return None

        def replace_financial_statement(self, **_kwargs: Any) -> None:
            return None

    monkeypatch.setattr(jobs, "db_connection", fake_db_connection)
    monkeypatch.setattr(jobs, "PipelineRepository", ImportRepo)

    jobs.import_local_document(
        settings,
        zip_path=zip_path,
        doc_id="S100LOCAL",
        edinet_code="E00001",
        filer_name="Local Co",
        submitted_date=date(2022, 12, 21),
        fiscal_year=2022,
    )

    repo = ImportRepo.instances[0]
    assert repo.companies == [("E00001", "Local Co")]
    assert repo.documents[0].doc_id == "S100LOCAL"
    assert repo.documents[0].fiscal_year == 2022
    assert repo.processed == ["S100LOCAL"]
    assert connection.commits == 1


def test_reprocess_statements_rebuilds_only_financial_statements(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """財務諸表だけを埋め直し、総資産が取れない書類は行を消すだけにする."""
    from edinet_pipeline.models import RawFactRecord

    def fact(element_id: str, value: str) -> RawFactRecord:
        return RawFactRecord(
            source_file="jpcrp.csv",
            row_number=1,
            element_id=element_id,
            item_name=None,
            context_id="CurrentYearInstant",
            relative_year="当期末",
            consolidation_type="連結",
            period_type=None,
            unit_id="JPY",
            unit_label=None,
            raw_value=value,
        )

    settings = make_settings()

    class StatementConnection(StubConnection):
        def rollback(self) -> None:
            return None

    connection = StatementConnection()
    StubRepository.reset()

    @contextmanager
    def fake_db_connection(_database_url: str):
        yield connection

    class StatementRepo(StubRepository):
        def __init__(self, conn: StubConnection) -> None:
            super().__init__(conn)
            self.context_filters: list[Any] = []
            self.written: list[tuple[str, Any]] = []

        def fetch_reprocessable_documents(self, *, limit: int | None = None) -> list[dict]:
            return [
                {"doc_id": "S100BS", "edinet_code": "E00001", "fiscal_year": 2025},
                {"doc_id": "S100NONE", "edinet_code": "E00002", "fiscal_year": 2025},
            ]

        def fetch_raw_facts(self, doc_id: str, *, context_ids: Any = None) -> list[RawFactRecord]:
            self.context_filters.append(context_ids)
            if doc_id == "S100BS":
                return [fact("jppfs_cor:Assets", "1000")]
            return []

        def replace_financial_statement(self, *, doc_id: str, statement: Any, **_: Any) -> None:
            self.written.append((doc_id, statement))

        def mark_processed(self, *_args: Any) -> None:
            raise AssertionError("statements-only must not touch financial_reports")

    monkeypatch.setattr(jobs, "db_connection", fake_db_connection)
    monkeypatch.setattr(jobs, "PipelineRepository", StatementRepo)

    count = jobs.reprocess_statements(settings)

    repo = StatementRepo.instances[0]
    assert count == 1
    assert [doc_id for doc_id, _ in repo.written] == ["S100BS", "S100NONE"]
    assert repo.written[0][1].total_assets == 1000
    assert repo.written[1][1] is None
    assert all(filters == jobs.STATEMENT_CONTEXT_IDS for filters in repo.context_filters)
