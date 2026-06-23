"""CLIエントリポイント — `edinet` コマンドのサブコマンド定義と実行振り分け."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from datetime import datetime

from edinet_pipeline.analytics import export_analytics
from edinet_pipeline.config import Settings
from edinet_pipeline.db import PipelineRepository, db_connection
from edinet_pipeline.industry_master import update_industries
from edinet_pipeline.jobs import (
    backfill_documents,
    fetch_documents_for_date,
    process_documents,
    reprocess_documents,
)
from edinet_pipeline.logging_utils import configure_logging


def parse_date(value: str) -> datetime.date:
    """YYYY-MM-DD 形式の文字列を date オブジェクトへ変換する."""
    return datetime.strptime(value, "%Y-%m-%d").date()


def build_parser() -> argparse.ArgumentParser:
    """サブコマンド付きの ArgumentParser を構築する.

    サブコマンド:
        fetch            : 指定日の書類一覧を取得し DB 登録
        process          : キューに溜まった書類を順次ダウンロード・解析
        backfill         : 日付範囲で fetch → process をまとめて実行
        reprocess        : 保存済み生行から再抽出 (再DLなし) し指標を更新
        export-analytics : PostgreSQL → Parquet / DuckDB へスナップショット出力
        dashboard        : 分析ダッシュボードを起動 (要 viz 依存)
    """
    parser = argparse.ArgumentParser(prog="edinet", description="EDINET annual report pipeline")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # --- fetch: 1 日分の書類メタデータを EDINET API から取得 ---
    fetch_parser = subparsers.add_parser(
        "fetch",
        help="Fetch EDINET document metadata for one day",
    )
    fetch_parser.add_argument(
        "--date", required=True, type=parse_date, help="Target date (YYYY-MM-DD)"
    )

    # --- process: pending / failed キューの書類を処理 ---
    process_parser = subparsers.add_parser("process", help="Process queued EDINET documents")
    process_parser.add_argument("--limit", type=int, default=10, help="Maximum documents per batch")
    process_parser.add_argument(
        "--retry-failed",
        action="store_true",
        help="Include failed documents in the processing queue",
    )

    # --- backfill: 日付範囲の一括取得 + 処理 ---
    backfill_parser = subparsers.add_parser(
        "backfill",
        help="Fetch and process EDINET documents over a date range",
    )
    backfill_parser.add_argument("--from", dest="start_date", required=True, type=parse_date)
    backfill_parser.add_argument("--to", dest="end_date", required=True, type=parse_date)
    backfill_parser.add_argument(
        "--process-limit",
        type=int,
        default=10,
        help="Batch size used while draining each day's queue",
    )
    backfill_parser.add_argument(
        "--retry-failed",
        action="store_true",
        help="Include failed documents when draining the queue",
    )

    # --- export-analytics: 分析用スナップショットの出力 ---
    export_parser = subparsers.add_parser(
        "export-analytics",
        help="Export analytics snapshots to Parquet and/or DuckDB",
    )
    export_parser.add_argument(
        "--format",
        choices=("parquet", "duckdb", "both"),
        default="both",
        help="Output format to refresh",
    )

    # --- update-industries: EDINETコード集約一覧から業種を取り込む ---
    update_industries_parser = subparsers.add_parser(
        "update-industries",
        help="Update companies.industry from EDINETコード集約一覧 (Edinetcode.zip)",
    )
    source_group = update_industries_parser.add_mutually_exclusive_group(required=True)
    source_group.add_argument(
        "--source-url",
        type=str,
        default=None,
        help="URL of Edinetcode ZIP (公式集約一覧)",
    )
    source_group.add_argument(
        "--source-file",
        type=str,
        default=None,
        help="Path to a pre-downloaded Edinetcode ZIP",
    )

    # --- reprocess: 保存済み生行から再抽出 (抽出ロジック修正の反映) ---
    reprocess_parser = subparsers.add_parser(
        "reprocess",
        help="Re-extract metrics from stored raw_edinet_facts (no re-download)",
    )
    reprocess_parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Maximum documents to reprocess (default: all with raw facts)",
    )

    # --- reset-stale: 停滞した processing 行を手動で pending へ復旧 ---
    reset_stale_parser = subparsers.add_parser(
        "reset-stale",
        help="Reset stale 'processing' rows back to 'pending' (manual recovery)",
    )
    reset_stale_parser.add_argument(
        "--minutes",
        type=int,
        default=None,
        help=(
            "Stale threshold in minutes "
            "(default: STALE_PROCESSING_MINUTES env, or 60)"
        ),
    )

    # --- dashboard: 分析ダッシュボードの起動 ---
    dashboard_parser = subparsers.add_parser(
        "dashboard",
        help="Launch interactive analytics dashboard (requires viz extras)",
    )
    dashboard_parser.add_argument(
        "--port", type=int, default=8501, help="Dashboard server port"
    )
    dashboard_parser.add_argument(
        "--host", type=str, default="localhost", help="Dashboard server host"
    )
    dashboard_parser.add_argument(
        "--duckdb-path",
        type=str,
        default=None,
        help="Path to DuckDB file (default: artifacts/analytics/edinet_analytics.duckdb)",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """CLI メイン関数 — 引数を解析し、対応するジョブを実行して終了コードを返す."""
    parser = build_parser()
    args = parser.parse_args(argv)

    # dashboard は PostgreSQL / API キーを必要としないため、Settings 前に分岐
    if args.command == "dashboard":
        try:
            from edinet_pipeline.dashboard import launch_dashboard
        except ImportError:
            parser.error(
                "Visualization dependencies not installed. "
                "Run: pip install -e '.[viz]'"
            )
        from edinet_pipeline.config import DEFAULT_DUCKDB_PATH

        duckdb_path = args.duckdb_path or DEFAULT_DUCKDB_PATH
        launch_dashboard(host=args.host, port=args.port, duckdb_path=duckdb_path)
        return 0

    settings = Settings.from_env()
    configure_logging(settings.log_level)

    if args.command == "fetch":
        fetch_documents_for_date(settings, args.date)
        return 0

    if args.command == "process":
        process_documents(settings, limit=args.limit, retry_failed=args.retry_failed)
        return 0

    if args.command == "backfill":
        if args.start_date > args.end_date:
            parser.error("--from must be on or before --to")
        backfill_documents(
            settings,
            start_date=args.start_date,
            end_date=args.end_date,
            process_limit=args.process_limit,
            retry_failed=args.retry_failed,
        )
        return 0

    if args.command == "reprocess":
        count = reprocess_documents(settings, limit=args.limit)
        print(f"reprocessed: count={count}")
        return 0

    if args.command == "export-analytics":
        export_analytics(settings, args.format)
        return 0

    if args.command == "reset-stale":
        # --minutes 未指定なら Settings (STALE_PROCESSING_MINUTES 環境変数) に従う
        minutes = (
            args.minutes if args.minutes is not None else settings.stale_processing_minutes
        )
        with db_connection(settings.database_url) as connection:
            repository = PipelineRepository(connection)
            count = repository.reset_stale_processing(stale_after_minutes=minutes)
            connection.commit()
        print(f"stale_processing_reset: count={count}")
        return 0

    if args.command == "update-industries":
        source = args.source_url or args.source_file
        summary = update_industries(settings, source=source)
        print(
            f"industries_updated: fetched={summary['fetched_rows']}, "
            f"industry_filled_total={summary['industry_filled_total']}"
        )
        return 0

    parser.error(f"Unsupported command: {args.command}")
    return 2
