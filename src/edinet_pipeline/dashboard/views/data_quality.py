"""データ品質ページ — 開示充足率と業種・規模別の診断.

v0.4 改修: 旧版の 4000 社×7指標の二値ヒートマップ（高さ約 10 万 px で実質
閲覧不能）を撤廃し、「業種別・規模別の開示充足度を診断するツール」に再設計。
"""

from __future__ import annotations

import duckdb
import plotly.express as px
import streamlit as st

from edinet_pipeline.dashboard.components.filters import (
    render_fiscal_year_filter,
    render_industry_filter,
)
from edinet_pipeline.dashboard.constants import (
    ALL_METRIC_LABELS,
    SALES_TIER_ORDER,
)
from edinet_pipeline.dashboard.data import (
    query_company_completeness,
    query_completeness_over_time,
    query_evidence_summary,
    query_industry_completeness,
    query_overall_completeness_kpi,
    query_size_completeness,
    query_unreported_top_companies,
)


def render(conn: duckdb.DuckDBPyConnection) -> None:
    """データ品質ページを描画する."""
    st.header("データ品質")
    st.info(
        "**このページは何のため？**\n\n"
        "EDINET から取得した企業データのうち、"
        "**どの企業の・どの指標が・どれだけ揃っているか**を診断します。"
        "業種・規模ごとの開示傾向を把握することで、人的資本情報の開示が進んでいる業種・遅れている業種が分かります。\n\n"
        "**充足率の定義**: 各企業は財務 4 指標（売上・営業利益・純利益・従業員数）と人的資本 3 指標"
        "（女性管理職比率・男性育休取得率・男女賃金格差）の計 **7 指標**を報告します。"
        "充足率 = 報告した指標数 / 7 × 100% です。"
    )

    year_min, year_max = render_fiscal_year_filter(conn, key_prefix="dq")
    if year_min == 0:
        return
    industry_filter = render_industry_filter(conn, key_prefix="dq")

    year = int(
        st.number_input(
            "対象年度", min_value=year_min, max_value=year_max, value=year_max,
            key="dq_year",
        )
    )

    _render_overall_kpi(conn, year)
    _render_industry_completeness(conn, year)
    _render_size_completeness(conn, year)
    _render_unreported_highlight(conn, year)
    _render_company_completeness_table(conn, year, industry_filter)
    _render_completeness_over_time(conn)
    _render_evidence_distribution(conn)


def _render_overall_kpi(conn: duckdb.DuckDBPyConnection, year: int) -> None:
    """全体充足率 KPI."""
    st.subheader(f"全体充足率（{year}年度）")
    kpi = query_overall_completeness_kpi(conn, year)
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("対象企業数", f"{kpi['total_companies']:,}")
    col2.metric("7指標すべて揃った企業", f"{kpi['full_companies']:,}")
    col3.metric("完全開示率", f"{kpi['full_pct']:.1f}%")
    col4.metric("平均充足率", f"{kpi['avg_completeness_pct']:.1f}%")
    st.caption(
        "**完全開示率** = 7 指標すべてを揃えた企業の割合。"
        "**平均充足率** = 各企業の充足率（7 中いくつ報告したか）の平均。"
    )


def _render_industry_completeness(conn: duckdb.DuckDBPyConnection, year: int) -> None:
    """業種別 充足率ランキング."""
    st.subheader("業種別の開示充足率")
    df = query_industry_completeness(conn, year)
    if df.empty:
        st.info("業種別のデータがありません")
        return

    tab_overall, tab_hc = st.tabs(["7 指標合計", "人的資本 3 指標のみ"])
    with tab_overall:
        top10 = df.head(10).sort_values("overall_pct")
        bottom10 = df.tail(10).sort_values("overall_pct")
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**開示が進んでいる業種 TOP10**")
            fig = px.bar(
                top10, x="overall_pct", y="industry", orientation="h",
                labels={"overall_pct": "充足率 (%)", "industry": ""},
                hover_data=["n_companies"],
            )
            fig.update_layout(height=340, margin=dict(l=0, r=0, t=10, b=0))
            st.plotly_chart(fig, use_container_width=True)
        with col2:
            st.markdown("**開示が遅れている業種 WORST10**")
            fig = px.bar(
                bottom10, x="overall_pct", y="industry", orientation="h",
                labels={"overall_pct": "充足率 (%)", "industry": ""},
                hover_data=["n_companies"],
            )
            fig.update_layout(height=340, margin=dict(l=0, r=0, t=10, b=0))
            st.plotly_chart(fig, use_container_width=True)
    with tab_hc:
        df_hc = df.sort_values("hc_pct", ascending=False)
        top10 = df_hc.head(10).sort_values("hc_pct")
        bottom10 = df_hc.tail(10).sort_values("hc_pct")
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**人的資本開示が進んでいる業種 TOP10**")
            fig = px.bar(
                top10, x="hc_pct", y="industry", orientation="h",
                labels={"hc_pct": "HC 3指標充足率 (%)", "industry": ""},
                hover_data=["n_companies"],
            )
            fig.update_layout(height=340, margin=dict(l=0, r=0, t=10, b=0))
            st.plotly_chart(fig, use_container_width=True)
        with col2:
            st.markdown("**人的資本開示が遅れている業種 WORST10**")
            fig = px.bar(
                bottom10, x="hc_pct", y="industry", orientation="h",
                labels={"hc_pct": "HC 3指標充足率 (%)", "industry": ""},
                hover_data=["n_companies"],
            )
            fig.update_layout(height=340, margin=dict(l=0, r=0, t=10, b=0))
            st.plotly_chart(fig, use_container_width=True)


