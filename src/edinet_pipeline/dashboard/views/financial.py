"""財務指標ページ — 売上高・利益・従業員数の推移と企業比較."""

from __future__ import annotations

import duckdb
import plotly.express as px
import streamlit as st

from edinet_pipeline.dashboard.components.filters import (
    render_company_filter,
    render_fiscal_year_filter,
)
from edinet_pipeline.dashboard.constants import FINANCIAL_METRIC_LABELS
from edinet_pipeline.dashboard.data import (
    query_company_comparison,
    query_financial_summary_stats,
    query_financial_trends,
)


def render(conn: duckdb.DuckDBPyConnection) -> None:
    """財務指標ページを描画する."""
    st.header("財務指標")

    year_min, year_max = render_fiscal_year_filter(conn, key_prefix="fin")
    if year_min == 0:
        return
    selected_codes = render_company_filter(conn, key_prefix="fin")

    _render_trends(conn, selected_codes, year_min, year_max)
    _render_company_ranking(conn, year_min, year_max)
    _render_summary_stats(conn, year_min, year_max)


def _render_trends(
    conn: duckdb.DuckDBPyConnection, selected_codes: list[str], year_min: int, year_max: int
) -> None:
    """時系列推移セクション."""
    st.subheader("財務指標の推移")
    if not selected_codes:
        st.info("企業を選択してください")
        return

    df = query_financial_trends(conn, selected_codes, year_min, year_max)
    if df.empty:
        st.info("該当するデータがありません")
        return

    metric = st.selectbox(
        "表示する指標",
        options=list(FINANCIAL_METRIC_LABELS.keys()),
        format_func=lambda m: FINANCIAL_METRIC_LABELS[m],
        key="fin_metric_trend",
    )
    fig = px.line(
        df,
        x="fiscal_year",
        y=metric,
        color="company_name",
        markers=True,
        labels={
            "fiscal_year": "年度",
            metric: FINANCIAL_METRIC_LABELS[metric],
            "company_name": "企業",
        },
        title=f"{FINANCIAL_METRIC_LABELS[metric]}の推移",
    )
    fig.update_xaxes(dtick=1)
    st.plotly_chart(fig, use_container_width=True)


def _render_company_ranking(
    conn: duckdb.DuckDBPyConnection, year_min: int, year_max: int
) -> None:
    """企業比較ランキングセクション."""
    st.subheader("企業比較ランキング")
    col1, col2, col3 = st.columns(3)
    metric = col1.selectbox(
        "比較指標",
        options=list(FINANCIAL_METRIC_LABELS.keys()),
        format_func=lambda m: FINANCIAL_METRIC_LABELS[m],
        key="fin_metric_compare",
    )
    year = col2.number_input(
        "年度", min_value=year_min, max_value=year_max, value=year_max, key="fin_compare_year"
    )
    top_n = col3.number_input("上位件数", min_value=5, max_value=50, value=20, key="fin_top_n")

    ranking_df = query_company_comparison(conn, metric, year, top_n)
    if ranking_df.empty:
        st.info("該当するデータがありません")
        return

    fig = px.bar(
        ranking_df.sort_values(metric, ascending=True),
        x=metric,
        y="company_name",
        orientation="h",
        labels={metric: FINANCIAL_METRIC_LABELS[metric], "company_name": "企業"},
        title=f"{FINANCIAL_METRIC_LABELS[metric]} Top {top_n} ({year}年度)",
    )
    fig.update_layout(yaxis={"categoryorder": "total ascending"}, height=max(400, top_n * 25))
    st.plotly_chart(fig, use_container_width=True)


def _render_summary_stats(
    conn: duckdb.DuckDBPyConnection, year_min: int, year_max: int
) -> None:
    """年度別集計統計セクション."""
    st.subheader("年度別 集計統計")
    stats_df = query_financial_summary_stats(conn, year_min, year_max)
    if not stats_df.empty:
        st.dataframe(stats_df, use_container_width=True, hide_index=True)
