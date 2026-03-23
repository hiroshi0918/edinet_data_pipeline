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