def _render_size_completeness(conn: duckdb.DuckDBPyConnection, year: int) -> None:
    """売上規模別の充足率."""
    st.subheader("売上規模別の開示充足率")
    st.caption("「大企業ほど人的資本情報を開示しているか？」を売上階層で診断します。")
    df = query_size_completeness(conn, year)
    if df.empty:
        st.info("規模別のデータがありません")
        return
    df_sorted = (
        df.set_index("tier")
        .reindex(SALES_TIER_ORDER)
        .dropna(subset=["hc_overall_pct"])
        .reset_index()
    )
    fig = px.bar(
        df_sorted,
        x="tier",
        y="hc_overall_pct",
        labels={"tier": "売上階層", "hc_overall_pct": "HC 3指標充足率 (%)"},
        text="hc_overall_pct",
        hover_data=["n_companies", "female_manager_ratio_pct",
                    "male_childcare_leave_ratio_pct", "gender_wage_gap_pct"],
    )
    fig.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
    fig.update_layout(yaxis_range=[0, 105])
    st.plotly_chart(fig, use_container_width=True)


def _render_unreported_highlight(conn: duckdb.DuckDBPyConnection, year: int) -> None:
    """売上TOPで人的資本未提出企業ハイライト."""
    st.subheader("売上 TOP で人的資本未開示の企業")
    st.caption(
        "売上規模上位の企業のうち、人的資本 3 指標（女性管理職比率・男性育休取得率・男女賃金格差）"
        "のいずれかを開示していない企業を一覧します。大企業ほど開示義務感は強いが、実際の状況を診断できます。"
    )
    df = query_unreported_top_companies(conn, year, top_n=20)
    if df.empty:
        st.success("売上 TOP に未開示企業はありません")
        return
    display_df = df.rename(
        columns={
            "company_name": "企業名",
            "industry": "業種",
            "sales": "売上高",
            "female_manager_ratio": "女性管理職比率",
            "male_childcare_leave_ratio": "男性育休取得率",
            "gender_wage_gap": "男女賃金格差",
            "missing_hc_count": "HC未開示数",
        }
    )[["企業名", "業種", "売上高", "HC未開示数",
       "女性管理職比率", "男性育休取得率", "男女賃金格差"]]
    st.dataframe(
        display_df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "売上高": st.column_config.NumberColumn(format="¥%,d"),
            "HC未開示数": st.column_config.NumberColumn(format="%d / 3"),
            "女性管理職比率": st.column_config.NumberColumn(format="%.1f %%"),
            "男性育休取得率": st.column_config.NumberColumn(format="%.1f %%"),
            "男女賃金格差": st.column_config.NumberColumn(format="%.1f %%"),
        },
    )


def _render_company_completeness_table(
    conn: duckdb.DuckDBPyConnection,
    year: int,
    industry_filter: tuple[str, ...],
) -> None:
    """企業別の充足率テーブル."""
    st.subheader("企業別の充足率（業種フィルタ連動）")
    st.caption(
        "各企業の充足率（7 指標中いくつ報告したか）。"
        "サイドバーで業種を絞り込むとここに反映されます。"
        "テーブルの列ヘッダクリックでソート、フィルタ機能でさらに絞り込めます。"
    )
    df = query_company_completeness(conn, year, industry_filter=industry_filter)
    if df.empty:
        st.info("該当企業がありません")
        return
    display_df = df.rename(
        columns={
            "company_name": "企業名",
            "industry": "業種",
            "sales": "売上高",
            "reported_count": "報告指標数",
            "completeness_pct": "充足率",
        }
    )[["企業名", "業種", "売上高", "報告指標数", "充足率"]]
    st.dataframe(
        display_df,
        use_container_width=True,
        hide_index=True,
        height=400,
        column_config={
            "売上高": st.column_config.NumberColumn(format="¥%,d"),
            "報告指標数": st.column_config.NumberColumn(format="%d / 7"),
            "充足率": st.column_config.ProgressColumn(
                format="%.0f %%", min_value=0, max_value=100,
            ),
        },
    )


def _render_completeness_over_time(conn: duckdb.DuckDBPyConnection) -> None:
    """年度別 指標充足率の推移（既存セクションを維持）."""
    st.subheader("年度別 指標充足率の推移")
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


def _render_evidence_distribution(conn: duckdb.DuckDBPyConnection) -> None:
    """抽出方法分布（既存セクションを維持）."""
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
