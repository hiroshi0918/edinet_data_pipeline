"""dashboard/app.py のテスト — DuckDB パス解決ロジック."""

from __future__ import annotations

from pathlib import Path

from edinet_pipeline.config import DEFAULT_DUCKDB_PATH
from edinet_pipeline.dashboard.app import _get_duckdb_path


class TestGetDuckdbPath:
    """_get_duckdb_path のテスト."""

    def test_default_path(self, monkeypatch):
        monkeypatch.delenv("EDINET_DUCKDB_PATH", raising=False)
        result = _get_duckdb_path()
        assert result == Path(DEFAULT_DUCKDB_PATH)

    def test_custom_path_from_env(self, monkeypatch):
        monkeypatch.setenv("EDINET_DUCKDB_PATH", "/custom/path/analytics.duckdb")
        result = _get_duckdb_path()
        assert result == Path("/custom/path/analytics.duckdb")
