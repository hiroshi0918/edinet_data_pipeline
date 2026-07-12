"""企業を調べる — 会社名・年度・次元で 1 社の有価証券報告書の値を確認する.

トップページ。会社名 (全件検索付き selectbox) と年度、開示範囲 (scope) ×
労働者区分 (worker_type) を選ぶと、その 1 次元分の 10 指標
(財務 4 + 人的資本 3 + 従業員情報 3) を表で表示する。
深掘りの peer 比較は「企業スポットライト」ページが担う。
"""

from __future__ import annotations

from collections.abc import Callable

import duckdb
import pandas as pd
import streamlit as st

from edinet_pipeline.dashboard.constants import (
    EMPLOYEE_INFO_METRIC_LABELS,
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
from edinet_pipeline.dashboard.theme import page_header, ratio_bar_card_html
from edinet_pipeline.models import SCOPE_REPORTING_COMPANY, WORKER_TYPE_ALL

# 表示順 (財務 4 → 人的資本 3 → 従業員情報 3)
_FINANCIAL_COLS: tuple[str, ...] = tuple(FINANCIAL_METRIC_LABELS.keys())
_HC_COLS: tuple[str, ...] = tuple(HC_METRIC_LABELS.keys())
_EMPLOYEE_INFO_COLS: tuple[str, ...] = tuple(EMPLOYEE_INFO_METRIC_LABELS.keys())


def render(conn: duckdb.DuckDBPyConnection) -> None:
    """企業を調べるページを描画する."""
    page_header(
        "COMPANY LOOKUP",
        "企業を調べる",
        "会社名・年度・開示範囲を選ぶと、その 1 社の有価証券報告書に記載された "
        "財務指標と人的資本指標を一枚で確認できます。",
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
    else:
        _render_metric_table(row)
        _render_employee_info(profile_df, fiscal_year)
    _render_history_table(profile_df, edinet_code, scope, worker_type)


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
    """全企業を 1 つの検索付き selectbox で選ばせ、edinet_code を返す.

    URL の ?company=<edinet_code> を初期選択に反映し、選択結果を URL に
    書き戻すことで、特定企業へのリンクを共有できるようにする。
    """
    companies = query_available_companies(conn)
    if companies.empty:
        st.warning("企業データがありません")
        return None, None
    # ラベル "会社名 (edinet_code)" → edinet_code の対応表
    options = {
        f"{r['company_name']} ({r['edinet_code']})": r["edinet_code"]
        for _, r in companies.iterrows()
    }
    codes = list(options.values())
    requested_code = st.query_params.get("company", "")
    initial_index = codes.index(requested_code) if requested_code in codes else 0
    chosen = st.selectbox(
        "会社名で検索・選択",
        options=list(options.keys()),
        index=initial_index,
        help="入力すると部分一致で絞り込めます。",
    )
    edinet_code = options[chosen]
    company_name = chosen.rsplit(" (", 1)[0]
    st.query_params["company"] = edinet_code
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
    """7 指標を財務メトリクスカードと人的資本のパリティバーで表示する."""
    st.subheader("財務指標")
    fin_cols = st.columns(len(_FINANCIAL_COLS))
    for ax, col in zip(fin_cols, _FINANCIAL_COLS, strict=True):
        ax.metric(FINANCIAL_METRIC_LABELS[col], _format_financial(row.get(col), col))

    st.subheader("人的資本指標")
    hc_cols = st.columns(len(_HC_COLS))
    for ax, col in zip(hc_cols, _HC_COLS, strict=True):
        value = row.get(col)
        v = float(value) if value is not None and pd.notna(value) else None
        ax.markdown(ratio_bar_card_html(HC_METRIC_LABELS[col], v), unsafe_allow_html=True)
    st.caption(
        "バーは 0%(淡い赤) → 100%(淡い緑) のパリティ目盛り。人的資本指標は"
        "提出会社/連結子会社・労働者区分で値が異なるため、上の次元セレクタで切り替えられます。"
    )


def _format_financial(value: object, col: str) -> str:
    """財務値を桁の大きい売上・利益は億円、従業員数は人で表示する."""
    if value is None or pd.isna(value):
        return "—"
    if col == "employee_count":
        return f"{int(value):,} 人"
    return f"{float(value) / 1e8:,.1f} 億円"


def _render_employee_info(profile_df: pd.DataFrame, fiscal_year: int) -> None:
    """従業員情報 3 指標 (平均年間給与・平均勤続年数・平均年齢) を表示する.

    「従業員の状況」の提出会社単体開示のため、次元セレクタとは独立に
    (reporting_company, all) の行から値を取る。
    """
    base = profile_df[
        (profile_df["fiscal_year"] == fiscal_year)
        & (profile_df["scope"] == SCOPE_REPORTING_COMPANY)
        & (profile_df["worker_type"] == WORKER_TYPE_ALL)
    ]
    row = base.iloc[0] if not base.empty else None

    st.subheader("従業員情報")
    cols = st.columns(len(_EMPLOYEE_INFO_COLS))
    for ax, col in zip(cols, _EMPLOYEE_INFO_COLS, strict=True):
        value = row.get(col) if row is not None else None
        ax.metric(EMPLOYEE_INFO_METRIC_LABELS[col], _format_employee_info(value, col))
    st.caption(
        "「従業員の状況」に記載される提出会社単体の値。"
        "開示範囲・労働者区分セレクタの影響を受けません。"
    )


def _format_employee_info(value: object, col: str) -> str:
    """従業員情報の値を単位付きで表示する (給与は万円へ丸める)."""
    if value is None or pd.isna(value):
        return "—"
    if col == "average_annual_salary":
        return f"{float(value) / 1e4:,.0f} 万円"
    if col == "average_years_of_service":
        return f"{float(value):.1f} 年"
    return f"{float(value):.1f} 歳"


# ------------------------------------------------------------------ #
#  年度推移テーブル
# ------------------------------------------------------------------ #

# 推移表の行定義: (カラム名, 行ラベル, フォーマッタ)。
# 有報の「主要な経営指標等の推移」に倣い、指標を行・年度を列に置く。
_HISTORY_ROWS: tuple[tuple[str, str, Callable[[float], str]], ...] = (
    ("sales", "売上高 (億円)", lambda v: f"{v / 1e8:,.1f}"),
    ("operating_profit", "営業利益 (億円)", lambda v: f"{v / 1e8:,.1f}"),
    ("net_profit", "純利益 (億円)", lambda v: f"{v / 1e8:,.1f}"),
    ("employee_count", "従業員数 (人)", lambda v: f"{int(v):,}"),
    ("female_manager_ratio", "女性管理職比率 (%)", lambda v: f"{v:.1f}"),
    ("male_childcare_leave_ratio", "男性育休取得率 (%)", lambda v: f"{v:.1f}"),
    ("gender_wage_gap", "男女賃金格差 (%)", lambda v: f"{v:.1f}"),
    ("average_annual_salary", "平均年間給与 (万円)", lambda v: f"{v / 1e4:,.0f}"),
    ("average_years_of_service", "平均勤続年数 (年)", lambda v: f"{v:.1f}"),
    ("average_age", "平均年齢 (歳)", lambda v: f"{v:.1f}"),
)

# 従業員情報は提出会社単体開示のため、次元セレクタに関わらず固定次元から取る
_EMPLOYEE_INFO_COL_SET = frozenset(EMPLOYEE_INFO_METRIC_LABELS)


def _build_history_frame(
    profile_df: pd.DataFrame, scope: str, worker_type: str
) -> pd.DataFrame:
    """指標 (行) × 年度 (列) の推移表を組み立てる (表示用フォーマット済み).

    財務・人的資本指標は指定次元 (scope × worker_type) の行から、
    従業員情報3指標は提出会社単体 (reporting_company, all) の行から取る
    (上部カードセクションと同じ規則)。欠損は "—" で埋める。
    """
    dim_rows = profile_df[
        (profile_df["scope"] == scope) & (profile_df["worker_type"] == worker_type)
    ].set_index("fiscal_year")
    base_rows = profile_df[
        (profile_df["scope"] == SCOPE_REPORTING_COMPANY)
        & (profile_df["worker_type"] == WORKER_TYPE_ALL)
    ].set_index("fiscal_year")

    years = sorted(profile_df["fiscal_year"].unique(), reverse=True)
    table: dict[str, list[str]] = {}
    for year in years:
        cells: list[str] = []
        for column, _, formatter in _HISTORY_ROWS:
            source = base_rows if column in _EMPLOYEE_INFO_COL_SET else dim_rows
            value = source.at[year, column] if year in source.index else None
            if value is None or pd.isna(value):
                cells.append("—")
            else:
                cells.append(formatter(float(value)))
        table[f"{year}年度"] = cells

    frame = pd.DataFrame(table, index=[label for _, label, _ in _HISTORY_ROWS])
    frame.index.name = "指標"
    return frame


def _render_history_table(
    profile_df: pd.DataFrame, edinet_code: str, scope: str, worker_type: str
) -> None:
    """全年度×全指標の推移表と、生データの CSV ダウンロードを表示する."""
    st.subheader("年度推移 (全データ)")
    frame = _build_history_frame(profile_df, scope, worker_type)
    st.dataframe(frame, use_container_width=True)
    st.caption(
        "財務・人的資本指標は選択中の開示範囲×労働者区分、従業員情報は提出会社単体の値。"
        "CSV には全次元の生値 (円・%) がそのまま入ります。"
    )
    csv_bytes = profile_df.to_csv(index=False).encode("utf-8-sig")
    st.download_button(
        "CSV をダウンロード",
        data=csv_bytes,
        file_name=f"edinet_{edinet_code}_metrics.csv",
        mime="text/csv",
    )
