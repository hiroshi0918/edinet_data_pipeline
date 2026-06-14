"""企業スポットライト — 単一企業の人的資本指標を peer と並べて評価する."""

from __future__ import annotations

import duckdb
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from edinet_pipeline.dashboard.constants import (
    HC_METRIC_LABELS,
    RATIO_DISPLAY_MAX,
    RATIO_DISPLAY_MIN,
    SCOPE_LABELS,
    WORKER_TYPE_LABELS,
)
from edinet_pipeline.dashboard.data import (
    detect_evaluation_scope,
    query_company_industry_rank,
    query_company_profile,
    query_ideal_cluster,
    query_industry_peers,
    query_size_peers,
    search_company_by_name,
)
from edinet_pipeline.models import SCOPE_CONSOLIDATED_SUBSIDIARY

_HC_COLS: tuple[str, ...] = tuple(HC_METRIC_LABELS.keys())


def render(conn: duckdb.DuckDBPyConnection) -> None:
    """企業スポットライトページを描画する."""
    st.header("企業スポットライト")
    st.caption(
        "単一の企業について、人的資本指標 3 つ（女性管理職比率・男性育休取得率・男女賃金格差）を "
        "**業界 peer** と **規模類似 peer** の両方の分布に並べて、"
        "「**理想値**」との差分を確認します。"
    )

    edinet_code, company_label = _render_company_selector(conn)
    if not edinet_code:
        st.info("企業を選択してください")
        return

    profile_df = query_company_profile(conn, edinet_code)
    if profile_df.empty:
        st.warning(f"{company_label} のデータが見つかりません")
        return

    fiscal_year, scope, worker_type = _render_dimension_selector(conn, edinet_code, profile_df)

    _render_company_summary(profile_df, edinet_code, fiscal_year, scope, worker_type)
    _render_industry_rank(conn, edinet_code, fiscal_year, scope, worker_type)
    target_row = _get_target_row(profile_df, fiscal_year, scope, worker_type)
    if target_row is None:
        st.warning(
            f"選択次元 ({SCOPE_LABELS.get(scope, scope)}) × {worker_type} "
            "に該当する行がありません。"
        )
        return

    industry_peers = query_industry_peers(
        conn, target_row.get("industry"), fiscal_year, scope, worker_type
    )
    size_peers = query_size_peers(
        conn,
        int(target_row.get("employee_count") or 0),
        fiscal_year, scope, worker_type,
    )
    ideal_cluster = query_ideal_cluster(conn, fiscal_year, scope, worker_type)

    _render_peer_violin("業界 peer 分布", industry_peers, target_row, group_label="業界 peer")
    _render_peer_violin(
        "規模類似 peer 分布（対数スケール ±0.3 dex）",
        size_peers,
        target_row,
        group_label="規模 peer",
    )
    _render_ideal_table(target_row, industry_peers, size_peers, ideal_cluster)


# ------------------------------------------------------------------ #
#  内部レンダラ
# ------------------------------------------------------------------ #


def _render_company_selector(
    conn: duckdb.DuckDBPyConnection,
) -> tuple[str | None, str | None]:
    """会社名検索 + 候補ドロップダウンで edinet_code を返す."""
    default_query = st.session_state.get("spotlight_query", "セプテーニ")
    query = st.text_input(
        "企業名で検索（部分一致）",
        value=default_query,
        key="spotlight_query",
    )
    candidates = search_company_by_name(conn, query, limit=50)
    if candidates.empty:
        return None, None
    options = [
        (row["edinet_code"], f"{row['company_name']} ({row['edinet_code']})")
        for _, row in candidates.iterrows()
    ]
    labels = [label for _, label in options]
    chosen = st.selectbox("企業を選択", options=labels, key="spotlight_chosen")
    edinet_code = next(code for code, label in options if label == chosen)
    return edinet_code, chosen


