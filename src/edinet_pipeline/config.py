from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from edinet_pipeline.models import FilingFilters


def _get_env(name: str, *, default: str | None = None, required: bool = False) -> str:
    value = os.getenv(name, default)
    if required and not value:
        raise ValueError(f"Environment variable {name} is required.")
    if value is None:
        raise ValueError(f"Environment variable {name} is required.")
    return value


@dataclass(frozen=True)
class Settings:
    edinet_api_key: str
    database_url: str
    request_timeout: int = 30
    retry_count: int = 3
    backoff_seconds: float = 2.0
    process_sleep_seconds: float = 1.0
    log_level: str = "INFO"
    analytics_output_dir: str = "artifacts/analytics"
    filing_filters: FilingFilters = field(default_factory=FilingFilters)

    @classmethod
    def from_env(cls) -> Settings:
        return cls(
            edinet_api_key=_get_env("EDINET_API_KEY", required=True),
            database_url=_get_env("DATABASE_URL", required=True),
            request_timeout=int(_get_env("EDINET_REQUEST_TIMEOUT", default="30")),
            retry_count=int(_get_env("EDINET_RETRY_COUNT", default="3")),
            backoff_seconds=float(_get_env("EDINET_BACKOFF_SECONDS", default="2")),
            process_sleep_seconds=float(_get_env("PROCESS_SLEEP_SECONDS", default="1")),
            log_level=_get_env("LOG_LEVEL", default="INFO").upper(),
            analytics_output_dir=_get_env(
                "ANALYTICS_OUTPUT_DIR", default="artifacts/analytics"
            ),
        )

    @property
    def analytics_output_root(self) -> Path:
        return Path(self.analytics_output_dir)

    @property
    def analytics_parquet_root(self) -> Path:
        return self.analytics_output_root / "parquet"

    @property
    def analytics_duckdb_path(self) -> Path:
        return self.analytics_output_root / "edinet_analytics.duckdb"
