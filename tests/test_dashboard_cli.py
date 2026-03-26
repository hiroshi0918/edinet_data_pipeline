"""dashboard サブコマンドの CLI テスト."""

from __future__ import annotations

import sys
from unittest.mock import patch

import pytest

from edinet_pipeline.cli import build_parser, main
from edinet_pipeline.config import DEFAULT_DUCKDB_PATH


class TestDashboardParser:
    """dashboard サブコマンドのパーサーテスト."""

    def test_dashboard_subcommand_exists(self):
        parser = build_parser()
        args = parser.parse_args(["dashboard"])
        assert args.command == "dashboard"

    def test_default_port(self):
        parser = build_parser()
        args = parser.parse_args(["dashboard"])
        assert args.port == 8501

    def test_custom_port(self):
        parser = build_parser()
        args = parser.parse_args(["dashboard", "--port", "9000"])
        assert args.port == 9000

    def test_default_host(self):
        parser = build_parser()
        args = parser.parse_args(["dashboard"])
        assert args.host == "localhost"

    def test_custom_host(self):
        parser = build_parser()
        args = parser.parse_args(["dashboard", "--host", "0.0.0.0"])
        assert args.host == "0.0.0.0"

    def test_default_duckdb_path_is_none(self):
        parser = build_parser()
        args = parser.parse_args(["dashboard"])
        assert args.duckdb_path is None

    def test_custom_duckdb_path(self):
        parser = build_parser()
        args = parser.parse_args(["dashboard", "--duckdb-path", "/tmp/test.duckdb"])
        assert args.duckdb_path == "/tmp/test.duckdb"

    def test_all_options_combined(self):
        parser = build_parser()
        args = parser.parse_args([
            "dashboard",
            "--port", "3000",
            "--host", "0.0.0.0",
            "--duckdb-path", "/data/analytics.duckdb",
        ])
        assert args.port == 3000
        assert args.host == "0.0.0.0"
        assert args.duckdb_path == "/data/analytics.duckdb"


class TestDashboardMain:
    """dashboard サブコマンドの main() 実行テスト."""

    def test_calls_launch_dashboard_with_defaults(self):
        with patch("edinet_pipeline.dashboard.launch_dashboard") as mock_launch:
            result = main(["dashboard"])
        assert result == 0
        mock_launch.assert_called_once_with(
            host="localhost",
            port=8501,
            duckdb_path=DEFAULT_DUCKDB_PATH,
        )

    def test_calls_launch_dashboard_with_custom_args(self):
        with patch("edinet_pipeline.dashboard.launch_dashboard") as mock_launch:
            result = main([
                "dashboard",
                "--port", "9999",
                "--host", "0.0.0.0",
                "--duckdb-path", "/tmp/custom.duckdb",
            ])
        assert result == 0
        mock_launch.assert_called_once_with(
            host="0.0.0.0",
            port=9999,
            duckdb_path="/tmp/custom.duckdb",
        )

    def test_does_not_require_env_vars(self, monkeypatch):
        """dashboard コマンドは EDINET_API_KEY / DATABASE_URL が不要."""
        monkeypatch.delenv("EDINET_API_KEY", raising=False)
        monkeypatch.delenv("DATABASE_URL", raising=False)
        with patch("edinet_pipeline.dashboard.launch_dashboard"):
            result = main(["dashboard"])
        assert result == 0

    def test_import_error_exits_with_error(self):
        """viz 依存が未インストールの場合、エラー終了する."""
        with patch.dict("sys.modules", {"edinet_pipeline.dashboard": None}):
            with pytest.raises(SystemExit) as exc_info:
                main(["dashboard"])
            assert exc_info.value.code != 0


class TestLaunchDashboard:
    """launch_dashboard 関数のテスト."""

    def test_subprocess_run_called_with_correct_args(self):
        with patch("edinet_pipeline.dashboard.subprocess.run") as mock_run:
            from edinet_pipeline.dashboard import launch_dashboard

            launch_dashboard(host="localhost", port=8501, duckdb_path="/tmp/test.duckdb")

        mock_run.assert_called_once()
        call_args = mock_run.call_args
        cmd = call_args[0][0]
        assert cmd[0] == sys.executable
        assert cmd[1:3] == ["-m", "streamlit"]
        assert cmd[3] == "run"
        assert cmd[4].endswith("app.py")
        assert "--server.port" in cmd
        assert "8501" in cmd
        assert "--server.address" in cmd
        assert "localhost" in cmd

    def test_env_contains_duckdb_path(self):
        with patch("edinet_pipeline.dashboard.subprocess.run") as mock_run:
            from edinet_pipeline.dashboard import launch_dashboard

            launch_dashboard(host="localhost", port=8501, duckdb_path="/data/my.duckdb")

        call_kwargs = mock_run.call_args[1]
        assert call_kwargs["env"]["EDINET_DUCKDB_PATH"] == "/data/my.duckdb"

    def test_custom_port_and_host(self):
        with patch("edinet_pipeline.dashboard.subprocess.run") as mock_run:
            from edinet_pipeline.dashboard import launch_dashboard

            launch_dashboard(host="0.0.0.0", port=3000, duckdb_path="/tmp/t.duckdb")

        cmd = mock_run.call_args[0][0]
        port_idx = cmd.index("--server.port")
        assert cmd[port_idx + 1] == "3000"
        host_idx = cmd.index("--server.address")
        assert cmd[host_idx + 1] == "0.0.0.0"


