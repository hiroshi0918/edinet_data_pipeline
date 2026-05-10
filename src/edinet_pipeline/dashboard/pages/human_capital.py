"""人的資本指標ページ — 分布・推移・散布図 (scope/worker_type 次元切替対応)."""

from __future__ import annotations

import duckdb
import pandas as pd
import plotly.express as px
import streamlit as st

from edinet_pipeline.dashboard.components.filters import (
    render_dimension_filter,
    render_fiscal_year_filter,
)
from edinet_pipeline.dashboard.constants import (
    HC_METRIC_LABELS,
    HC_TREND_LABEL_MAP,
    SCOPE_LABELS,
    WORKER_TYPE_LABELS,
)
from edinet_pipeline.dashboard.data import (
    query_hc_distribution,
    query_hc_scatter,
    query_hc_trends,
)


def render(conn: duckdb.DuckDBPyConnection) -> None:
    """人的資本指標ページを描画する."""
    st.header("人的資本指標")

    year_min, year_max = render_fiscal_year_filter(conn, key_prefix="hc")
    if year_min == 0:
        return
    scope, worker_type = render_dimension_filter(key_prefix="hc")

    st.caption(
        f"表示中の次元: **{SCOPE_LABELS[scope]} × {WORKER_TYPE_LABELS[worker_type]}**"
    )

    dist_df = _render_distribution(conn, year_min, year_max, scope, worker_type)
    _render_trends(conn, year_min, year_max, scope, worker_type)
    _render_scatter(conn, year_min, year_max, scope, worker_type)

    if not dist_df.empty:
        st.subheader("詳細データ")
        st.dataframe(dist_df, use_container_width=True, hide_index=True)


def _render_distribution(
    conn: duckdb.DuckDBPyConnection,
    year_min: int,
    year_max: int,
    scope: str,
    worker_type: str,
) -> pd.DataFrame:
    """分布プロットセクション."""
    st.subheader("指標の分布")
    col1, col2 = st.columns(2)
    metric = col1.selectbox(
        "指標を選択",
        options=list(HC_METRIC_LABELS.keys()),
        format_func=lambda m: HC_METRIC_LABELS[m],
        key="hc_dist_metric",
    )
    year = col2.number_input(
        "年度", min_value=year_min, max_value=year_max, value=year_max, key="hc_dist_year"
    )

    label = HC_METRIC_LABELS[metric]
    dist_df = query_hc_distribution(conn, metric, year, scope=scope, worker_type=worker_type)
    if dist_df.empty:
        st.info(f"{label}のデータがありません ({year}年度・選択次元)")
        return dist_df

    tab_hist, tab_box = st.tabs(["ヒストグラム", "箱ひげ図"])
    with tab_hist:
        fig = px.histogram(
            dist_df, x=metric, nbins=20,
            labels={metric: label}, title=f"{label} 分布 ({year}年度)",
        )
        st.plotly_chart(fig, use_container_width=True)
    with tab_box:
        fig = px.box(
            dist_df, y=metric, points="all",
            labels={metric: label}, title=f"{label} 箱ひげ図 ({year}年度)",
        )
        st.plotly_chart(fig, use_container_width=True)
    return dist_df


def _render_trends(
    conn: duckdb.DuckDBPyConnection,
    year_min: int,
    year_max: int,
    scope: str,
    worker_type: str,
) -> None:
    """年度別平均推移セクション."""
    st.subheader("年度別 平均推移")
    trends_df = query_hc_trends(conn, year_min, year_max, scope, worker_type)
    if trends_df.empty:
        st.info("推移データがありません")
        return

    trend_cols = [c for c in trends_df.columns if c.startswith("avg_")]
    melted = trends_df.melt(
        id_vars=["fiscal_year"], value_vars=trend_cols,
        var_name="metric", value_name="value",
    )
    melted["metric"] = melted["metric"].map(HC_TREND_LABEL_MAP)
    fig = px.line(
        melted, x="fiscal_year", y="value", color="metric", markers=True,
        labels={"fiscal_year": "年度", "value": "平均値 (%)", "metric": "指標"},
        title="人的資本指標 平均推移",
    )
    fig.update_xaxes(dtick=1)
    st.plotly_chart(fig, use_container_width=True)


def _render_scatter(
    conn: duckdb.DuckDBPyConnection,
    year_min: int,
    year_max: int,
    scope: str,
    worker_type: str,
) -> None:
    """散布図セクション."""
    st.subheader("女性管理職比率 vs 男性育休取得率")
    year = st.number_input(
        "年度", min_value=year_min, max_value=year_max, value=year_max, key="hc_scatter_year"
    )
    scatter_df = query_hc_scatter(conn, year, scope=scope, worker_type=worker_type)
    if scatter_df.empty:
        st.info(f"両指標を持つデータがありません ({year}年度・選択次元)")
        return

    fig = px.scatter(
        scatter_df,
        x="female_manager_ratio", y="male_childcare_leave_ratio",
        size="employee_count", hover_name="company_name",
        labels={
            "female_manager_ratio": HC_METRIC_LABELS["female_manager_ratio"],
            "male_childcare_leave_ratio": HC_METRIC_LABELS["male_childcare_leave_ratio"],
            "employee_count": "従業員数",
        },
        title=f"女性管理職比率 vs 男性育休取得率 ({year}年度)",
    )
    st.plotly_chart(fig, use_container_width=True)
