from __future__ import annotations

import argparse
from collections.abc import Sequence
from datetime import datetime

from edinet_pipeline.analytics import export_analytics
from edinet_pipeline.config import Settings
from edinet_pipeline.jobs import backfill_documents, fetch_documents_for_date, process_documents
from edinet_pipeline.logging_utils import configure_logging


def parse_date(value: str) -> datetime.date:
    return datetime.strptime(value, "%Y-%m-%d").date()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="edinet", description="EDINET annual report pipeline")
    subparsers = parser.add_subparsers(dest="command", required=True)

    fetch_parser = subparsers.add_parser(
        "fetch",
        help="Fetch EDINET document metadata for one day",
    )
    fetch_parser.add_argument(
        "--date", required=True, type=parse_date, help="Target date (YYYY-MM-DD)"
    )

    process_parser = subparsers.add_parser("process", help="Process queued EDINET documents")
    process_parser.add_argument("--limit", type=int, default=10, help="Maximum documents per batch")
    process_parser.add_argument(
        "--retry-failed",
        action="store_true",
        help="Include failed documents in the processing queue",
    )

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
