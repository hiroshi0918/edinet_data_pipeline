"""ジョブ層 — fetch / process / backfill の 3 つのパイプラインジョブを定義.

実行フロー:
  fetch  : EDINET API → 書類メタデータを DB 登録 (pending or skipped)
  process: pending キューから書類を取得 → CSV ZIP ダウンロード → 指標抽出 → DB 更新
  backfill: 日付範囲で fetch → process を繰り返す一括実行
"""

from __future__ import annotations

import logging
import re
import time
from datetime import date, datetime, timedelta
from typing import Any

from edinet_pipeline.client import CsvUnavailableError, EdinetClient
from edinet_pipeline.config import Settings
from edinet_pipeline.db import DatabasePool, PipelineRepository, db_connection
from edinet_pipeline.extractors import merge_llm_records, parse_document_zip
from edinet_pipeline.llm_extractor import extract_via_llm
from edinet_pipeline.logging_utils import log_event
from edinet_pipeline.models import DocumentRecord, ParsedDocument

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------ #
#  ユーティリティ: API レスポンスの日付パース
# ------------------------------------------------------------------ #

def _parse_api_date(raw_value: str) -> date:
    """文字列中から YYYY-MM-DD パターンを抽出し date に変換する."""
    match = re.search(r"\d{4}-\d{2}-\d{2}", raw_value)
    if not match:
        raise ValueError(f"Invalid date value from EDINET API: {raw_value}")
    return datetime.strptime(match.group(), "%Y-%m-%d").date()


def derive_fiscal_year(document: dict[str, Any]) -> int:
    """書類情報から決算年度 (年) を導出する.

    優先順位: periodEnd → submitDateTime
    """
    period_end = str(document.get("periodEnd") or "").strip()
    if period_end:
        return _parse_api_date(period_end).year

    submit_datetime = str(document.get("submitDateTime") or "").strip()
    if submit_datetime:
        return _parse_api_date(submit_datetime).year

    raise ValueError(f"Could not derive fiscal year for document {document.get('docID')}")


def derive_submitted_date(document: dict[str, Any]) -> date:
    """submitDateTime フィールドから提出日を取得する."""
    submit_datetime = str(document.get("submitDateTime") or "").strip()
    if not submit_datetime:
        raise ValueError(f"submitDateTime is missing for document {document.get('docID')}")
    return _parse_api_date(submit_datetime)


def build_document_record(document: dict[str, Any]) -> DocumentRecord:
    """API レスポンスの 1 書類分の dict を DocumentRecord に変換する."""
    return DocumentRecord(
        doc_id=str(document["docID"]),
        edinet_code=str(document["edinetCode"]),
        filer_name=str(document["filerName"]),
        submitted_date=derive_submitted_date(document),
        fiscal_year=derive_fiscal_year(document),
        csv_available=str(document.get("csvFlag", "0")) == "1",
        source_metadata=document,
    )


# ------------------------------------------------------------------ #
#  Job 1: fetch — 指定日の書類メタデータを取得・DB 登録
# ------------------------------------------------------------------ #

def fetch_documents_for_date(
    settings: Settings,
    target_date: date,
    client_cls: type[EdinetClient] | None = None,
) -> dict[str, int]:
    """指定日の書類一覧を EDINET API から取得し、対象書類を DB へ登録する.

    Returns:
        処理サマリ (total_results, matched_reports, pending_count, skipped_count)
    """
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
            # フィルタ条件 (有価証券報告書のみ) と必須フィールドの確認
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


# ------------------------------------------------------------------ #
#  Layer 3b: LLM フォールバック呼び出し
# ------------------------------------------------------------------ #


def _has_reporting_company_metrics(parsed: ParsedDocument) -> bool:
    """提出会社の人的資本指標が1つでも取れているか."""
    for record in parsed.human_metrics:
        if record.scope != "reporting_company":
            continue
        if (
            record.female_manager_ratio is not None
            or record.male_childcare_leave_ratio is not None
            or record.gender_wage_gap is not None
        ):
            return True
    return False


def _maybe_run_llm_fallback(
    parsed: ParsedDocument,
    *,
    settings: Settings,
    pool: DatabasePool,
) -> None:
    """Layer 1/2 で提出会社の指標が取れていない場合のみ LLM 抽出を試行する.

    LLMが無効 (settings.llm_enabled == False) なら何もしない。
    """
    if not settings.llm_enabled:
        return
    if not parsed.employee_status_text:
        return
    if _has_reporting_company_metrics(parsed):
        return  # 既に取れているので LLM 不要

    with pool.connection() as cache_conn:
        result = extract_via_llm(
            parsed.employee_status_text,
            settings=settings,
            cache_connection=cache_conn,
        )
    filled = merge_llm_records(parsed, result.records, source_file="(llm_fallback)")
    log_event(
        logger, "info", "llm_fallback_executed",
        cache_hit=result.cache_hit, fields_filled=filled,
        records=len(result.records),
    )


# ------------------------------------------------------------------ #
#  Job 2: process — キュー内の書類を順次ダウンロード・解析
# ------------------------------------------------------------------ #

