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
from edinet_pipeline.dashboard.data import (
    query_available_fiscal_years,
    query_busiest_fiscal_year,
)


def render_single_year_filter(
    conn: duckdb.DuckDBPyConnection,
    key_prefix: str = "",
) -> int | None:
    """単一年度の selectbox をサイドバーに描画し、選択年度を返す (既定は最新年度).

    箱ひげ図やランキングのように「ある 1 年度」を見るページで使う。年度が無ければ
    None を返す。2026 のような部分年度も候補に含むため、各ページで件数の薄さに注意。
    """
    years = query_available_fiscal_years(conn)
    if not years:
        st.sidebar.warning("データがありません")
        return None
    years_desc = sorted(years, reverse=True)
    # 既定は「企業数が最多の年度」。最新が部分年度でも初期表示が薄くならない。
    busiest = query_busiest_fiscal_year(conn)
    default_index = years_desc.index(busiest) if busiest in years_desc else 0
    return int(
        st.sidebar.selectbox(
            "年度",
            options=years_desc,
            index=default_index,
            key=f"{key_prefix}_single_year",
        )
    )


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
