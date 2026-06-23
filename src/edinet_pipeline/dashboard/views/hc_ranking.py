"""人的資本トップ/ボトム企業 — 女性管理職比率・男女賃金格差の企業ランキング.

選択年度・次元で、女性管理職比率と男女賃金格差について上位 10 社・下位 10 社を
名指しで並べる。男性育休取得率は単一企業の値が集計タイミングでノイズを含むため、
ここでは扱わず「業種で比べる」(箱ひげ図) に委ねる。
"""

from __future__ import annotations

import duckdb
import pandas as pd
import streamlit as st

from edinet_pipeline.dashboard.components.filters import (
    render_dimension_filter,
    render_single_year_filter,
)
from edinet_pipeline.dashboard.constants import HC_METRIC_LABELS, RANKING_HC_METRICS
from edinet_pipeline.dashboard.data import query_company_comparison

_TOP_N = 10

# 各指標の「上位/下位が何を意味するか」の注記 (誤読防止)
_DIRECTION_NOTE: dict[str, tuple[str, str]] = {
    "female_manager_ratio": ("上位 = 女性管理職比率が高い", "下位 = 低い"),
    "gender_wage_gap": (
        "上位 = 男女賃金格差が小さい (女性賃金が男性に近い)",
        "下位 = 格差が大きい",
    ),
}


def render(conn: duckdb.DuckDBPyConnection) -> None:
    """人的資本トップ/ボトム企業ページを描画する."""
    st.header("人的資本トップ/ボトム企業")
    st.caption(
        "女性管理職比率・男女賃金格差について、上位 10 社と下位 10 社を企業名で示します。"
        "男性育休取得率は単一企業の値がぶれやすいため、ここでは扱わず「業種で比べる」で"
        "業種分布として確認してください。"
    )

    fiscal_year = render_single_year_filter(conn, key_prefix="hcrank")
    scope, worker_type = render_dimension_filter(key_prefix="hcrank")
    if fiscal_year is None:
        st.warning("データがありません")
        return

    metric = st.radio(
        "指標を選択",
        options=list(RANKING_HC_METRICS),
        format_func=lambda m: HC_METRIC_LABELS[m],
        horizontal=True,
        key="hcrank_metric",
    )

    top_note, bottom_note = _DIRECTION_NOTE[metric]
    top_df = query_company_comparison(
        conn, metric, fiscal_year, top_n=_TOP_N,
        ascending=False, scope=scope, worker_type=worker_type,
    )
    bottom_df = query_company_comparison(
        conn, metric, fiscal_year, top_n=_TOP_N,
        ascending=True, scope=scope, worker_type=worker_type,
    )

    if top_df.empty and bottom_df.empty:
        st.info(f"{fiscal_year} 年度・選択次元に {HC_METRIC_LABELS[metric]} の開示がありません。")
        return

    col_top, col_bottom = st.columns(2)
    with col_top:
        st.subheader(f"上位 {_TOP_N} 社")
        st.caption(top_note)
        st.dataframe(
            _format_ranking(top_df, metric), use_container_width=True, hide_index=True
        )
    with col_bottom:
        st.subheader(f"下位 {_TOP_N} 社")
        st.caption(bottom_note)
        st.dataframe(
            _format_ranking(bottom_df, metric), use_container_width=True, hide_index=True
        )


def _format_ranking(df: pd.DataFrame, metric: str) -> pd.DataFrame:
    """ランキング DataFrame を表示用 (順位・企業名・業種・値) に整形する."""
    if df.empty:
        return pd.DataFrame(columns=["順位", "企業名", "業種", HC_METRIC_LABELS[metric]])
    out = pd.DataFrame(
        {
            "順位": range(1, len(df) + 1),
            "企業名": df["company_name"].to_numpy(),
            "業種": df["industry"].fillna("(未取得)").to_numpy(),
            HC_METRIC_LABELS[metric]: [f"{float(v):.1f} %" for v in df[metric]],
        }
    )
    return out
