"""財務指標ページ — 売上高・利益・従業員数の推移と企業比較.

v0.4 改修: プリセット選択・業種フィルタ・業種中央値ライン・Q1/Q3 統計を追加。
"""

from __future__ import annotations

import duckdb
import plotly.express as px
import streamlit as st

from edinet_pipeline.dashboard.components.filters import (
    render_company_filter,
    render_fiscal_year_filter,
    render_industry_filter,
)
from edinet_pipeline.dashboard.constants import FINANCIAL_METRIC_LABELS
from edinet_pipeline.dashboard.data import (
    query_company_comparison,
    query_financial_summary_extended,
    query_financial_trends,
    query_metric_overall_median,
)


def render(conn: duckdb.DuckDBPyConnection) -> None:
    """財務指標ページを描画する."""
    st.header("財務指標")
    st.caption(
        "企業の財務指標（売上高・営業利益・純利益・従業員数）の推移と比較を表示します。"
        "サイドバーの **プリセット** で企業選択をワンクリックで切り替えられます。"
        "**業種** で絞り込むと、ランキング・統計が業種内に限定されます。"
    )

    year_min, year_max = render_fiscal_year_filter(conn, key_prefix="fin")
    if year_min == 0:
        return
    industry_filter = render_industry_filter(conn, key_prefix="fin")
    selected_codes = render_company_filter(
        conn,
        fiscal_year=year_max,
        key_prefix="fin",
        industry_filter=industry_filter,
    )

    _render_trends(conn, selected_codes, year_min, year_max)
    _render_company_ranking(conn, year_min, year_max, industry_filter)
    _render_summary_stats(conn, year_min, year_max, industry_filter)


def _render_trends(
    conn: duckdb.DuckDBPyConnection, selected_codes: list[str], year_min: int, year_max: int
) -> None:
    """時系列推移セクション."""
    st.subheader("財務指標の推移")
    if not selected_codes:
        st.info("企業が選択されていません。サイドバーでプリセットまたはカスタム選択をしてください。")
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
        title=f"{FINANCIAL_METRIC_LABELS[metric]}の推移（{len(selected_codes)}社）",
    )
    fig.update_xaxes(dtick=1)
    st.plotly_chart(fig, use_container_width=True)


def _render_company_ranking(
    conn: duckdb.DuckDBPyConnection,
    year_min: int,
    year_max: int,
    industry_filter: tuple[str, ...],
) -> None:
    """企業比較ランキングセクション（業種中央値ライン付き）."""
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

    ranking_df = query_company_comparison(
        conn, metric, int(year), int(top_n), industry_filter=industry_filter,
    )
    if ranking_df.empty:
        st.info("該当するデータがありません")
        return

    overall_median = query_metric_overall_median(
        conn, metric, int(year), industry_filter=industry_filter,
    )

    industry_label = (
        f"業種: {', '.join(industry_filter)}" if industry_filter else "全業種"
    )
    fig = px.bar(
        ranking_df.sort_values(metric, ascending=True),
        x=metric,
        y="company_name",
        orientation="h",
        labels={metric: FINANCIAL_METRIC_LABELS[metric], "company_name": "企業"},
        title=f"{FINANCIAL_METRIC_LABELS[metric]} Top {top_n} ({int(year)}年度・{industry_label})",
        hover_data=["industry"],
    )
    if overall_median is not None:
        fig.add_vline(
            x=overall_median,
            line_dash="dash",
            line_color="#e74c3c",
            annotation_text=f"中央値 {overall_median:,.0f}",
            annotation_position="top",
        )
    fig.update_layout(yaxis={"categoryorder": "total ascending"}, height=max(400, top_n * 25))
    st.plotly_chart(fig, use_container_width=True)


def _render_summary_stats(
    conn: duckdb.DuckDBPyConnection,
    year_min: int,
    year_max: int,
    industry_filter: tuple[str, ...],
) -> None:
    """年度別集計統計セクション（Q1/Q3 を含む拡張版・桁区切りフォーマット）."""
    st.subheader("年度別 集計統計（Q1/Q3 を含む拡張版）")
    stats_df = query_financial_summary_extended(
        conn, year_min, year_max, industry_filter=industry_filter,
    )
    if stats_df.empty:
        st.info("該当するデータがありません")
        return

    label_map = {
        "fiscal_year": "年度",
        "count": "企業数",
        "avg_sales": "売上高 平均",
        "med_sales": "売上高 中央値",
        "q1_sales": "売上高 Q1",
        "q3_sales": "売上高 Q3",
        "avg_operating_profit": "営業利益 平均",
        "med_operating_profit": "営業利益 中央値",
        "q1_operating_profit": "営業利益 Q1",
        "q3_operating_profit": "営業利益 Q3",
        "avg_net_profit": "純利益 平均",
        "med_net_profit": "純利益 中央値",
        "avg_employee_count": "従業員数 平均",
        "med_employee_count": "従業員数 中央値",
    }
    display_df = stats_df.rename(columns=label_map)

    column_config: dict[str, st.column_config.Column] = {
        "年度": st.column_config.NumberColumn(format="%d"),
        "企業数": st.column_config.NumberColumn(format="%,d"),
    }
    for label in display_df.columns:
        if label in ("年度", "企業数"):
            continue
        if "従業員数" in label:
            column_config[label] = st.column_config.NumberColumn(format="%,d 人")
        else:
            column_config[label] = st.column_config.NumberColumn(format="¥%,d")

    st.dataframe(
        display_df,
        use_container_width=True,
        hide_index=True,
        column_config=column_config,
    )
