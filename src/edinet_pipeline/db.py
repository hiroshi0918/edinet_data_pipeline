from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import date

import psycopg2
from psycopg2.extras import Json, RealDictCursor

from edinet_pipeline.models import DocumentRecord, MetricEvidenceRecord, ParsedDocument

PROCESSABLE_STATUSES = ("pending", "failed")


@contextmanager
def db_connection(database_url: str) -> Iterator[psycopg2.extensions.connection]:
    connection = psycopg2.connect(database_url)
    try:
        yield connection
    finally:
        connection.close()


class PipelineRepository:
    def __init__(self, connection: psycopg2.extensions.connection) -> None:
        self.connection = connection

    def upsert_company(self, edinet_code: str, company_name: str) -> None:
        with self.connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO companies (edinet_code, company_name)
                VALUES (%s, %s)
                ON CONFLICT (edinet_code) DO UPDATE SET
                    company_name = EXCLUDED.company_name
                """,
                (edinet_code, company_name),
            )

    def upsert_document(self, document: DocumentRecord) -> None:
        initial_status = "pending" if document.csv_available else "skipped"
        initial_error = None if document.csv_available else "CSV not available from EDINET"
        with self.connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO financial_reports (
                    doc_id,
                    edinet_code,
                    fiscal_year,
                    status,
                    retry_count,
                    last_error,
                    processed_at,
                    sales,
                    operating_profit,
                    net_profit,
                    employee_count,
                    submitted_date,
                    source_metadata
                )
                VALUES (
                    %s, %s, %s, %s, 0, %s, NULL,
                    NULL, NULL, NULL, NULL, %s, %s
                )
                ON CONFLICT (doc_id) DO UPDATE SET
                    edinet_code = EXCLUDED.edinet_code,
                    fiscal_year = EXCLUDED.fiscal_year,
                    submitted_date = EXCLUDED.submitted_date,
                    source_metadata = EXCLUDED.source_metadata,
                    status = CASE
                        WHEN financial_reports.status IN ('processed', 'failed', 'processing')
                            THEN financial_reports.status
                        WHEN EXCLUDED.status = 'skipped' THEN 'skipped'
                        ELSE 'pending'
                    END,
                    last_error = CASE
                        WHEN financial_reports.status = 'failed' THEN financial_reports.last_error
                        WHEN EXCLUDED.status = 'skipped' THEN EXCLUDED.last_error
                        ELSE NULL
                    END
                """,
                (
                    document.doc_id,
                    document.edinet_code,
                    document.fiscal_year,
                    initial_status,
                    initial_error,
                    document.submitted_date,
                    Json(document.source_metadata),
                ),
            )

    def claim_documents_for_processing(
        self,
        *,
        limit: int,
        retry_failed: bool,
        submitted_date: date | None = None,
    ) -> list[dict]:
        statuses = ["pending"]
        if retry_failed:
            statuses.append("failed")

        date_filter = ""
        parameters: list[object] = [statuses]
        if submitted_date is not None:
            date_filter = "AND submitted_date = %s"
            parameters.append(submitted_date)
        parameters.append(limit)

        with self.connection.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(
                f"""
                WITH next_docs AS (
                    SELECT doc_id
                    FROM financial_reports
                    WHERE status = ANY(%s)
                    {date_filter}
                    ORDER BY submitted_date, doc_id
                    LIMIT %s
                    FOR UPDATE SKIP LOCKED
                )
                UPDATE financial_reports AS fr
                SET status = 'processing',
                    last_error = NULL
                FROM next_docs
                WHERE fr.doc_id = next_docs.doc_id
                RETURNING
                    fr.doc_id,
                    fr.edinet_code,
                    fr.fiscal_year,
                    fr.submitted_date,
                    fr.source_metadata
                """,
                parameters,
            )
            return list(cursor.fetchall())

    def mark_processed(self, doc_id: str, parsed: ParsedDocument) -> None:
        with self.connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE financial_reports
                SET sales = %s,
                    operating_profit = %s,
                    net_profit = %s,
                    employee_count = %s,
                    status = 'processed',
                    last_error = NULL,
                    processed_at = CURRENT_TIMESTAMP
                WHERE doc_id = %s
                """,
                (
                    parsed.financial_metrics["sales"],
                    parsed.financial_metrics["operating_profit"],
                    parsed.financial_metrics["net_profit"],
                    parsed.financial_metrics["employee_count"],
                    doc_id,
                ),
            )

    def mark_failed(self, doc_id: str, reason: str) -> None:
        with self.connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE financial_reports
                SET status = 'failed',
                    retry_count = retry_count + 1,
                    last_error = LEFT(%s, 1000),
                    processed_at = NULL
                WHERE doc_id = %s
                """,
                (reason, doc_id),
            )

    def reset_to_pending(self, doc_id: str, reason: str) -> None:
        with self.connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE financial_reports
                SET status = 'pending',
                    last_error = LEFT(%s, 1000)
                WHERE doc_id = %s
                """,
                (reason, doc_id),
            )

    def mark_skipped(self, doc_id: str, reason: str) -> None:
        with self.connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE financial_reports
                SET status = 'skipped',
                    last_error = LEFT(%s, 1000),
                    processed_at = CURRENT_TIMESTAMP
                WHERE doc_id = %s
                """,
                (reason, doc_id),
            )

    def upsert_human_metrics(
        self,
        *,
        edinet_code: str,
        fiscal_year: int,
        parsed: ParsedDocument,
        source_name: str = "EDINET_CSV",
    ) -> None:
        if all(value is None for value in parsed.human_metrics.values()):
            return

        with self.connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO human_capital_metrics (
                    edinet_code,
                    fiscal_year,
                    female_manager_ratio,
                    male_childcare_leave_ratio,
                    gender_wage_gap,
                    source_name
                )
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (edinet_code, fiscal_year, source_name) DO UPDATE SET
                    female_manager_ratio = EXCLUDED.female_manager_ratio,
                    male_childcare_leave_ratio = EXCLUDED.male_childcare_leave_ratio,
                    gender_wage_gap = EXCLUDED.gender_wage_gap
                """,
                (
                    edinet_code,
                    fiscal_year,
                    parsed.human_metrics["female_manager_ratio"],
                    parsed.human_metrics["male_childcare_leave_ratio"],
                    parsed.human_metrics["gender_wage_gap"],
                    source_name,
                ),
            )

    def replace_metric_evidence(self, doc_id: str, evidence: list[MetricEvidenceRecord]) -> None:
        with self.connection.cursor() as cursor:
            cursor.execute("DELETE FROM metric_evidence WHERE doc_id = %s", (doc_id,))
            if not evidence:
                return
            cursor.executemany(
                """
                INSERT INTO metric_evidence (
                    doc_id,
                    metric_name,
                    item_name,
                    raw_value,
                    relative_year,
                    source_file,
                    matched_by
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                [
                    (
                        doc_id,
                        record.metric_name,
                        record.item_name,
                        record.raw_value,
                        record.relative_year,
                        record.source_file,
                        record.matched_by,
                    )
                    for record in evidence
                ],
            )

    def fetch_company_year_metrics_rows(self) -> list[dict]:
        with self.connection.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(
                """
                SELECT
                    edinet_code,
                    company_name,
                    fiscal_year,
                    doc_id,
                    submitted_date,
                    status,
                    sales,
                    operating_profit,
                    net_profit,
                    employee_count,
                    female_manager_ratio,
                    male_childcare_leave_ratio,
                    gender_wage_gap,
                    source_name
                FROM vw_company_year_metrics
                ORDER BY fiscal_year, edinet_code, doc_id
                """
            )
            return list(cursor.fetchall())

    def fetch_metric_evidence_rows(self) -> list[dict]:
        with self.connection.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(
                """
                SELECT
                    fr.doc_id,
                    fr.edinet_code,
                    c.company_name,
                    fr.fiscal_year,
                    fr.submitted_date,
                    fr.status AS report_status,
                    me.metric_name,
                    me.item_name,
                    me.raw_value,
                    me.relative_year,
                    me.source_file,
                    me.matched_by
                FROM metric_evidence me
                JOIN financial_reports fr
                  ON fr.doc_id = me.doc_id
                JOIN companies c
                  ON c.edinet_code = fr.edinet_code
                ORDER BY fr.fiscal_year, fr.edinet_code, fr.doc_id, me.metric_name, me.item_name
                """
            )
            return list(cursor.fetchall())
