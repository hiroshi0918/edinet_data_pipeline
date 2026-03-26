"""ダッシュボードパッケージ — Streamlit による分析結果の可視化."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def launch_dashboard(*, host: str, port: int, duckdb_path: str) -> None:
    """Streamlit ダッシュボードを subprocess 経由で起動する.

    Args:
        host: サーバーのバインドアドレス
        port: サーバーのポート番号
        duckdb_path: 読み込む DuckDB ファイルのパス
    """
    app_path = str(Path(__file__).parent / "app.py")
    env = {**os.environ, "EDINET_DUCKDB_PATH": str(duckdb_path)}
    subprocess.run(
        [
            sys.executable,
            "-m",
            "streamlit",
            "run",
            app_path,
            "--server.port",
            str(port),
            "--server.address",
            host,
        ],
        env=env,
        check=False,
    )