def _record_terminal_state(
    pool: DatabasePool,
    *,
    doc_id: str,
    status: str,
    reason: str,
    started_at: float,
    log_level: str,
) -> None:
    """書類の最終状態 (skipped / failed) を 1 トランザクションで記録し、ログ出力する.

    Args:
        pool: コネクションプール
        doc_id: 対象書類 ID
        status: "skipped" or "failed"
        reason: DB に記録する失敗理由 (last_error)
        started_at: 経過時間計測の起点 (time.time() の値)
        log_level: log_event に渡すログレベル ("warning" / "error" 等)
    """
    with pool.connection() as connection:
        repository = PipelineRepository(connection)
        if status == "skipped":
            repository.mark_skipped(doc_id, reason)
        else:
            repository.mark_failed(doc_id, reason)
        connection.commit()
    elapsed_ms = int((time.time() - started_at) * 1000)
    log_event(
        logger,
        log_level,
        "document_processed",
        doc_id=doc_id,
        status=status,
        reason=reason,
        elapsed_ms=elapsed_ms,
    )


def _record_interruption(pool: DatabasePool, *, doc_id: str, reason: str) -> None:
    """SIGINT 等の中断発生時に書類を pending へ戻し、中断ログを出力する.

    呼び出し側は本関数を呼んだあと **必ず例外を再 raise** すること
    (BaseException を握りつぶしてはいけない)。
    """
    with pool.connection() as connection:
        repository = PipelineRepository(connection)
        repository.reset_to_pending(doc_id, reason)
        connection.commit()
    log_event(
        logger,
        "warning",
        "document_interrupted",
        doc_id=doc_id,
        status="pending",
        reason=reason,
    )


def process_documents(
    settings: Settings,
    *,
    limit: int,
    retry_failed: bool = False,
    submitted_date: date | None = None,
    client_cls: type[EdinetClient] | None = None,
) -> int:
    """pending (+ オプションで failed) の書類を取得し、CSV 解析・DB 更新を行う.

    処理フロー (1 書類あたり):
      1. CSV ZIP をダウンロード
      2. parse_document_zip で財務指標 + 人的資本指標を抽出
      3. DB に結果を書き込み (processed / skipped / failed)

    例外時の遷移先:
      - CsvUnavailableError      → skipped
      - その他の Exception 派生   → failed (EdinetApiError を含む)
      - BaseException (SIGINT 等) → pending に戻し、再 raise する

    Returns:
        処理した書類数
    """
    client_cls = client_cls or EdinetClient

    # ループ内で書類ごとに接続を張り直すと PostgreSQL ハンドシェイクのコストが累積するため、
    # プールから接続を借り受ける方式に切り替える。
    pool = DatabasePool(
        settings.database_url,
        min_size=settings.db_pool_min_size,
        max_size=settings.db_pool_max_size,
    )
    try:
        with pool.connection() as connection:
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
                    # CSV ZIP ダウンロード → 指標抽出 → (必要なら) LLM フォールバック
                    zip_bytes = client.download_document_csv(doc_id)
                    parsed = parse_document_zip(
                        zip_bytes, max_ratio=settings.human_metric_max_ratio
                    )
                    _maybe_run_llm_fallback(parsed, settings=settings, pool=pool)

                    with pool.connection() as connection:
                        repository = PipelineRepository(connection)
                        repository.replace_raw_facts(doc_id, parsed.raw_facts)
                        repository.mark_processed(doc_id, parsed)
                        # 既存の人的資本レコードを全消去 → 新次元で再upsert (整合性確保)
                        repository.delete_human_metrics_for_doc(
                            edinet_code=edinet_code, fiscal_year=fiscal_year,
                        )
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
                    # CSV が存在しない書類 → skipped に遷移 (warning ログ)
                    _record_terminal_state(
                        pool,
                        doc_id=doc_id,
                        status="skipped",
                        reason=str(exc),
                        started_at=started_at,
                        log_level="warning",
                    )
                except Exception as exc:
                    # API エラー (EdinetApiError) や予期しない例外を一括で failed 扱いにする。
                    # mark_failed 側で retry_count をインクリメントするため、
                    # `--retry-failed` で再試行可能。
                    _record_terminal_state(
                        pool,
                        doc_id=doc_id,
                        status="failed",
                        reason=str(exc),
                        started_at=started_at,
                        log_level="error",
                    )
                except BaseException as exc:
                    # SIGINT / SystemExit → pending に戻して中断を安全に処理し、必ず再 raise する。
                    # 再 raise しないと SIGINT が握りつぶされ、ユーザの停止指示が無視されてしまう。
                    _record_interruption(pool, doc_id=doc_id, reason=f"Interrupted: {exc}")
                    raise

                # API レートリミット対策として各書類の処理間にスリープ
                if settings.process_sleep_seconds > 0:
                    time.sleep(settings.process_sleep_seconds)
        finally:
            client.close()

        return len(claimed_documents)
    finally:
        pool.closeall()


# ------------------------------------------------------------------ #
#  Job 3: backfill — 日付範囲の一括 fetch + process
# ------------------------------------------------------------------ #

def backfill_documents(
    settings: Settings,
    *,
    start_date: date,
    end_date: date,
    process_limit: int,
    retry_failed: bool = False,
    client_cls: type[EdinetClient] | None = None,
) -> None:
    """start_date から end_date まで 1 日ずつ fetch → process を繰り返す.

    各日付について:
      1. fetch_documents_for_date で書類一覧を取得・登録
      2. process_documents を queue が空になるまで繰り返し実行
    """
    client_cls = client_cls or EdinetClient
    current_date = start_date
    while current_date <= end_date:
        fetch_documents_for_date(settings, current_date, client_cls=client_cls)
        # その日のキューが空になるまで繰り返し処理
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
