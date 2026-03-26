"""概要ページ — パイプラインの KPI とステータス分布."""

from __future__ import annotations

import duckdb
import plotly.express as px
import streamlit as st

from edinet_pipeline.dashboard.constants import STATUS_COLOR_MAP
from edinet_pipeline.dashboard.data import query_kpi_summary, query_status_distribution


def render(conn: duckdb.DuckDBPyConnection) -> None:
    """概要ページを描画する."""
    st.header("パイプライン概要")

    kpi = query_kpi_summary(conn)

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("企業数", f"{kpi['company_count']:,}")
    col2.metric("年度数", kpi["year_count"])
    col3.metric("総レコード数", f"{kpi['total_records']:,}")
    col4.metric("最新提出日", str(kpi["latest_submission"] or "N/A"))

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
