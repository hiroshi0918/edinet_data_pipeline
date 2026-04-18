"""データベースアクセス層 — PostgreSQL への CRUD 操作とパイプライン状態管理.

テーブル構成:
  companies             : 企業マスタ (edinet_code がキー)
  financial_reports     : 書類メタ + 財務指標 + 処理ステータス
  human_capital_metrics : 人的資本指標 (女性管理職比率 等)
  raw_edinet_facts      : 元CSVの生行データ
  metric_evidence       : 抽出根拠の監査証跡
  vw_company_year_metrics : 企業×年度ごとの統合ビュー (分析用)
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import date

import psycopg2
from psycopg2.extras import Json, RealDictCursor, execute_values
from psycopg2.pool import ThreadedConnectionPool

from edinet_pipeline.models import (
    DocumentRecord,
    MetricEvidenceRecord,
    ParsedDocument,
    RawFactRecord,
)

# claim_documents_for_processing で取得対象とするステータス
PROCESSABLE_STATUSES = ("pending", "failed")

# _replace_child_records で操作を許可するテーブル名の許可リスト
# テーブル名は SQL の identifier として動的展開されるため、許可外の名前を拒否して
# インジェクション経路を遮断する
_CHILD_TABLE_ALLOWLIST: frozenset[str] = frozenset({"raw_edinet_facts", "metric_evidence"})


@contextmanager
def db_connection(database_url: str) -> Iterator[psycopg2.extensions.connection]:
    """PostgreSQL コネクションのコンテキストマネージャ (自動 close).

    単発用途 (CLI サブコマンドの 1 回きり処理など) 向け。
    多数の書類をループ処理する場合は DatabasePool を使う。
    """
    connection = psycopg2.connect(database_url)
    try:
        yield connection
    finally:
        connection.close()


class DatabasePool:
    """psycopg2 の ThreadedConnectionPool を薄くラップした接続プール.

    書類ごとに connect/close を繰り返すとハンドシェイクコストが累積するため、
    process_documents のループなど反復利用では本プール経由で接続を取り回す。
    コンテキストマネージャでの取得を基本とし、例外時も自動で putconn される。
    """

    def __init__(
        self,
        database_url: str,
        *,
        min_size: int = 1,
        max_size: int = 5,
    ) -> None:
        if min_size < 0 or max_size < 1 or min_size > max_size:
            raise ValueError(
                f"Invalid pool size: min={min_size}, max={max_size}"
            )
        self._pool = ThreadedConnectionPool(min_size, max_size, database_url)

    @contextmanager
    def connection(self) -> Iterator[psycopg2.extensions.connection]:
        """プールから接続を 1 つ借り受け、ブロック終了時に返却する."""
        conn = self._pool.getconn()
        try:
            yield conn
        finally:
            # プール側で既に close されたコネクションを putconn すると例外になるため、
            # 念のため closed 判定してから返却する。
            if not conn.closed:
                self._pool.putconn(conn)
            else:
                self._pool.putconn(conn, close=True)

    def closeall(self) -> None:
        """プール内の全接続を閉じる (プロセス終了時などに呼ぶ)."""
        self._pool.closeall()


class PipelineRepository:
    """パイプラインの DB 操作を集約するリポジトリクラス.

    このクラスでは commit を行わない — トランザクション制御は呼び出し側の責務。
    """

    def __init__(self, connection: psycopg2.extensions.connection) -> None:
        self.connection = connection

    # ------------------------------------------------------------------ #
    #  企業・書類の登録 (Upsert)
    # ------------------------------------------------------------------ #

    def upsert_company(self, edinet_code: str, company_name: str) -> None:
        """企業マスタへ INSERT or UPDATE (edinet_code をキーにする)."""
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
        """書類メタデータを INSERT or UPDATE.

        ステータス遷移ルール:
          - 既に processed / failed / processing → ステータス維持
          - CSV 未提供 (csvFlag=0) → skipped
          - 上記以外 → pending (処理待ち)
        """
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

    # ------------------------------------------------------------------ #
    #  処理キューの取得と状態遷移
    # ------------------------------------------------------------------ #

    def claim_documents_for_processing(
        self,
        *,
        limit: int,
        retry_failed: bool,
        submitted_date: date | None = None,
    ) -> list[dict]:
        """処理対象の書類を SELECT FOR UPDATE SKIP LOCKED で排他取得し、
        ステータスを 'processing' に更新して返す.

        並行ワーカーが同じ書類を重複処理しないようロックベースで制御する。
        """
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
        """処理成功 — 財務指標を書き込み、ステータスを 'processed' へ."""
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
        """処理失敗 — エラー理由を記録し retry_count をインクリメント."""
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
        """中断からの復帰 — ステータスを 'pending' に戻す (SIGINT 等)."""
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
        """処理スキップ — CSV が存在しない書類などに使用."""
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

    # ------------------------------------------------------------------ #
    #  人的資本指標 / 生データ / 抽出根拠の保存
    # ------------------------------------------------------------------ #

    def upsert_human_metrics(
        self,
        *,
        edinet_code: str,
        fiscal_year: int,
        parsed: ParsedDocument,
        source_name: str = "EDINET_CSV",
    ) -> None:
        """人的資本指標を INSERT or UPDATE.

        全値が None の場合は何もしない (空レコード防止)。
        """
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

    def _replace_child_records(
        self, doc_id: str, table: str, columns: list[str], rows: list[tuple],
    ) -> None:
        """DELETE → bulk INSERT の冪等な洗い替え.

        table はクエリ文字列に動的展開されるため、許可リストで事前検証する。
        """
        if table not in _CHILD_TABLE_ALLOWLIST:
            raise ValueError(f"Disallowed child table: {table!r}")
        with self.connection.cursor() as cursor:
            cursor.execute(f"DELETE FROM {table} WHERE doc_id = %s", (doc_id,))
            if not rows:
                return
            col_list = ", ".join(columns)
            execute_values(
                cursor,
                f"INSERT INTO {table} ({col_list}) VALUES %s",
                rows,
                page_size=1000,
            )

    def replace_raw_facts(self, doc_id: str, raw_facts: list[RawFactRecord]) -> None:
        """元CSVの生行データを全削除 → 再挿入 (冪等な洗い替え方式)."""
        self._replace_child_records(
            doc_id,
            "raw_edinet_facts",
            [
                "doc_id", "source_file", "row_number", "element_id", "item_name",
                "context_id", "relative_year", "consolidation_type", "period_type",
                "unit_id", "unit_label", "raw_value",
            ],
            [
                (
                    doc_id, r.source_file, r.row_number, r.element_id, r.item_name,
                    r.context_id, r.relative_year, r.consolidation_type, r.period_type,
                    r.unit_id, r.unit_label, r.raw_value,
                )
                for r in raw_facts
            ],
        )

    def replace_metric_evidence(self, doc_id: str, evidence: list[MetricEvidenceRecord]) -> None:
        """抽出根拠を全削除 → 再挿入 (冪等な洗い替え方式)."""
        self._replace_child_records(
            doc_id,
            "metric_evidence",
            [
                "doc_id", "metric_name", "item_name", "raw_value",
                "relative_year", "source_file", "matched_by",
            ],
            [
                (
                    doc_id, r.metric_name, r.item_name, r.raw_value,
                    r.relative_year, r.source_file, r.matched_by,
                )
                for r in evidence
            ],
        )

    # ------------------------------------------------------------------ #
    #  分析レイヤー用クエリ (Read-Only)
    # ------------------------------------------------------------------ #

    def fetch_company_year_metrics_rows(self) -> list[dict]:
        """vw_company_year_metrics ビューから全行を取得 (Parquet / DuckDB 出力用)."""
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
        """metric_evidence を companies・financial_reports と JOIN して全行取得."""
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
