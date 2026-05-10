from __future__ import annotations

import os
from pathlib import Path

import psycopg2
import pytest

from alembic import command
from alembic.config import Config


@pytest.fixture(scope="session")
def database_url() -> str | None:
    return os.getenv("DATABASE_URL")


@pytest.fixture(scope="session")
def migrated_database(database_url: str | None) -> str:
    if not database_url:
        pytest.skip("DATABASE_URL is not set")

    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", database_url)
    command.upgrade(config, "head")
    return database_url


@pytest.fixture()
def db_connection(migrated_database: str):
    connection = psycopg2.connect(migrated_database)
    connection.autocommit = True
    with connection.cursor() as cursor:
        cursor.execute(
            """
            TRUNCATE TABLE raw_edinet_facts, metric_evidence, human_capital_metrics,
            financial_reports, companies, llm_extraction_cache
            RESTART IDENTITY CASCADE
            """
        )
    yield connection
    connection.close()


@pytest.fixture()
def pipeline_env(monkeypatch: pytest.MonkeyPatch, migrated_database: str) -> None:
    monkeypatch.setenv("EDINET_API_KEY", "dummy-edinet-key")
    monkeypatch.setenv("DATABASE_URL", migrated_database)
    monkeypatch.setenv("PROCESS_SLEEP_SECONDS", "0")
    monkeypatch.setenv("LOG_LEVEL", "INFO")


@pytest.fixture()
def analytics_output_dir(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    output_dir = tmp_path / "analytics"
    monkeypatch.setenv("ANALYTICS_OUTPUT_DIR", str(output_dir))
    return output_dir
