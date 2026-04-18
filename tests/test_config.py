from __future__ import annotations

from pathlib import Path

import pytest

from edinet_pipeline.config import Settings

SETTINGS_ENV_VARS = (
    "EDINET_API_KEY",
    "DATABASE_URL",
    "EDINET_REQUEST_TIMEOUT",
    "EDINET_RETRY_COUNT",
    "EDINET_BACKOFF_SECONDS",
    "PROCESS_SLEEP_SECONDS",
    "LOG_LEVEL",
    "ANALYTICS_OUTPUT_DIR",
    "HUMAN_METRIC_MAX_RATIO",
    "DB_POOL_MIN_SIZE",
    "DB_POOL_MAX_SIZE",
)


def clear_settings_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in SETTINGS_ENV_VARS:
        monkeypatch.delenv(name, raising=False)


@pytest.mark.parametrize("missing_name", ["EDINET_API_KEY", "DATABASE_URL"])
def test_settings_from_env_requires_mandatory_variables(
    monkeypatch: pytest.MonkeyPatch,
    missing_name: str,
) -> None:
    clear_settings_env(monkeypatch)
    monkeypatch.setenv("EDINET_API_KEY", "dummy-edinet-key")
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:password@localhost:5432/edinet_db")
    monkeypatch.delenv(missing_name, raising=False)

    with pytest.raises(ValueError, match=missing_name):
        Settings.from_env()


def test_settings_from_env_applies_defaults_and_derived_paths(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clear_settings_env(monkeypatch)
    monkeypatch.setenv("EDINET_API_KEY", "dummy-edinet-key")
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:password@localhost:5432/edinet_db")

    settings = Settings.from_env()

    assert settings.request_timeout == 30
    assert settings.retry_count == 3
    assert settings.backoff_seconds == 2.0
    assert settings.process_sleep_seconds == 1.0
    assert settings.log_level == "INFO"
    assert settings.analytics_output_root == Path("artifacts/analytics")
    assert settings.analytics_parquet_root == Path("artifacts/analytics/parquet")
    assert settings.analytics_duckdb_path == Path("artifacts/analytics/edinet_analytics.duckdb")
    assert settings.human_metric_max_ratio == 200.0
    assert settings.db_pool_min_size == 1
    assert settings.db_pool_max_size == 5


def test_settings_from_env_parses_numeric_values_and_uppercases_log_level(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clear_settings_env(monkeypatch)
    monkeypatch.setenv("EDINET_API_KEY", "dummy-edinet-key")
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:password@localhost:5432/edinet_db")
    monkeypatch.setenv("EDINET_REQUEST_TIMEOUT", "45")
    monkeypatch.setenv("EDINET_RETRY_COUNT", "5")
    monkeypatch.setenv("EDINET_BACKOFF_SECONDS", "0.25")
    monkeypatch.setenv("PROCESS_SLEEP_SECONDS", "0")
    monkeypatch.setenv("LOG_LEVEL", "debug")
    monkeypatch.setenv("ANALYTICS_OUTPUT_DIR", "/tmp/edinet-analytics")
    monkeypatch.setenv("HUMAN_METRIC_MAX_RATIO", "150.5")
    monkeypatch.setenv("DB_POOL_MIN_SIZE", "2")
    monkeypatch.setenv("DB_POOL_MAX_SIZE", "10")

    settings = Settings.from_env()

    assert settings.request_timeout == 45
    assert settings.retry_count == 5
    assert settings.backoff_seconds == 0.25
    assert settings.process_sleep_seconds == 0.0
    assert settings.log_level == "DEBUG"
    assert settings.analytics_output_root == Path("/tmp/edinet-analytics")
    assert settings.analytics_parquet_root == Path("/tmp/edinet-analytics/parquet")
    assert settings.analytics_duckdb_path == Path("/tmp/edinet-analytics/edinet_analytics.duckdb")
    assert settings.human_metric_max_ratio == 150.5
    assert settings.db_pool_min_size == 2
    assert settings.db_pool_max_size == 10
