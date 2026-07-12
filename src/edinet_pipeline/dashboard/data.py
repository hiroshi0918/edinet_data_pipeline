"""データアクセス層 — DuckDB ファイルからの読み取り専用クエリ関数群.

このモジュールはダッシュボードからの read-only クエリだけを扱う。すべての関数は
`duckdb.DuckDBPyConnection` を引数で受け取り、`pandas.DataFrame` または
プリミティブ値を返す。動的に列名を埋め込む関数 (`query_company_comparison`、
`query_hc_distribution_by_industry`) は `_validate_metric` で許可リスト検証して
からクエリに組み立てるため、ユーザ入力経由の SQL インジェクションは発生しない。

`@st.cache_data(ttl=300)` が付いた関数は 5 分間結果をキャッシュする。
"""

from __future__ import annotations

import duckdb
import pandas as pd
import streamlit as st

from edinet_pipeline.dashboard.constants import (
    ALLOWED_ALL_METRICS,
    ALLOWED_FINANCIAL_METRICS,
    ALLOWED_HC_METRICS,
    DEFAULT_SCOPE,
    DEFAULT_WORKER_TYPE,
    IDEAL_CLUSTER_THRESHOLDS,
    TABLE_COMPANY_YEAR_METRICS,
)
from edinet_pipeline.models import (
    ALLOWED_SCOPES,
    ALLOWED_WORKER_TYPES,
    SCOPE_CONSOLIDATED_SUBSIDIARY,
    SCOPE_REPORTING_COMPANY,
)

_T = TABLE_COMPANY_YEAR_METRICS


@st.cache_resource
def get_connection(duckdb_path: str) -> duckdb.DuckDBPyConnection:
    """DuckDB ファイルへの読み取り専用接続を返す (Streamlit セッション間で再利用)."""
    return duckdb.connect(duckdb_path, read_only=True)


def _validate_metric(metric: str, allowed: set[str]) -> None:
    """metric が許可リストに含まれなければ ValueError を送出する.

    DuckDB では列名をパラメータバインドできないため、動的に列名を埋め込む
    クエリでは事前に許可リスト検証を行うことで SQL インジェクションを防いでいる。
    """
    if metric not in allowed:
        raise ValueError(f"Invalid metric: {metric}")


# ------------------------------------------------------------------ #
#  フィルター用ヘルパー
# ------------------------------------------------------------------ #


