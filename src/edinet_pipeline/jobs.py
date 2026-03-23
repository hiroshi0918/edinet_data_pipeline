from __future__ import annotations

import logging
import re
import time
from datetime import date, datetime, timedelta
from typing import Any

from edinet_pipeline.client import CsvUnavailableError, EdinetApiError, EdinetClient
from edinet_pipeline.config import Settings
from edinet_pipeline.db import PipelineRepository, db_connection
from edinet_pipeline.extractors import parse_document_zip
from edinet_pipeline.logging_utils import log_event
from edinet_pipeline.models import DocumentRecord

logger = logging.getLogger(__name__)


def _parse_api_date(raw_value: str) -> date:
    match = re.search(r"\d{4}-\d{2}-\d{2}", raw_value)
    if not match:
        raise ValueError(f"Invalid date value from EDINET API: {raw_value}")
    return datetime.strptime(match.group(), "%Y-%m-%d").date()


def derive_fiscal_year(document: dict[str, Any]) -> int:
    period_end = str(document.get("periodEnd") or "").strip()
    if period_end:
        return _parse_api_date(period_end).year

    submit_datetime = str(document.get("submitDateTime") or "").strip()
    if submit_datetime:
        return _parse_api_date(submit_datetime).year

    raise ValueError(f"Could not derive fiscal year for document {document.get('docID')}")


def derive_submitted_date(document: dict[str, Any]) -> date:
    submit_datetime = str(document.get("submitDateTime") or "").strip()
    if not submit_datetime:
        raise ValueError(f"submitDateTime is missing for document {document.get('docID')}")
    return _parse_api_date(submit_datetime)


def build_document_record(document: dict[str, Any]) -> DocumentRecord:
    return DocumentRecord(
        doc_id=str(document["docID"]),
        edinet_code=str(document["edinetCode"]),
        filer_name=str(document["filerName"]),
        submitted_date=derive_submitted_date(document),
        fiscal_year=derive_fiscal_year(document),
        csv_available=str(document.get("csvFlag", "0")) == "1",
        source_metadata=document,
    )


def fetch_documents_for_date(
    settings: Settings,
    target_date: date,
    client_cls: type[EdinetClient] | None = None,
) -> dict[str, int]:
    client_cls = client_cls or EdinetClient
    client = client_cls(settings)
    try:
        payload = client.fetch_documents(target_date.isoformat())
    finally:
        client.close()

    results = payload.get("results", [])
    matched_reports = 0
    pending_count = 0
    skipped_count = 0

    with db_connection(settings.database_url) as connection:
        repository = PipelineRepository(connection)
        for document in results:
            if not settings.filing_filters.matches(document):
                continue
            if (
                not document.get("edinetCode")
                or not document.get("docID")
                or not document.get("filerName")
            ):
                continue

            record = build_document_record(document)
            repository.upsert_company(record.edinet_code, record.filer_name)
            repository.upsert_document(record)
            matched_reports += 1
            pending_count += int(record.csv_available)
            skipped_count += int(not record.csv_available)

        connection.commit()

    summary = {
        "total_results": int(
            payload.get("metadata", {}).get("resultset", {}).get("count", len(results))
        ),
        "matched_reports": matched_reports,
        "pending_count": pending_count,
        "skipped_count": skipped_count,
    }
    log_event(logger, "info", "fetch_completed", target_date=target_date.isoformat(), **summary)
    return summary


