"""共通サイドバーフィルター — 各ページから再利用する Streamlit ウィジェット."""

from __future__ import annotations

import duckdb
import streamlit as st

from edinet_pipeline.dashboard.constants import (
    DEFAULT_PRESET,
    DEFAULT_SCOPE,
    DEFAULT_WORKER_TYPE,
    PRESET_LABELS,
    SCOPE_LABELS,
    WORKER_TYPE_LABELS,
)
from edinet_pipeline.dashboard.data import (
    query_available_companies,
    query_available_fiscal_years,
    query_available_industries,
    query_companies_by_preset,
)


def render_fiscal_year_filter(
    conn: duckdb.DuckDBPyConnection,
    key_prefix: str = "",
) -> tuple[int, int]:
    """年度範囲スライダーを描画し (min, max) を返す."""
    years = query_available_fiscal_years(conn)
    if not years:
        st.sidebar.warning("データがありません")
        return 0, 0
    if len(years) == 1:
        st.sidebar.info(f"年度: {years[0]}")
        return years[0], years[0]
    year_range = st.sidebar.slider(
        "年度範囲",
        min_value=min(years),
        max_value=max(years),
        value=(min(years), max(years)),
        key=f"{key_prefix}_fiscal_year",
    )
    return year_range[0], year_range[1]


def render_dimension_filter(
    key_prefix: str = "",
    *,
    scope_default: str = DEFAULT_SCOPE,
    worker_type_default: str = DEFAULT_WORKER_TYPE,
) -> tuple[str, str]:
    """サイドバーに次元 (scope/worker_type) のセレクタを描画し、選択値を返す.

    人的資本指標が次元別にスキーマ化されたことに伴い、ダッシュボード全体で
    同じ次元を切り替えられるよう共通化する。
    """
    st.sidebar.markdown("**人的資本の開示範囲**")
    scope = st.sidebar.selectbox(
        "対象範囲",
        options=list(SCOPE_LABELS.keys()),
        index=list(SCOPE_LABELS.keys()).index(scope_default),
        format_func=lambda code: SCOPE_LABELS[code],
        key=f"{key_prefix}_scope",
    )
    worker_type = st.sidebar.selectbox(
        "労働者区分",
        options=list(WORKER_TYPE_LABELS.keys()),
        index=list(WORKER_TYPE_LABELS.keys()).index(worker_type_default),
        format_func=lambda code: WORKER_TYPE_LABELS[code],
        key=f"{key_prefix}_worker_type",
    )
    return scope, worker_type


def render_industry_filter(
    conn: duckdb.DuckDBPyConnection,
    key_prefix: str = "",
) -> tuple[str, ...]:
    """業種マルチセレクトをサイドバーに描画し、選択された業種を tuple で返す.

    全ページ共通のサイドバー要素。返り値が tuple なのは、各 query 関数が
    @st.cache_data で hashable な引数を求めるため。空 tuple は「全業種」を意味する。
    """
    industries = query_available_industries(conn)
    if not industries:
        return ()
    selected = st.sidebar.multiselect(
        "業種で絞り込む（未選択 = 全業種）",
        options=industries,
        default=[],
        key=f"{key_prefix}_industry",
        help="複数選択可。未選択の場合は全業種を対象にします。",
    )
    return tuple(selected)


def render_company_filter(
    conn: duckdb.DuckDBPyConnection,
    fiscal_year: int,
    key_prefix: str = "",
    *,
    industry_filter: tuple[str, ...] = (),
    show_preset: bool = True,
) -> list[str]:
    """プリセット選択と企業マルチセレクトを描画し、選択された edinet_code を返す.

    プリセットが "custom" 以外のときは自動でプリセット由来の企業が選ばれる。
    "custom" のときだけ multiselect の手動選択が反映される。
    industry_filter が渡されたら multiselect の候補もその業種に絞る。
    """
    df = query_available_companies(conn)
    if df.empty:
        st.sidebar.warning("企業データがありません")
        return []
    options = dict(zip(df["edinet_code"], df["company_name"], strict=True))

    if industry_filter:
        # 業種フィルタが指定された場合、候補をその業種の企業に絞る
        df_filtered = conn.execute(
            f"""
            SELECT DISTINCT edinet_code, company_name
              FROM {_get_table_name()}
             WHERE industry IN ({", ".join(["?"] * len(industry_filter))})
            """,
            list(industry_filter),
        ).fetchdf()
        allowed = set(df_filtered["edinet_code"].tolist())
        options = {k: v for k, v in options.items() if k in allowed}

    preset = DEFAULT_PRESET
    if show_preset:
        preset = st.sidebar.radio(
            "プリセット",
            options=list(PRESET_LABELS.keys()),
            format_func=lambda p: PRESET_LABELS[p],
            index=list(PRESET_LABELS.keys()).index(DEFAULT_PRESET),
            key=f"{key_prefix}_preset",
            help=(
                "プリセットを選ぶと自動で企業が選択されます。"
                "「カスタム」を選ぶと下のマルチセレクトで自由に選べます。"
            ),
        )

    if preset != "custom":
        preset_codes = query_companies_by_preset(
            conn, preset, fiscal_year, top_n=10
        )
        # プリセット由来コードのうち、業種フィルタ後の候補に存在するものだけ採用
        default_codes = [c for c in preset_codes if c in options]
        if not default_codes:
            default_codes = list(options.keys())[:5]
        # custom 以外のときは multiselect を表示せず読み取り専用に
        st.sidebar.caption(
            f"プリセット選択中: **{PRESET_LABELS[preset]}**（{len(default_codes)}社）"
        )
        return default_codes

    # custom: マルチセレクトで自由選択
    selected = st.sidebar.multiselect(
        "企業を選択（カスタム）",
        options=list(options.keys()),
        default=list(options.keys())[:5],
        format_func=lambda code: f"{options[code]} ({code})",
        key=f"{key_prefix}_company",
    )
    return selected


def _get_table_name() -> str:
    """循環 import を避けるための遅延参照ヘルパー."""
    from edinet_pipeline.dashboard.constants import TABLE_COMPANY_YEAR_METRICS
    return TABLE_COMPANY_YEAR_METRICS