def _render_dimension_selector(
    conn: duckdb.DuckDBPyConnection,
    edinet_code: str,
    profile_df: pd.DataFrame,
) -> tuple[int, str, str]:
    """年度・scope・worker_type を選ぶ. scope は自動推定/手動を切替可能."""
    years = sorted(profile_df["fiscal_year"].unique(), reverse=True)
    col1, col2, col3 = st.columns(3)
    fiscal_year = int(col1.selectbox("年度", years, key="spotlight_year"))

    mode = col2.radio(
        "評価次元",
        options=["自動推定", "手動指定"],
        horizontal=True,
        key="spotlight_scope_mode",
    )
    if mode == "自動推定":
        auto_scope = detect_evaluation_scope(conn, edinet_code, fiscal_year)
        scope = auto_scope
        col2.caption(
            f"自動推定: **{SCOPE_LABELS.get(scope, scope)}**"
            + (
                "（提出会社の指標が NULL のため連結子会社で評価）"
                if scope == SCOPE_CONSOLIDATED_SUBSIDIARY
                else "（提出会社の指標で評価）"
            )
        )
    else:
        scope_options = list(SCOPE_LABELS.keys())
        scope = col2.selectbox(
            "scope",
            options=scope_options,
            format_func=lambda s: SCOPE_LABELS[s],
            key="spotlight_scope_manual",
        )

    worker_type = col3.selectbox(
        "労働者区分",
        options=list(WORKER_TYPE_LABELS.keys()),
        format_func=lambda w: WORKER_TYPE_LABELS[w],
        key="spotlight_worker",
    )
    return fiscal_year, scope, worker_type


def _render_company_summary(
    profile_df: pd.DataFrame,
    edinet_code: str,
    fiscal_year: int,
    scope: str,
    worker_type: str,
) -> None:
    """企業プロファイル + 該当行のサマリ."""
    st.subheader("企業プロファイル")
    head = profile_df.iloc[0]
    industry = head.get("industry") or "(industry 未取得)"
    st.markdown(
        f"- **企業名**: {head['company_name']} (`{edinet_code}`)\n"
        f"- **業界**: {industry}\n"
        f"- **評価次元**: {SCOPE_LABELS.get(scope, scope)} × "
        f"{WORKER_TYPE_LABELS.get(worker_type, worker_type)}\n"
        f"- **対象年度**: {fiscal_year}"
    )
    pivot = profile_df.set_index(["fiscal_year", "scope", "worker_type"])[
        list(_HC_COLS) + ["sales", "operating_profit", "employee_count"]
    ]
    st.dataframe(pivot, use_container_width=True)


def _render_industry_rank(
    conn: duckdb.DuckDBPyConnection,
    edinet_code: str,
    fiscal_year: int,
    scope: str,
    worker_type: str,
) -> None:
    """選択企業の業種内ランクを 3 指標で表示する."""
    rank = query_company_industry_rank(conn, edinet_code, fiscal_year, scope, worker_type)
    if not rank or not rank.get("industry"):
        return
    st.subheader(f"業種内ランク（{rank['industry']}・{fiscal_year}年度）")
    st.caption(f"同業種 {rank['industry_total']} 社の中でこの企業がどの位置にいるか")
    col1, col2, col3 = st.columns(3)
    col1.metric(
        "売上高 ランク",
        f"{rank['sales_rank']} 位" if rank.get("sales_rank") else "—",
        delta=f"/ {rank['industry_with_sales']} 社中" if rank.get("sales_rank") else None,
        delta_color="off",
    )
    col2.metric(
        "営業利益 ランク",
        f"{rank['operating_profit_rank']} 位" if rank.get("operating_profit_rank") else "—",
        delta=f"/ {rank['industry_total']} 社中" if rank.get("operating_profit_rank") else None,
        delta_color="off",
    )
    col3.metric(
        "女性管理職比率 ランク",
        f"{rank['female_manager_ratio_rank']} 位" if rank.get("female_manager_ratio_rank") else "—",
        delta=(
            f"/ {rank['industry_with_fmr']} 社中"
            if rank.get("female_manager_ratio_rank") else None
        ),
        delta_color="off",
    )


def _get_target_row(
    profile_df: pd.DataFrame, fiscal_year: int, scope: str, worker_type: str
) -> pd.Series | None:
    df = profile_df[
        (profile_df["fiscal_year"] == fiscal_year)
        & (profile_df["scope"] == scope)
        & (profile_df["worker_type"] == worker_type)
    ]
    if df.empty:
        return None
    return df.iloc[0]


