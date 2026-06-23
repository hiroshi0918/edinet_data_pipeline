"""規模×人的資本 — 財務規模の上位/下位 10 社に人的資本指標を併記する.

選択した財務軸 (売上・営業利益・従業員数) で上位 10 社・下位 10 社を並べ、各社の
女性管理職比率・男女賃金格差を横に置く。「規模が大きい/小さい会社の人的資本開示は
どうか」を読むためのページ。男性育休取得率はノイズが大きいため併記しない。
"""

from __future__ import annotations

import duckdb
import pandas as pd
import streamlit as st

from edinet_pipeline.dashboard.components.filters import (
    render_dimension_filter,
    render_single_year_filter,
)
from edinet_pipeline.dashboard.constants import FINANCIAL_METRIC_LABELS, SIZE_AXIS_METRICS
from edinet_pipeline.dashboard.data import query_financial_ranking_with_hc

_TOP_N = 10

# 下位ランキングの下限 (アーティファクト/空殻除外)。営業利益は巨額赤字が実体なので None。
_BOTTOM_FLOOR: dict[str, float | None] = {
    "sales": 1e8,            # 売上=1 等の抽出アーティファクトを除外 (1 億円未満を切る)
    "operating_profit": None,  # 巨額赤字は実体なのでフィルタしない
    "employee_count": 1,     # 従業員 0 人の特殊会社/持株会社を除外
}
_BOTTOM_FLOOR_NOTE: dict[str, str] = {
    "sales": "下位は売上 1 億円以上に限定 (銀行等の抽出エラーを除外)",
    "operating_profit": "下位はフィルタなし (巨額赤字は実体)",
    "employee_count": "下位は従業員 1 人以上に限定 (0 人の持株会社等を除外)",
}

# 金額系は億円換算、従業員数は人数で表示
_YEN_METRICS = {"sales", "operating_profit"}


def render(conn: duckdb.DuckDBPyConnection) -> None:
    """規模×人的資本ページを描画する."""
    st.header("規模×人的資本")
    st.caption(
        "財務規模の上位 10 社・下位 10 社に、女性管理職比率・男女賃金格差を併記します。"
        "「大企業ほど開示が進んでいるか」「小規模企業はどうか」を読むためのページです。"
    )

    fiscal_year = render_single_year_filter(conn, key_prefix="sizehc")
    scope, worker_type = render_dimension_filter(key_prefix="sizehc")
    if fiscal_year is None:
        st.warning("データがありません")
        return

    metric = st.radio(
        "財務軸を選択",
        options=list(SIZE_AXIS_METRICS),
        format_func=lambda m: FINANCIAL_METRIC_LABELS[m],
        horizontal=True,
        key="sizehc_metric",
    )

    top_df = query_financial_ranking_with_hc(
        conn, metric, fiscal_year, top_n=_TOP_N,
        ascending=False, scope=scope, worker_type=worker_type,
    )
    bottom_df = query_financial_ranking_with_hc(
        conn, metric, fiscal_year, top_n=_TOP_N,
        ascending=True, min_value=_BOTTOM_FLOOR[metric],
        scope=scope, worker_type=worker_type,
    )

    if top_df.empty and bottom_df.empty:
        st.info(
            f"{fiscal_year} 年度・選択次元に {FINANCIAL_METRIC_LABELS[metric]} の"
            "データがありません。"
        )
        return

    col_top, col_bottom = st.columns(2)
    with col_top:
        st.subheader(f"{FINANCIAL_METRIC_LABELS[metric]} 上位 {_TOP_N} 社")
        st.dataframe(
            _format_table(top_df, metric), use_container_width=True, hide_index=True
        )
    with col_bottom:
        st.subheader(f"{FINANCIAL_METRIC_LABELS[metric]} 下位 {_TOP_N} 社")
        st.caption(_BOTTOM_FLOOR_NOTE[metric])
        st.dataframe(
            _format_table(bottom_df, metric), use_container_width=True, hide_index=True
        )


def _format_table(df: pd.DataFrame, metric: str) -> pd.DataFrame:
    """ランキングを表示用 (順位・企業名・財務値・HC 2 指標) に整形する."""
    label = FINANCIAL_METRIC_LABELS[metric]
    cols = ["順位", "企業名", label, "女性管理職比率", "男女賃金格差"]
    if df.empty:
        return pd.DataFrame(columns=cols)
    return pd.DataFrame(
        {
            "順位": range(1, len(df) + 1),
            "企業名": df["company_name"].to_numpy(),
            label: [_format_value(v, metric) for v in df["value"]],
            "女性管理職比率": [_format_pct(v) for v in df["female_manager_ratio"]],
            "男女賃金格差": [_format_pct(v) for v in df["gender_wage_gap"]],
        }
    )


def _format_value(value: object, metric: str) -> str:
    if value is None or pd.isna(value):
        return "—"
    if metric in _YEN_METRICS:
        return f"{float(value) / 1e8:,.1f} 億円"
    return f"{int(value):,} 人"


def _format_pct(value: object) -> str:
    if value is None or pd.isna(value):
        return "—"
    return f"{float(value):.1f} %"
