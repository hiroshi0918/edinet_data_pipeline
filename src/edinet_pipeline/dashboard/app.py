"""Streamlit ダッシュボードのエントリポイント — マルチページ構成."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from pathlib import Path

import duckdb
import streamlit as st

from edinet_pipeline.dashboard.data import get_connection
from edinet_pipeline.dashboard.datasource import DuckdbDownloadError, ensure_duckdb_file
from edinet_pipeline.dashboard.theme import app_brand_header, inject_global_css
from edinet_pipeline.dashboard.views import (
    company_lookup,
    company_spotlight,
    hc_ranking,
    industry_boxplot,
    size_vs_hc,
)

_PAGES: dict[str, Callable[[duckdb.DuckDBPyConnection], None]] = {
    "企業を調べる": company_lookup.render,
    "業種で比べる": industry_boxplot.render,
    "人的資本トップ/ボトム企業": hc_ranking.render,
    "規模×人的資本": size_vs_hc.render,
    "企業スポットライト": company_spotlight.render,
}


def main() -> None:
    """ダッシュボードアプリケーションのメイン関数."""
    st.set_page_config(
        page_title="EDINET Analytics Dashboard",
        page_icon=":chart_with_upwards_trend:",
        layout="wide",
    )
    inject_global_css()
    app_brand_header()

    try:
        duckdb_path = ensure_duckdb_file()
        conn = get_connection(str(duckdb_path))
    except (duckdb.IOException, DuckdbDownloadError) as exc:
        # ローカル開発と公開環境の双方に効くメッセージ (どちらの導線も案内)
        st.error(
            "DuckDB データを読み込めませんでした。\n\n"
            f"詳細: {exc}\n\n"
            "- ローカル開発: `edinet export-analytics --format duckdb` を実行して "
            "`artifacts/analytics/edinet_analytics.duckdb` を生成してください。\n"
            "- 公開環境: GitHub Releases の `data-latest` タグに "
            "`edinet_analytics.duckdb` が添付されているか確認してください。"
        )
        return

    # サイドバーにデータ更新日 (DuckDB ファイルの mtime) を表示
    try:
        updated_at = datetime.fromtimestamp(Path(duckdb_path).stat().st_mtime)
        st.sidebar.caption(f"データ更新日: {updated_at:%Y-%m-%d %H:%M}")
    except OSError:
        pass

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
