"""共通サイドバーフィルター — 各ページから再利用する Streamlit ウィジェット."""

from __future__ import annotations

import duckdb
import streamlit as st

from edinet_pipeline.dashboard.constants import (
    DEFAULT_SCOPE,
    DEFAULT_WORKER_TYPE,
    SCOPE_LABELS,
    WORKER_TYPE_LABELS,
)
from edinet_pipeline.dashboard.data import query_available_companies, query_available_fiscal_years


def render_fiscal_year_filter(
    conn: duckdb.DuckDBPyConnection,
    key_prefix: str = "",
) -> tuple[int, int]:
    """年度範囲スライダーを描画し (min, max) を返す."""
    years = query_available_fiscal_years(conn)
    if not years:
        st.sidebar.warning("データがありません")
        return 0, 0
    if len(years) == 1:
        st.sidebar.info(f"年度: {years[0]}")
        return years[0], years[0]
    year_range = st.sidebar.slider(
        "年度範囲",
        min_value=min(years),
        max_value=max(years),
        value=(min(years), max(years)),
        key=f"{key_prefix}_fiscal_year",
    )
    return year_range[0], year_range[1]


def render_dimension_filter(
    key_prefix: str = "",
    *,
    scope_default: str = DEFAULT_SCOPE,
    worker_type_default: str = DEFAULT_WORKER_TYPE,
) -> tuple[str, str]:
    """サイドバーに次元 (scope/worker_type) のセレクタを描画し、選択値を返す.

    人的資本指標が次元別にスキーマ化されたことに伴い、ダッシュボード全体で
    同じ次元を切り替えられるよう共通化する。
    """
    st.sidebar.markdown("**人的資本の開示範囲**")
    scope = st.sidebar.selectbox(
        "対象範囲",
        options=list(SCOPE_LABELS.keys()),
        index=list(SCOPE_LABELS.keys()).index(scope_default),
        format_func=lambda code: SCOPE_LABELS[code],
        key=f"{key_prefix}_scope",
    )
    worker_type = st.sidebar.selectbox(
        "労働者区分",
        options=list(WORKER_TYPE_LABELS.keys()),
        index=list(WORKER_TYPE_LABELS.keys()).index(worker_type_default),
        format_func=lambda code: WORKER_TYPE_LABELS[code],
        key=f"{key_prefix}_worker_type",
    )
    return scope, worker_type


def render_company_filter(
    conn: duckdb.DuckDBPyConnection,
    key_prefix: str = "",
    max_default: int = 5,
) -> list[str]:
    """企業マルチセレクトを描画し、選択された edinet_code のリストを返す."""
    df = query_available_companies(conn)
    if df.empty:
        st.sidebar.warning("企業データがありません")
        return []
    options = dict(zip(df["edinet_code"], df["company_name"], strict=True))
    default_codes = list(options.keys())[:max_default]
    selected = st.sidebar.multiselect(
        "企業を選択",
        options=list(options.keys()),
        default=default_codes,
        format_func=lambda code: f"{options[code]} ({code})",
        key=f"{key_prefix}_company",
    )
    return selected
