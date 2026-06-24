"""業種で比べる — 人的資本指標の業種別分布を箱ひげ図で見る.

選択した年度・次元で、女性管理職比率・男女賃金格差・男性育休取得率のいずれかを
業種別の箱ひげ図 (横向き・中央値順) に描く。中央値・四分位・外れ値が一目で分かり、
「どの業種が進んでいて、ばらつきはどうか」を読める。
"""

from __future__ import annotations

import duckdb
import plotly.graph_objects as go
import streamlit as st

from edinet_pipeline.dashboard.components.filters import (
    render_dimension_filter,
    render_single_year_filter,
)
from edinet_pipeline.dashboard.constants import HC_METRIC_LABELS
from edinet_pipeline.dashboard.data import query_hc_distribution_by_industry
from edinet_pipeline.dashboard.theme import median_color, page_header, style_plotly

_MIN_COMPANIES = 5


def render(conn: duckdb.DuckDBPyConnection) -> None:
    """業種で比べるページ (箱ひげ図) を描画する."""
    page_header(
        "BY INDUSTRY",
        "業種で比べる",
        "人的資本指標の業種別分布を箱ひげ図で表示します。箱は四分位、縦線は中央値、"
        f"外側の点は外れ値。中央値の高い業種ほど上・濃い緑になります "
        f"(開示 {_MIN_COMPANIES} 社未満の業種は除外)。",
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

    # 中央値の昇順に業種を並べ (横向きで上ほど高い)、中央値ランクで淡藍→濃tealに着色
    medians = df.groupby("industry")["value"].median().sort_values()
    industries = medians.index.tolist()
    n = len(industries)
    fig = go.Figure()
    for i, industry in enumerate(industries):
        t = i / max(1, n - 1)  # 0 = 中央値最小, 1 = 最大
        color = median_color(t)
        values = df.loc[df["industry"] == industry, "value"]
        fig.add_trace(
            go.Box(
                x=values,
                name=industry,
                orientation="h",
                boxpoints="outliers",
                marker=dict(color=color, size=4, opacity=0.5),
                line=dict(color=color, width=1.4),
                fillcolor=color,
                opacity=0.9,
                hovertemplate=(
                    f"{industry}<br>{HC_METRIC_LABELS[metric]}: "
                    "%{x:.1f}%<extra></extra>"
                ),
            )
        )
    style_plotly(fig, height=max(420, 26 * n))
    fig.update_layout(showlegend=False)
    fig.update_xaxes(title=HC_METRIC_LABELS[metric], ticksuffix="%")
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