def process_documents(
    settings: Settings,
    *,
    limit: int,
    retry_failed: bool = False,
    submitted_date: date | None = None,
    client_cls: type[EdinetClient] | None = None,
) -> int:
    client_cls = client_cls or EdinetClient
    with db_connection(settings.database_url) as connection:
        repository = PipelineRepository(connection)
        claimed_documents = repository.claim_documents_for_processing(
            limit=limit,
            retry_failed=retry_failed,
            submitted_date=submitted_date,
        )
        connection.commit()

    if not claimed_documents:
        log_event(
            logger,
            "info",
            "process_queue_empty",
            retry_failed=retry_failed,
            submitted_date=submitted_date.isoformat() if submitted_date else None,
        )
        return 0

    client = client_cls(settings)
    try:
        for document in claimed_documents:
            started_at = time.time()
            doc_id = document["doc_id"]
            edinet_code = document["edinet_code"]
            fiscal_year = document["fiscal_year"]
            try:
                zip_bytes = client.download_document_csv(doc_id)
                parsed = parse_document_zip(zip_bytes)
                with db_connection(settings.database_url) as connection:
                    repository = PipelineRepository(connection)
                    repository.mark_processed(doc_id, parsed)
                    repository.upsert_human_metrics(
                        edinet_code=edinet_code,
                        fiscal_year=fiscal_year,
                        parsed=parsed,
                    )
                    repository.replace_metric_evidence(doc_id, parsed.evidence)
                    connection.commit()
                elapsed_ms = int((time.time() - started_at) * 1000)
                log_event(
                    logger,
                    "info",
                    "document_processed",
                    doc_id=doc_id,
                    status="processed",
                    elapsed_ms=elapsed_ms,
                    evidence_count=len(parsed.evidence),
                )
            except CsvUnavailableError as exc:
                with db_connection(settings.database_url) as connection:
                    repository = PipelineRepository(connection)
                    repository.mark_skipped(doc_id, str(exc))
                    connection.commit()
                elapsed_ms = int((time.time() - started_at) * 1000)
                log_event(
                    logger,
                    "warning",
                    "document_processed",
                    doc_id=doc_id,
                    status="skipped",
                    reason=str(exc),
                    elapsed_ms=elapsed_ms,
                )
            except EdinetApiError as exc:
                with db_connection(settings.database_url) as connection:
                    repository = PipelineRepository(connection)
                    repository.mark_failed(doc_id, str(exc))
                    connection.commit()
                elapsed_ms = int((time.time() - started_at) * 1000)
                log_event(
                    logger,
                    "error",
                    "document_processed",
                    doc_id=doc_id,
                    status="failed",
                    reason=str(exc),
                    elapsed_ms=elapsed_ms,
                )
            except Exception as exc:
                with db_connection(settings.database_url) as connection:
                    repository = PipelineRepository(connection)
                    repository.mark_failed(doc_id, str(exc))
                    connection.commit()
                elapsed_ms = int((time.time() - started_at) * 1000)
                log_event(
                    logger,
                    "error",
                    "document_processed",
                    doc_id=doc_id,
                    status="failed",
                    reason=str(exc),
                    elapsed_ms=elapsed_ms,
                )
            except BaseException as exc:
                with db_connection(settings.database_url) as connection:
                    repository = PipelineRepository(connection)
                    repository.reset_to_pending(doc_id, f"Interrupted: {exc}")
                    connection.commit()
                log_event(
                    logger,
                    "warning",
                    "document_interrupted",
                    doc_id=doc_id,
                    status="pending",
                    reason=f"Interrupted: {exc}",
                )
                raise

            if settings.process_sleep_seconds > 0:
                time.sleep(settings.process_sleep_seconds)
    finally:
        client.close()

    return len(claimed_documents)


def backfill_documents(
    settings: Settings,
    *,
    start_date: date,
    end_date: date,
    process_limit: int,
    retry_failed: bool = False,
    client_cls: type[EdinetClient] | None = None,
) -> None:
    client_cls = client_cls or EdinetClient
    current_date = start_date
    while current_date <= end_date:
        fetch_documents_for_date(settings, current_date, client_cls=client_cls)
        while True:
            processed = process_documents(
                settings,
                limit=process_limit,
                retry_failed=retry_failed,
                submitted_date=current_date,
                client_cls=client_cls,
            )
            if processed == 0:
                break
        current_date += timedelta(days=1)
