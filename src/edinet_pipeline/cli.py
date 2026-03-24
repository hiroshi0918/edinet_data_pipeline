"""CLIエントリポイント — `edinet` コマンドのサブコマンド定義と実行振り分け."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from datetime import datetime

from edinet_pipeline.analytics import export_analytics
from edinet_pipeline.config import Settings
from edinet_pipeline.jobs import backfill_documents, fetch_documents_for_date, process_documents
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
        export-analytics : PostgreSQL → Parquet / DuckDB へスナップショット出力
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
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """CLI メイン関数 — 引数を解析し、対応するジョブを実行して終了コードを返す."""
    parser = build_parser()
    args = parser.parse_args(argv)
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

    if args.command == "export-analytics":
        export_analytics(settings, args.format)
        return 0

    parser.error(f"Unsupported command: {args.command}")
    return 2
