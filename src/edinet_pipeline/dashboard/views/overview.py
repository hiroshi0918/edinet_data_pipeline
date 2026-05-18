"""概要ページ — パイプラインの KPI とステータス分布、データストーリー."""

from __future__ import annotations

import duckdb
import pandas as pd
import plotly.express as px
import streamlit as st

from edinet_pipeline.dashboard.constants import (
    SALES_TIER_ORDER,
    STATUS_COLOR_MAP,
)
from edinet_pipeline.dashboard.data import (
    query_kpi_summary,
    query_overview_highlights,
    query_status_distribution,
)


def render(conn: duckdb.DuckDBPyConnection) -> None:
    """概要ページを描画する."""
    st.header("パイプライン概要")

    kpi = query_kpi_summary(conn)
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("企業数", f"{kpi['company_count']:,}")
    col2.metric("年度数", kpi["year_count"])
    col3.metric("総レコード数", f"{kpi['total_records']:,}")
    col4.metric("最新提出日", str(kpi["latest_submission"] or "N/A"))

    _render_data_story(conn)
    _render_status_distribution(conn)


def _render_data_story(conn: duckdb.DuckDBPyConnection) -> None:
    """データストーリー: 業種格差・劇的改善・規模パラドックスの 3 カード."""
    st.subheader("このデータが教えてくれる 3 つのこと")
    st.caption(
        "EDINET 有価証券報告書を 4,000 社超で集計した結果、強い傾向が 3 つ浮かび上がります。"
        "各カードは最新年度のデータを集計したものです。"
    )

    highlights = query_overview_highlights(conn)
    col1, col2, col3 = st.columns(3)
    with col1:
        _render_industry_gap_card(highlights["industry_gap"])
    with col2:
        _render_improvement_card(highlights["improvement"])
    with col3:
        _render_size_paradox_card(highlights["size_paradox"])


def _render_industry_gap_card(industry_gap_df: pd.DataFrame) -> None:
    """業種格差カード: 女性管理職比率の業種別中央値 TOP/BOTTOM."""
    st.markdown("**🔥 業種格差ハイライト**")
    if industry_gap_df.empty or len(industry_gap_df) < 2:
        st.info("業種データが不足しています")
        return
    top = industry_gap_df.iloc[0]
    bottom = industry_gap_df.iloc[-1]
    gap = top["median_value"] - bottom["median_value"]
    st.metric(
        "女性管理職比率（業種別中央値）",
        f"{top['median_value']:.1f}% vs {bottom['median_value']:.1f}%",
        delta=f"{gap:.1f}pt の格差",
        delta_color="off",
    )
    st.caption(f"最高: **{top['industry']}** / 最低: **{bottom['industry']}**")
    top5 = industry_gap_df.head(5).sort_values("median_value")
    fig = px.bar(
        top5,
        x="median_value",
        y="industry",
        orientation="h",
        labels={"median_value": "中央値 (%)", "industry": ""},
        title="業種別 中央値 TOP5",
    )
    fig.update_layout(height=220, margin=dict(l=0, r=0, t=30, b=0), showlegend=False)
    st.plotly_chart(fig, use_container_width=True)


def _render_improvement_card(improvement_df: pd.DataFrame) -> None:
    """改善ハイライトカード: 男性育休取得率の年度推移."""
    st.markdown("**📈 急速に改善した指標**")
    if improvement_df.empty or len(improvement_df) < 2:
        st.info("年度推移データが不足しています")
        return
    last = improvement_df.iloc[-1]
    prev = improvement_df.iloc[-2]
    delta = last["median_value"] - prev["median_value"]
    st.metric(
        "男性育休取得率（中央値）",
        f"{last['median_value']:.1f}%",
        delta=f"前年比 +{delta:.1f}pt" if delta >= 0 else f"前年比 {delta:.1f}pt",
    )
    st.caption(
        f"{int(prev['fiscal_year'])}年度 {prev['median_value']:.1f}% "
        f"→ {int(last['fiscal_year'])}年度 {last['median_value']:.1f}%"
    )
    fig = px.line(
        improvement_df,
        x="fiscal_year",
        y="median_value",
        markers=True,
        labels={"fiscal_year": "年度", "median_value": "中央値 (%)"},
        title="年度別中央値の推移",
    )
    fig.update_xaxes(dtick=1)
    fig.update_layout(height=220, margin=dict(l=0, r=0, t=30, b=0))
    st.plotly_chart(fig, use_container_width=True)


def _render_size_paradox_card(size_paradox_df: pd.DataFrame) -> None:
    """規模パラドックスカード: 売上規模が大きいほど女性管理職比率が低い."""
    st.markdown("**🤔 規模パラドックス**")
    if size_paradox_df.empty:
        st.info("規模別データがありません")
        return
    df_sorted = (
        size_paradox_df.set_index("tier")
        .reindex(SALES_TIER_ORDER)
        .dropna(subset=["median_value"])
        .reset_index()
    )
    if len(df_sorted) < 2:
        st.info("階層データが不足しています")
        return
    smallest = df_sorted.iloc[0]
    largest = df_sorted.iloc[-1]
    delta = largest["median_value"] - smallest["median_value"]
    st.metric(
        "売上規模 vs 女性管理職比率",
        f"小規模 {smallest['median_value']:.1f}% → 大規模 {largest['median_value']:.1f}%",
        delta=f"{delta:.1f}pt（大企業ほど低い）",
        delta_color="inverse",
    )
    st.caption(f"小規模層: {smallest['tier']} / 大規模層: {largest['tier']}")
    fig = px.bar(
        df_sorted,
        x="tier",
        y="median_value",
        labels={"tier": "売上階層", "median_value": "中央値 (%)"},
        title="売上階層別 女性管理職比率（中央値）",
    )
    fig.update_layout(height=220, margin=dict(l=0, r=0, t=30, b=0))
    st.plotly_chart(fig, use_container_width=True)


def _render_status_distribution(conn: duckdb.DuckDBPyConnection) -> None:
    """既存の処理ステータス分布グラフを維持."""
    st.subheader("処理ステータス分布")
    status_df = query_status_distribution(conn)
    if status_df.empty:
        st.info("ステータスデータがありません")
        return

    fig = px.bar(
        status_df,
        x="fiscal_year",
        y="doc_count",
        color="status",
        color_discrete_map=STATUS_COLOR_MAP,
        barmode="stack",
        labels={"fiscal_year": "年度", "doc_count": "件数", "status": "ステータス"},
        title="年度別 処理ステータス",
    )
    fig.update_xaxes(dtick=1)
    st.plotly_chart(fig, use_container_width=True)
