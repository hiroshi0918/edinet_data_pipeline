from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import urlparse

import psycopg2
import pytest

from alembic import command
from alembic.config import Config

# 本番 DB 誤破壊防止: TEST_DATABASE_URL を専用に見て、DATABASE_URL とは独立させる。
# 過去に DATABASE_URL を共用していた際、pytest 実行で本番テーブルが TRUNCATE される
# 事故が発生したため、専用環境変数 + DB 名チェックの二重ガードを採用している。
_TEST_DB_ENV_VAR = "TEST_DATABASE_URL"


def _is_safe_test_database(url: str) -> bool:
    """URL のデータベース名に "test" を含むときだけ TRUNCATE を許可する."""
    try:
        path = urlparse(url).path or ""
    except Exception:
        return False
    db_name = path.lstrip("/")
    return "test" in db_name.lower()


@pytest.fixture(scope="session")
def database_url() -> str | None:
    return os.getenv(_TEST_DB_ENV_VAR)


@pytest.fixture(scope="session")
def migrated_database(database_url: str | None) -> str:
    if not database_url:
        pytest.skip(
            f"{_TEST_DB_ENV_VAR} is not set. "
            "Set it to a dedicated test database whose name contains 'test' "
            "(e.g. postgresql://user:password@db:5432/edinet_test)."
        )

    if not _is_safe_test_database(database_url):
        pytest.fail(
            f"{_TEST_DB_ENV_VAR} must point to a database whose name contains "
            f"'test' (got: {urlparse(database_url).path}). Refusing to run "
            "destructive fixtures against a non-test database."
        )

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
