"""データ品質ページ — カバレッジヒートマップ・充足率・抽出方法分布."""

from __future__ import annotations

import duckdb
import plotly.express as px
import streamlit as st

from edinet_pipeline.dashboard.components.filters import render_fiscal_year_filter
from edinet_pipeline.dashboard.constants import ALL_METRIC_COLUMNS, ALL_METRIC_LABELS
from edinet_pipeline.dashboard.data import (
    query_completeness_over_time,
    query_coverage_matrix,
    query_evidence_summary,
)


def render(conn: duckdb.DuckDBPyConnection) -> None:
    """データ品質ページを描画する."""
    st.header("データ品質")

    year_min, year_max = render_fiscal_year_filter(conn, key_prefix="dq")
    if year_min == 0:
        return

    _render_coverage(conn, year_min, year_max)
    _render_completeness(conn)
    _render_evidence(conn)


def _render_coverage(
    conn: duckdb.DuckDBPyConnection, year_min: int, year_max: int
) -> None:
    """カバレッジヒートマップ + 欠損サマリー."""
    st.subheader("指標カバレッジ")
    year = st.number_input(
        "年度", min_value=year_min, max_value=year_max, value=year_max, key="dq_coverage_year"
    )
    st.caption(
        "1行=1企業、1列=1指標。**緑=値あり / 赤=欠損**。"
        "セルにマウスを乗せると企業名・指標名・値の有無が表示されます。"
    )
    cov_df = query_coverage_matrix(conn, year)
    if cov_df.empty:
        st.info(f"データがありません ({year}年度)")
        return

    heat_data = cov_df.set_index("company_name")[ALL_METRIC_COLUMNS]
    heat_data.columns = [ALL_METRIC_LABELS[c] for c in heat_data.columns]
    fig = px.imshow(
        heat_data,
        color_continuous_scale=["#e74c3c", "#2ecc71"],
        aspect="auto",
        labels={"color": "値あり=1 / 欠損=0", "x": "指標", "y": "企業"},
        title=f"指標カバレッジ ({year}年度)",
    )
    fig.update_coloraxes(
        cmin=0, cmax=1,
        colorbar=dict(tickvals=[0, 1], ticktext=["欠損", "あり"]),
    )
    fig.update_traces(
        hovertemplate="企業: %{y}<br>指標: %{x}<br>状態: %{z}<extra></extra>"
    )
    fig.update_layout(height=max(400, len(cov_df) * 25))
    st.plotly_chart(fig, use_container_width=True)

    cov_df["missing_count"] = len(ALL_METRIC_COLUMNS) - cov_df[ALL_METRIC_COLUMNS].sum(axis=1)
    missing_df = (
        cov_df[cov_df["missing_count"] > 0][["company_name", "edinet_code", "missing_count"]]
        .sort_values("missing_count", ascending=False)
    )
    if not missing_df.empty:
        st.subheader("欠損が多い企業")
        st.dataframe(missing_df, use_container_width=True, hide_index=True)


def _render_completeness(conn: duckdb.DuckDBPyConnection) -> None:
    """年度別指標充足率の推移."""
    st.subheader("年度別 指標充足率")
    st.caption(
        "**充足率 = その年度に当該指標を 1 件以上報告した企業の割合（全企業中）**。"
        "100% に近いほど開示企業が多い指標であることを意味します。"
    )
    comp_df = query_completeness_over_time(conn)
    if comp_df.empty:
        st.info("充足率データがありません")
        return

    pct_cols = [c for c in comp_df.columns if c.endswith("_pct")]
    melted = comp_df.melt(
        id_vars=["fiscal_year"], value_vars=pct_cols,
        var_name="metric", value_name="completeness_pct",
    )
    label_map = {f"{k}_pct": v for k, v in ALL_METRIC_LABELS.items()}
    melted["metric"] = melted["metric"].map(label_map)
    fig = px.line(
        melted, x="fiscal_year", y="completeness_pct", color="metric", markers=True,
        labels={"fiscal_year": "年度", "completeness_pct": "充足率 (%)", "metric": "指標"},
        title="指標充足率の推移",
    )
    fig.update_xaxes(dtick=1)
    fig.update_yaxes(range=[0, 105])
    st.plotly_chart(fig, use_container_width=True)


def _render_evidence(conn: duckdb.DuckDBPyConnection) -> None:
    """抽出方法分布."""
    st.subheader("抽出方法の分布")
    st.caption(
        "各指標がどの方法で抽出されたかの内訳。"
        "**element_id_match**（XBRL要素IDで一致 / 最も信頼性高）→ "
        "**item_name_match**（項目名で一致）→ "
        "**text_fallback**（テキストブロックから正規表現抽出）→ "
        "**llm_fallback**（LLM で抽出）の順に信頼性が下がります。"
    )
    evidence_df = query_evidence_summary(conn)
    if evidence_df.empty:
        st.info("抽出根拠データがありません")
        return

    fig = px.bar(
        evidence_df, x="metric_name", y="evidence_count", color="matched_by", barmode="group",
        labels={"metric_name": "指標名", "evidence_count": "件数", "matched_by": "抽出方法"},
        title="指標別 抽出方法の件数",
    )
    st.plotly_chart(fig, use_container_width=True)
