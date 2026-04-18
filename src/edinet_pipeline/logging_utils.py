from __future__ import annotations

import json
import logging
from typing import Any


def configure_logging(level: str) -> None:
    """ルートロガーのレベルとフォーマットを設定する.

    Airflow などの親プロセスが既にロガーを初期化済みの場合、
    無引数 basicConfig は何もせずレベルが反映されない。
    force=True で既存ハンドラを置き換えた上で、明示的に setLevel を呼び、
    設定値が必ず反映されるようにする。
    """
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    logging.basicConfig(
        level=numeric_level,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        force=True,
    )
    logging.getLogger().setLevel(numeric_level)


def log_event(logger: logging.Logger, level: str, event: str, **fields: Any) -> None:
    payload = {"event": event, **fields}
    getattr(logger, level.lower())(
        json.dumps(payload, ensure_ascii=False, default=str, sort_keys=True)
    )
