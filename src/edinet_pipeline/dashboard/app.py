"""Streamlit ダッシュボードのエントリポイント — マルチページ構成."""

from __future__ import annotations

import os
from collections.abc import Callable
from pathlib import Path

import duckdb
import streamlit as st

from edinet_pipeline.config import DEFAULT_DUCKDB_PATH
from edinet_pipeline.dashboard.data import get_connection
from edinet_pipeline.dashboard.pages import data_quality, financial, human_capital, overview

_PAGES: dict[str, Callable[[duckdb.DuckDBPyConnection], None]] = {
    "概要": overview.render,
    "財務指標": financial.render,
    "人的資本指標": human_capital.render,
    "データ品質": data_quality.render,
}


def _get_duckdb_path() -> Path:
    """環境変数またはデフォルトパスから DuckDB ファイルパスを取得する."""
    return Path(os.environ.get("EDINET_DUCKDB_PATH", DEFAULT_DUCKDB_PATH))


def main() -> None:
    """ダッシュボードアプリケーションのメイン関数."""
    st.set_page_config(
        page_title="EDINET Analytics Dashboard",
        page_icon=":chart_with_upwards_trend:",
        layout="wide",
    )
    st.title("EDINET 分析ダッシュボード")

    duckdb_path = _get_duckdb_path()
    try:
        conn = get_connection(str(duckdb_path))
    except duckdb.IOException:
        st.error(
            f"DuckDB ファイルが見つかりません: {duckdb_path}\n\n"
            "`edinet export-analytics --format duckdb` を実行してデータをエクスポートしてください。"
        )
        return

    page_name = st.sidebar.radio("ページ選択", options=list(_PAGES.keys()), index=0)
    _PAGES[page_name](conn)


# Streamlit はスクリプト全体を毎リクエストで実行するため main() を import 時に呼ぶ必要がある。
# ただし pytest 経由など Streamlit ランタイム外からの import 時は副作用を避ける。
def _running_under_streamlit() -> bool:
    try:
        from streamlit.runtime import exists  # type: ignore[import-not-found]
    except Exception:
        return False
    return bool(exists())


if _running_under_streamlit():
    main()
