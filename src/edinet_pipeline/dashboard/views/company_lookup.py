"""企業を調べる — 会社名・年度・次元で 1 社の有価証券報告書の値を確認する.

トップページ。会社名 (全件検索付き selectbox) と年度、開示範囲 (scope) ×
労働者区分 (worker_type) を選ぶと、その 1 次元分の 7 指標 (財務 4 + 人的資本 3)
を表で表示する。深掘りの peer 比較は「企業スポットライト」ページが担う。
"""

from __future__ import annotations

import duckdb
import pandas as pd
import streamlit as st

from edinet_pipeline.dashboard.constants import (
    FINANCIAL_METRIC_LABELS,
    HC_METRIC_LABELS,
    SCOPE_LABELS,
    WORKER_TYPE_LABELS,
)
from edinet_pipeline.dashboard.data import (
    query_available_companies,
    query_company_profile,
    query_kpi_summary,
)

# 表示順 (財務 4 → 人的資本 3) とラベル
_METRIC_LABELS: dict[str, str] = {**FINANCIAL_METRIC_LABELS, **HC_METRIC_LABELS}
_FINANCIAL_COLS: tuple[str, ...] = tuple(FINANCIAL_METRIC_LABELS.keys())


def render(conn: duckdb.DuckDBPyConnection) -> None:
    """企業を調べるページを描画する."""
    st.header("企業を調べる")
    st.caption(
        "会社名・年度・開示範囲を選んで、その 1 社の有価証券報告書に記載された "
        "財務指標と人的資本指標を確認します。"
    )

    _render_data_range(conn)

    edinet_code, company_name = _render_company_selector(conn)
    if not edinet_code:
        st.info("企業を選択してください")
        return

    profile_df = query_company_profile(conn, edinet_code)
    if profile_df.empty:
        st.warning(f"{company_name} のデータが見つかりません")
        return

    fiscal_year, scope, worker_type = _render_dimension_selector(profile_df)
    row = _select_row(profile_df, fiscal_year, scope, worker_type)

    _render_identity(profile_df, edinet_code, fiscal_year, scope, worker_type)
    if row is None:
        st.warning(
            f"選択した次元 ({SCOPE_LABELS.get(scope, scope)} × "
            f"{WORKER_TYPE_LABELS.get(worker_type, worker_type)}) に該当する行が"
            f"{fiscal_year} 年度にありません。次元を切り替えてください。"
        )
        return
    _render_metric_table(row)


# ------------------------------------------------------------------ #
#  内部レンダラ
# ------------------------------------------------------------------ #


def _render_data_range(conn: duckdb.DuckDBPyConnection) -> None:
    """データ範囲 (企業数=年度重複排除・年度数・最新提出日) を上部に示す."""
    kpi = query_kpi_summary(conn)
    col1, col2, col3 = st.columns(3)
    col1.metric("企業数 (年度重複排除)", f"{kpi['company_count']:,} 社")
    col2.metric("収録年度数", f"{kpi['year_count']} 年度")
    latest = kpi["latest_submission"]
    col3.metric("最新提出日", str(latest) if latest is not None else "—")
    st.divider()


def _render_company_selector(
    conn: duckdb.DuckDBPyConnection,
) -> tuple[str | None, str | None]:
    """全企業を 1 つの検索付き selectbox で選ばせ、edinet_code を返す."""
    companies = query_available_companies(conn)
    if companies.empty:
        st.warning("企業データがありません")
        return None, None
    # ラベル "会社名 (edinet_code)" → edinet_code の対応表
    options = {
        f"{r['company_name']} ({r['edinet_code']})": r["edinet_code"]
        for _, r in companies.iterrows()
    }
    chosen = st.selectbox(
        "会社名で検索・選択",
        options=list(options.keys()),
        index=0,
        help="入力すると部分一致で絞り込めます。",
    )
    edinet_code = options[chosen]
    company_name = chosen.rsplit(" (", 1)[0]
    return edinet_code, company_name


def _render_dimension_selector(profile_df: pd.DataFrame) -> tuple[int, str, str]:
    """年度・scope・worker_type のセレクタを描画する (年度は実在年度のみ)."""
    years = sorted(profile_df["fiscal_year"].unique(), reverse=True)
    col1, col2, col3 = st.columns(3)
    fiscal_year = int(col1.selectbox("年度", years, key="lookup_year"))
    scope = col2.selectbox(
        "開示範囲 (scope)",
        options=list(SCOPE_LABELS.keys()),
        format_func=lambda s: SCOPE_LABELS[s],
        key="lookup_scope",
    )
    worker_type = col3.selectbox(
        "労働者区分",
        options=list(WORKER_TYPE_LABELS.keys()),
        format_func=lambda w: WORKER_TYPE_LABELS[w],
        key="lookup_worker",
    )
    return fiscal_year, scope, worker_type


def _select_row(
    profile_df: pd.DataFrame, fiscal_year: int, scope: str, worker_type: str
) -> pd.Series | None:
    df = profile_df[
        (profile_df["fiscal_year"] == fiscal_year)
        & (profile_df["scope"] == scope)
        & (profile_df["worker_type"] == worker_type)
    ]
    return None if df.empty else df.iloc[0]


def _render_identity(
    profile_df: pd.DataFrame,
    edinet_code: str,
    fiscal_year: int,
    scope: str,
    worker_type: str,
) -> None:
    """企業の同定情報 (社名・業種・対象次元) を示す."""
    head = profile_df.iloc[0]
    industry = head.get("industry") or "(業種未取得)"
    st.markdown(
        f"- **企業名**: {head['company_name']} (`{edinet_code}`)\n"
        f"- **業種**: {industry}\n"
        f"- **対象**: {fiscal_year} 年度 / {SCOPE_LABELS.get(scope, scope)} × "
        f"{WORKER_TYPE_LABELS.get(worker_type, worker_type)}"
    )


def _render_metric_table(row: pd.Series) -> None:
    """7 指標を縦持ちの表で表示する (財務は桁区切り、HC は % 表記)."""
    records = []
    for col, label in _METRIC_LABELS.items():
        value = row.get(col)
        if value is None or pd.isna(value):
            display = "—"
        elif col in _FINANCIAL_COLS:
            display = f"{int(value):,}"
        else:
            display = f"{float(value):.1f} %"
        records.append({"指標": label, "値": display})
    table = pd.DataFrame(records)
    st.subheader("有価証券報告書の値")
    st.dataframe(table, use_container_width=True, hide_index=True)
    st.caption(
        "財務指標は円単位。人的資本指標は提出会社/連結子会社・労働者区分で値が異なる"
        "ため、上の次元セレクタで切り替えてください。"
    )
