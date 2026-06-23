"""業種で比べる — 人的資本指標の業種別分布を箱ひげ図で見る.

選択した年度・次元で、女性管理職比率・男女賃金格差・男性育休取得率のいずれかを
業種別の箱ひげ図 (横向き・中央値順) に描く。中央値・四分位・外れ値が一目で分かり、
「どの業種が進んでいて、ばらつきはどうか」を読める。
"""

from __future__ import annotations

import duckdb
import plotly.express as px
import streamlit as st

from edinet_pipeline.dashboard.components.filters import (
    render_dimension_filter,
    render_single_year_filter,
)
from edinet_pipeline.dashboard.constants import HC_METRIC_LABELS
from edinet_pipeline.dashboard.data import query_hc_distribution_by_industry

_MIN_COMPANIES = 5


def render(conn: duckdb.DuckDBPyConnection) -> None:
    """業種で比べるページ (箱ひげ図) を描画する."""
    st.header("業種で比べる")
    st.caption(
        "人的資本指標の業種別分布を箱ひげ図で表示します。箱は四分位、縦線は中央値、"
        "外側の点は外れ値です。業種は中央値の高い順に並びます "
        f"(開示 {_MIN_COMPANIES} 社未満の業種は除外)。"
    )

    fiscal_year = render_single_year_filter(conn, key_prefix="boxplot")
    scope, worker_type = render_dimension_filter(key_prefix="boxplot")
    if fiscal_year is None:
        st.warning("データがありません")
        return

    metric = st.radio(
        "指標を選択",
        options=list(HC_METRIC_LABELS.keys()),
        format_func=lambda m: HC_METRIC_LABELS[m],
        horizontal=True,
        key="boxplot_metric",
    )

    df = query_hc_distribution_by_industry(
        conn, metric, fiscal_year, scope, worker_type, min_companies=_MIN_COMPANIES
    )
    if df.empty:
        st.info(
            f"{fiscal_year} 年度・選択次元で、{HC_METRIC_LABELS[metric]} を "
            f"{_MIN_COMPANIES} 社以上開示している業種がありません。"
        )
        return

    # 中央値の高い順に業種を並べる (横向き箱ひげで上ほど高い)
    order = (
        df.groupby("industry")["value"].median().sort_values().index.tolist()
    )
    fig = px.box(
        df,
        x="value",
        y="industry",
        orientation="h",
        points="outliers",
        category_orders={"industry": order},
        labels={"value": HC_METRIC_LABELS[metric], "industry": "業種"},
    )
    # 業種数に応じて高さを伸ばし、全業種のラベルが潰れないようにする
    fig.update_layout(height=max(400, 26 * len(order)), margin=dict(l=10, r=10))
    st.plotly_chart(fig, use_container_width=True)

    if metric == "male_childcare_leave_ratio":
        st.caption(
            "⚠️ 男性育休取得率は前年度の出産に当年度取得した等の集計タイミングで "
            "100% を超える値が正当に発生します。箱の外の点として表示され、中央値"
            "ベースの並びには影響しません。"
        )

    n_companies = len(df)
    n_industries = df["industry"].nunique()
    st.caption(f"対象: {n_industries} 業種 / {n_companies:,} 社 ({fiscal_year} 年度)")
