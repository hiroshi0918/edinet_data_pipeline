from __future__ import annotations

import json
import logging
from typing import Any


def configure_logging(level: str) -> None:
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    logging.basicConfig(
        level=numeric_level,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )


def log_event(logger: logging.Logger, level: str, event: str, **fields: Any) -> None:
    payload = {"event": event, **fields}
    getattr(logger, level.lower())(
        json.dumps(payload, ensure_ascii=False, default=str, sort_keys=True)
    )