@st.cache_data(ttl=300)
def query_available_companies(_conn: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """フィルター用の企業一覧 (edinet_code, company_name) を返す."""
    return _conn.execute(
        f"""
        SELECT DISTINCT edinet_code, company_name
        FROM {_T}
        ORDER BY UPPER(company_name)
        """
    ).fetchdf()


@st.cache_data(ttl=300)
def query_available_fiscal_years(_conn: duckdb.DuckDBPyConnection) -> list[int]:
    """フィルター用の年度リストを昇順で返す."""
    df = _conn.execute(
        f"""
        SELECT DISTINCT fiscal_year
        FROM {_T}
        ORDER BY fiscal_year
        """
    ).fetchdf()
    return df["fiscal_year"].tolist()


@st.cache_data(ttl=300)
def query_busiest_fiscal_year(_conn: duckdb.DuckDBPyConnection) -> int | None:
    """企業数が最も多い年度を返す (年度フィルタの既定値用).

    最新年度は提出が出揃っていない部分年度になりがちで、初期表示が薄くなる。
    収録企業数が最大の年度を既定にすると、最初から濃い分布を見せられる。
    """
    df = _conn.execute(
        f"""
        SELECT fiscal_year, COUNT(DISTINCT edinet_code) AS n
          FROM {_T}
         WHERE scope = ? AND worker_type = ?
         GROUP BY fiscal_year
         ORDER BY n DESC, fiscal_year DESC
         LIMIT 1
        """,
        [DEFAULT_SCOPE, DEFAULT_WORKER_TYPE],
    ).fetchdf()
    return int(df["fiscal_year"].iloc[0]) if not df.empty else None


# ------------------------------------------------------------------ #
#  サマリー (データ範囲 KPI)
# ------------------------------------------------------------------ #


@st.cache_data(ttl=300)
def query_kpi_summary(_conn: duckdb.DuckDBPyConnection) -> dict:
    """KPI サマリー: 企業数、年度数、レコード数、最新提出日.

    ビューは scope/worker_type で複数行を返すため、デフォルト次元に絞って
    1書類=1行に正規化してから集計する。
    """
    row = _conn.execute(
        f"""
        SELECT
            COUNT(DISTINCT edinet_code) AS company_count,
            COUNT(DISTINCT fiscal_year) AS year_count,
            COUNT(*)                    AS total_records,
            MAX(submitted_date)         AS latest_submission
        FROM {_T}
        WHERE scope = ? AND worker_type = ?
        """,
        [DEFAULT_SCOPE, DEFAULT_WORKER_TYPE],
    ).fetchone()
    return {
        "company_count": row[0],
        "year_count": row[1],
        "total_records": row[2],
        "latest_submission": row[3],
    }




# ------------------------------------------------------------------ #
#  企業ランキング (指標で上位/下位を並べる)
# ------------------------------------------------------------------ #




def query_company_comparison(
    conn: duckdb.DuckDBPyConnection,
    metric: str,
    fiscal_year: int,
    top_n: int = 20,
    *,
    ascending: bool = False,
    industry_filter: tuple[str, ...] = (),
    scope: str = DEFAULT_SCOPE,
    worker_type: str = DEFAULT_WORKER_TYPE,
) -> pd.DataFrame:
    """指定年度・指定指標で企業をランキングする (業種絞り込みと scope/worker_type 対応).

    ascending=False で上位 (大きい順)、True で下位 (小さい順)。NULL は除外する。
    """
    _validate_metric(metric, ALLOWED_ALL_METRICS)
    order = "ASC" if ascending else "DESC"
    base_sql = f"""
        SELECT edinet_code, company_name, industry, {metric}
          FROM {_T}
         WHERE fiscal_year = ?
           AND {metric} IS NOT NULL
           AND scope = ? AND worker_type = ?
    """
    params: list[object] = [fiscal_year, scope, worker_type]
    if industry_filter:
        placeholders = ", ".join(["?"] * len(industry_filter))
        base_sql += f"   AND industry IN ({placeholders})\n"
        params.extend(industry_filter)
    base_sql += f" ORDER BY {metric} {order} LIMIT ?"
    params.append(top_n)
    return conn.execute(base_sql, params).fetchdf()






# ------------------------------------------------------------------ #
#  Company Spotlight: 単一企業の peer 比較・理想クラスタ算出
# ------------------------------------------------------------------ #


def _validate_scope_worker(scope: str, worker_type: str) -> None:
    if scope not in ALLOWED_SCOPES:
        raise ValueError(f"Invalid scope: {scope}")
    if worker_type not in ALLOWED_WORKER_TYPES:
        raise ValueError(f"Invalid worker_type: {worker_type}")


@st.cache_data(ttl=300)
def query_company_profile(
    _conn: duckdb.DuckDBPyConnection, edinet_code: str
) -> pd.DataFrame:
    """指定企業の全 (fiscal_year, scope, worker_type) 行を返す."""
    return _conn.execute(
        f"""
        SELECT fiscal_year, scope, worker_type, doc_id, submitted_date,
               sales, operating_profit, net_profit, employee_count,
               female_manager_ratio, male_childcare_leave_ratio, gender_wage_gap,
               average_annual_salary, average_years_of_service, average_age,
               industry, company_name
          FROM {_T}
         WHERE edinet_code = ?
         ORDER BY fiscal_year DESC, scope, worker_type
        """,
        [edinet_code],
    ).fetchdf()


@st.cache_data(ttl=300)
def detect_evaluation_scope(
    _conn: duckdb.DuckDBPyConnection, edinet_code: str, fiscal_year: int | None = None
) -> str:
    """提出会社の HC 指標がほぼ NULL なら 'consolidated_subsidiary' を返す.

    持株会社 (例: セプテーニ HD) は提出会社単体に従業員がほぼ無く HC が NULL に
    なるため、グループ全体を表す連結子会社 scope で評価するのが妥当。判定は最新
    年度（または指定年度）の reporting_company × all 行を見て、主要 2 指標
    (female_manager_ratio, male_childcare_leave_ratio) が両方 NULL なら持株会社
    と推定する。gender_wage_gap は役員報酬等で値が入ることがあるため判定対象から
    除外する。
    """
    where_year = "AND fiscal_year = ?" if fiscal_year is not None else ""
    params: list[object] = [edinet_code, DEFAULT_SCOPE, DEFAULT_WORKER_TYPE]
    if fiscal_year is not None:
        params.append(fiscal_year)
    df = _conn.execute(
        f"""
        SELECT female_manager_ratio, male_childcare_leave_ratio, gender_wage_gap
          FROM {_T}
         WHERE edinet_code = ?
           AND scope = ? AND worker_type = ?
           {where_year}
         ORDER BY fiscal_year DESC
         LIMIT 1
        """,
        params,
    ).fetchdf()
    if df.empty:
        return SCOPE_REPORTING_COMPANY
    row = df.iloc[0]
    # 持株会社は提出会社単体に従業員がほぼ無いため、女性管理職比率と男性育休
    # 取得率の主要 2 指標が両方 NULL なら持株会社と推定する。賃金格差だけは
    # 役員報酬等で値が入ることがあるため判定対象から除外する。
    if pd.isna(row["female_manager_ratio"]) and pd.isna(row["male_childcare_leave_ratio"]):
        return SCOPE_CONSOLIDATED_SUBSIDIARY
    return SCOPE_REPORTING_COMPANY


@st.cache_data(ttl=300)
def query_industry_peers(
    _conn: duckdb.DuckDBPyConnection,
    industry: str | None,
    fiscal_year: int,
    scope: str,
    worker_type: str,
) -> pd.DataFrame:
    """同業界 peer の HC 指標 + 財務情報を返す.

    industry が None や空文字なら空 DataFrame を返す。
    """
    _validate_scope_worker(scope, worker_type)
    if not industry:
        return pd.DataFrame()
    return _conn.execute(
        f"""
        SELECT edinet_code, company_name, industry, employee_count,
               sales, operating_profit, net_profit,
               female_manager_ratio, male_childcare_leave_ratio, gender_wage_gap
          FROM {_T}
         WHERE industry = ?
           AND fiscal_year = ?
           AND scope = ? AND worker_type = ?
        """,
        [industry, fiscal_year, scope, worker_type],
    ).fetchdf()


@st.cache_data(ttl=300)
def query_size_peers(
    _conn: duckdb.DuckDBPyConnection,
    employee_count_target: int,
    fiscal_year: int,
    scope: str,
    worker_type: str,
    log_dex: float = 0.3,
) -> pd.DataFrame:
    """対数スケール ±log_dex (デフォルト 0.3 dex ≒ 2 倍) の規模類似 peer.

    線形 ±50% だと小規模企業で peer 数が極端に減るため、log スケールで対称な
    幅を取る。employee_count_target=58 (ビジネスコーチ) なら 29-115 名程度が
    peer に含まれる。
    """
    _validate_scope_worker(scope, worker_type)
    if employee_count_target is None or employee_count_target <= 0:
        return pd.DataFrame()
    return _conn.execute(
        f"""
        SELECT edinet_code, company_name, industry, employee_count,
               sales, operating_profit, net_profit,
               female_manager_ratio, male_childcare_leave_ratio, gender_wage_gap
          FROM {_T}
         WHERE fiscal_year = ?
           AND scope = ? AND worker_type = ?
           AND employee_count IS NOT NULL
           AND employee_count > 0
           AND LOG10(CAST(employee_count AS DOUBLE))
               BETWEEN LOG10(CAST(? AS DOUBLE)) - ?
                   AND LOG10(CAST(? AS DOUBLE)) + ?
        """,
        [
            fiscal_year, scope, worker_type,
            employee_count_target, log_dex,
            employee_count_target, log_dex,
        ],
    ).fetchdf()


@st.cache_data(ttl=300)
def query_ideal_cluster(
    _conn: duckdb.DuckDBPyConnection,
    fiscal_year: int,
    scope: str,
    worker_type: str,
) -> pd.DataFrame:
    """3 HC 指標すべて P75 以上 + 営業利益率 P50 以上の「理想クラスタ」企業を返す.

    各指標の P75 / 営業利益率 P50 は同じ (fiscal_year, scope, worker_type) 集合
    から動的に算出する。male_childcare_leave_ratio は法令許容上 100% を超える
    値があるため、ここでは値を加工せず純粋な P75 で閾値を取る。
    """
    _validate_scope_worker(scope, worker_type)
    hc_pct = IDEAL_CLUSTER_THRESHOLDS["hc_percentile"] / 100
    op_pct = IDEAL_CLUSTER_THRESHOLDS["operating_margin_percentile"] / 100
    return _conn.execute(
        f"""
        WITH base AS (
            SELECT *,
                   CASE WHEN sales IS NOT NULL AND sales > 0
                        THEN CAST(operating_profit AS DOUBLE) / sales
                        ELSE NULL END AS op_margin
              FROM {_T}
             WHERE fiscal_year = ?
               AND scope = ? AND worker_type = ?
        ),
        thresholds AS (
            SELECT
                quantile_cont(female_manager_ratio, ?) AS f_thr,
                quantile_cont(male_childcare_leave_ratio, ?) AS m_thr,
                quantile_cont(gender_wage_gap, ?) AS g_thr,
                quantile_cont(op_margin, ?) AS op_thr
              FROM base
        )
        SELECT b.edinet_code, b.company_name, b.industry, b.employee_count,
               b.sales, b.operating_profit, b.op_margin,
               b.female_manager_ratio, b.male_childcare_leave_ratio, b.gender_wage_gap
          FROM base b, thresholds t
         WHERE b.female_manager_ratio        >= t.f_thr
           AND b.male_childcare_leave_ratio  >= t.m_thr
           AND b.gender_wage_gap             >= t.g_thr
           AND b.op_margin                   >= t.op_thr
         ORDER BY b.op_margin DESC NULLS LAST
        """,
        [fiscal_year, scope, worker_type, hc_pct, hc_pct, hc_pct, op_pct],
    ).fetchdf()


@st.cache_data(ttl=300)
def search_company_by_name(
    _conn: duckdb.DuckDBPyConnection, query: str, limit: int = 50
) -> pd.DataFrame:
    """企業名の部分一致検索 (Streamlit セレクタ用)."""
    if not query:
        return pd.DataFrame()
    pattern = f"%{query}%"
    return _conn.execute(
        f"""
        SELECT DISTINCT edinet_code, company_name, industry
          FROM {_T}
         WHERE company_name ILIKE ?
         ORDER BY UPPER(company_name)
         LIMIT ?
        """,
        [pattern, limit],
    ).fetchdf()


# ------------------------------------------------------------------ #
#  Company Spotlight: 業種内ランク算出
# ------------------------------------------------------------------ #










# 百分率系メトリクス（0〜100% に常識的範囲を制限すべきもの）
# 男性育休取得率は EDINET 原本に 200% 等の極端値が含まれるため、改善率ランキングでは除外する。
_HC_PERCENT_METRICS: set[str] = {
    "female_manager_ratio",
    "male_childcare_leave_ratio",
    "gender_wage_gap",
}




















@st.cache_data(ttl=300)
def query_company_industry_rank(
    _conn: duckdb.DuckDBPyConnection,
    edinet_code: str,
    fiscal_year: int,
    scope: str = DEFAULT_SCOPE,
    worker_type: str = DEFAULT_WORKER_TYPE,
) -> dict:
    """選択企業の業種内ランクを返す（売上・営業利益・女性管理職比率）.

    SQL でランクを直接計算するより、業種の peer をすべて取得して pandas 側で
    順位付けする方がコードが読みやすく、NULL 処理も柔軟。peer 数は通常数百件
    程度なので性能も問題ない。
    """
    target_row = _conn.execute(
        f"""
        SELECT industry, sales, operating_profit, female_manager_ratio
          FROM {_T}
         WHERE edinet_code = ?
           AND fiscal_year = ?
           AND scope = ? AND worker_type = ?
         LIMIT 1
        """,
        [edinet_code, fiscal_year, scope, worker_type],
    ).fetchone()
    if not target_row:
        return {}
    industry, target_sales, target_op, target_fmr = target_row
    if not industry:
        return {"industry": None}

    peers_df = _conn.execute(
        f"""
        SELECT edinet_code, sales, operating_profit, female_manager_ratio
          FROM {_T}
         WHERE industry = ?
           AND fiscal_year = ?
           AND scope = ? AND worker_type = ?
        """,
        [industry, fiscal_year, scope, worker_type],
    ).fetchdf()

    def _rank(col: str, target_val: float | None) -> int | None:
        if target_val is None or pd.isna(target_val):
            return None
        valid = peers_df[peers_df[col].notna()][col]
        if len(valid) == 0:
            return None
        return int((valid > target_val).sum()) + 1

    return {
        "industry": industry,
        "industry_total": len(peers_df),
        "industry_with_sales": int(peers_df["sales"].notna().sum()),
        "industry_with_fmr": int(peers_df["female_manager_ratio"].notna().sum()),
        "sales_rank": _rank("sales", target_sales),
        "operating_profit_rank": _rank("operating_profit", target_op),
        "female_manager_ratio_rank": _rank("female_manager_ratio", target_fmr),
    }


# ====================================================================== #
#  v0.5 改修: 5 ページ再編 (業種別箱ひげ図 / 規模×人的資本ランキング)
# ====================================================================== #


@st.cache_data(ttl=300)
def query_hc_distribution_by_industry(
    _conn: duckdb.DuckDBPyConnection,
    metric: str,
    fiscal_year: int,
    scope: str = DEFAULT_SCOPE,
    worker_type: str = DEFAULT_WORKER_TYPE,
    min_companies: int = 5,
) -> pd.DataFrame:
    """業種別箱ひげ図用に、指定 HC 指標の企業別生値 + industry を返す.

    集約せず企業ごとの値を残したまま、開示 min_companies 社未満の業種だけ
    QUALIFY で除外する。男性育休取得率の >100% も加工せず返す (箱の外の点として
    自然に可視化されるため)。
    """
    _validate_metric(metric, ALLOWED_HC_METRICS)
    return _conn.execute(
        f"""
        SELECT industry, edinet_code, company_name, {metric} AS value
          FROM {_T}
         WHERE fiscal_year = ?
           AND scope = ? AND worker_type = ?
           AND {metric} IS NOT NULL
           AND industry IS NOT NULL
        QUALIFY COUNT(*) OVER (PARTITION BY industry) >= ?
        """,
        [fiscal_year, scope, worker_type, min_companies],
    ).fetchdf()


@st.cache_data(ttl=300)
def query_financial_ranking_with_hc(
    _conn: duckdb.DuckDBPyConnection,
    metric: str,
    fiscal_year: int,
    top_n: int = 10,
    *,
    ascending: bool = False,
    min_value: float | None = None,
    scope: str = DEFAULT_SCOPE,
    worker_type: str = DEFAULT_WORKER_TYPE,
) -> pd.DataFrame:
    """財務指標で上位/下位 N 社を返し、女性管理職比率・男女賃金格差を併記する.

    ascending=False で上位 (大きい順)、True で下位 (小さい順)。min_value は下位
    ランキングでアーティファクト (売上=1) や空殻会社 (従業員 0) を除くための下限。
    男性育休取得率はノイズが大きいため併記列に含めない (RANKING_HC_METRICS と整合)。
    """
    _validate_metric(metric, ALLOWED_FINANCIAL_METRICS)
    order = "ASC" if ascending else "DESC"
    base_sql = f"""
        SELECT edinet_code, company_name, industry, {metric} AS value,
               female_manager_ratio, gender_wage_gap
          FROM {_T}
         WHERE fiscal_year = ?
           AND scope = ? AND worker_type = ?
           AND {metric} IS NOT NULL
    """
    params: list[object] = [fiscal_year, scope, worker_type]
    if min_value is not None:
        base_sql += f"   AND {metric} >= ?\n"
        params.append(min_value)
    base_sql += f" ORDER BY {metric} {order} NULLS LAST LIMIT ?"
    params.append(top_n)
    return _conn.execute(base_sql, params).fetchdf()