def _render_peer_violin(
    section_title: str,
    peer_df: pd.DataFrame,
    target_row: pd.Series,
    group_label: str,
) -> None:
    """3 指標のヴァイオリンプロット + 当該企業の縦線."""
    st.subheader(section_title)
    n = len(peer_df)
    if peer_df.empty:
        st.info(f"{section_title} に該当する peer がありません（n=0）。")
        return
    st.caption(f"{group_label}: {_peer_size_note(n)}")

    cols = st.columns(3)
    for ax, metric in zip(cols, _HC_COLS, strict=True):
        values = peer_df[metric].dropna().astype(float)
        target_value = target_row.get(metric)
        with ax:
            fig = go.Figure()
            if not values.empty:
                fig.add_trace(
                    go.Violin(
                        y=values,
                        name=group_label,
                        box_visible=True,
                        meanline_visible=True,
                        points="all",
                        marker=dict(opacity=0.4),
                    )
                )
            if target_value is not None and pd.notna(target_value):
                fig.add_hline(
                    y=float(target_value),
                    line_color="red",
                    line_width=2,
                    annotation_text=f"対象: {float(target_value):.1f}%",
                    annotation_position="top left",
                )
            fig.update_layout(
                title=HC_METRIC_LABELS[metric],
                height=350,
                showlegend=False,
            )
            if metric == "male_childcare_leave_ratio":
                fig.update_yaxes(range=[RATIO_DISPLAY_MIN, RATIO_DISPLAY_MAX])
            st.plotly_chart(fig, use_container_width=True)


def _render_ideal_table(
    target_row: pd.Series,
    industry_peers: pd.DataFrame,
    size_peers: pd.DataFrame,
    ideal_cluster: pd.DataFrame,
) -> None:
    """「4 種の理想値」と当該企業の差分テーブル."""
    st.subheader("4 種の「理想値」と現在値の差分")
    st.caption(
        "**業界 P75** / **規模 peer P75** / "
        "**理想クラスタ平均** (3 指標すべて P75 以上 AND 営業利益率 P50 以上) / "
        "**業界トップ10 平均** を並べて、ロールモデル像を多角的に提示します。"
    )

    rows = []
    for metric in _HC_COLS:
        target_value = target_row.get(metric)
        target_value_f = float(target_value) if pd.notna(target_value) else None
        ind_p75 = _percentile(industry_peers, metric, 75)
        size_p75 = _percentile(size_peers, metric, 75)
        cluster_avg = (
            float(ideal_cluster[metric].dropna().mean())
            if not ideal_cluster.empty and ideal_cluster[metric].notna().any()
            else None
        )
        top10_avg = _top_n_mean(industry_peers, metric, 10)
        rows.append({
            "指標": HC_METRIC_LABELS[metric],
            "現在値": target_value_f,
            "業界 P75": ind_p75,
            "規模 peer P75": size_p75,
            "理想クラスタ平均": cluster_avg,
            "業界トップ10 平均": top10_avg,
        })
    df = pd.DataFrame(rows)
    formatters = {
        c: "{:.2f}".format
        for c in df.columns
        if c != "指標"
    }
    st.dataframe(
        df.style.format(formatters, na_rep="—"),
        use_container_width=True,
        hide_index=True,
    )

    if not ideal_cluster.empty:
        st.caption(
            f"理想クラスタの構成企業数: **{len(ideal_cluster)}** 社。"
            "クラスタ業種分布を以下に示します。"
        )
        if "industry" in ideal_cluster.columns:
            industry_counts = (
                ideal_cluster["industry"].fillna("(未取得)").value_counts()
            )
            st.dataframe(industry_counts, use_container_width=True)


def _peer_size_note(n: int) -> str:
    """peer 件数からサンプル数注記文字列を返す."""
    if n < 5:
        return f"⚠️ n={n} は参考値（信頼区間が極めて広い）"
    if n < 10:
        return f"ℹ️ n={n} は少なめ（bootstrap CI 推奨レベル）"
    return f"n={n}"


def _percentile(df: pd.DataFrame, metric: str, q: int) -> float | None:
    if df.empty or metric not in df.columns:
        return None
    values = df[metric].dropna().astype(float)
    if values.empty:
        return None
    return float(values.quantile(q / 100))


def _top_n_mean(df: pd.DataFrame, metric: str, n: int) -> float | None:
    if df.empty or metric not in df.columns:
        return None
    values = df[metric].dropna().astype(float).sort_values(ascending=False)
    if values.empty:
        return None
    return float(values.head(n).mean())
