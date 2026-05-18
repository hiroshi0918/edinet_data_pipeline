"""データアクセス層 — DuckDB ファイルからの読み取り専用クエリ関数群.

このモジュールはダッシュボードからの read-only クエリだけを扱う。すべての関数は
`duckdb.DuckDBPyConnection` を引数で受け取り、`pandas.DataFrame` または
プリミティブ値を返す。動的に列名を埋め込む関数 (`query_company_comparison`、
`query_hc_distribution`) は `_validate_metric` で許可リスト検証してからクエリに
組み立てるため、ユーザ入力経由の SQL インジェクションは発生しない。

`@st.cache_data(ttl=300)` が付いた関数は 5 分間結果をキャッシュする。フィルタが
頻繁に変わらないページ (overview / data_quality) のクエリで使う。
"""

from __future__ import annotations

import duckdb
import pandas as pd
import streamlit as st

from edinet_pipeline.dashboard.constants import (
    ALLOWED_ALL_METRICS,
    ALLOWED_HC_METRICS,
    DEFAULT_SCOPE,
    DEFAULT_WORKER_TYPE,
    IDEAL_CLUSTER_THRESHOLDS,
    TABLE_COMPANY_YEAR_METRICS,
    TABLE_METRIC_EVIDENCE,
    sales_tier_case_sql,
)
from edinet_pipeline.models import (
    ALLOWED_SCOPES,
    ALLOWED_WORKER_TYPES,
    SCOPE_CONSOLIDATED_SUBSIDIARY,
    SCOPE_REPORTING_COMPANY,
)

_T = TABLE_COMPANY_YEAR_METRICS
_E = TABLE_METRIC_EVIDENCE


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


# ------------------------------------------------------------------ #
#  概要 (Overview)
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


@st.cache_data(ttl=300)
def query_status_distribution(_conn: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """fiscal_year x status の件数分布 (デフォルト次元行で 1書類=1行に正規化)."""
    return _conn.execute(
        f"""
        SELECT fiscal_year, status, COUNT(*) AS doc_count
        FROM {_T}
        WHERE scope = ? AND worker_type = ?
        GROUP BY fiscal_year, status
        ORDER BY fiscal_year, status
        """,
        [DEFAULT_SCOPE, DEFAULT_WORKER_TYPE],
    ).fetchdf()


# ------------------------------------------------------------------ #
#  財務指標 (Financial)
# ------------------------------------------------------------------ #


def query_financial_trends(
    conn: duckdb.DuckDBPyConnection,
    edinet_codes: list[str],
    year_min: int,
    year_max: int,
) -> pd.DataFrame:
    """選択企業の財務指標推移を返す (人的資本の次元増殖を排除するためデフォルト次元で絞る)."""
    if not edinet_codes:
        return pd.DataFrame()
    placeholders = ", ".join(["?"] * len(edinet_codes))
    return conn.execute(
        f"""
        SELECT edinet_code, company_name, fiscal_year,
               sales, operating_profit, net_profit, employee_count
        FROM {_T}
        WHERE edinet_code IN ({placeholders})
          AND fiscal_year BETWEEN ? AND ?
          AND scope = ? AND worker_type = ?
        ORDER BY fiscal_year, UPPER(company_name)
        """,
        [*edinet_codes, year_min, year_max, DEFAULT_SCOPE, DEFAULT_WORKER_TYPE],
    ).fetchdf()


def query_company_comparison(
    conn: duckdb.DuckDBPyConnection,
    metric: str,
    fiscal_year: int,
    top_n: int = 20,
    *,
    industry_filter: tuple[str, ...] = (),
    scope: str = DEFAULT_SCOPE,
    worker_type: str = DEFAULT_WORKER_TYPE,
) -> pd.DataFrame:
    """指定年度・指定指標で企業をランキングする (業種絞り込みと scope/worker_type 対応)."""
    _validate_metric(metric, ALLOWED_ALL_METRICS)
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
    base_sql += f" ORDER BY {metric} DESC LIMIT ?"
    params.append(top_n)
    return conn.execute(base_sql, params).fetchdf()


@st.cache_data(ttl=300)
def query_metric_overall_median(
    _conn: duckdb.DuckDBPyConnection,
    metric: str,
    fiscal_year: int,
    industry_filter: tuple[str, ...] = (),
    scope: str = DEFAULT_SCOPE,
    worker_type: str = DEFAULT_WORKER_TYPE,
) -> float | None:
    """指定指標の全体中央値（業種フィルタ反映）を返す.

    財務指標ページのランキングで「業種中央値ライン」を重ねるために使う。
    フィルタが空なら全体中央値、業種フィルタが指定されればその業種範囲の中央値。
    """
    _validate_metric(metric, ALLOWED_ALL_METRICS)
    base_sql = f"""
        SELECT MEDIAN({metric}) AS median_value
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
    row = _conn.execute(base_sql, params).fetchone()
    return float(row[0]) if row and row[0] is not None else None


@st.cache_data(ttl=300)
def query_financial_summary_stats(
    _conn: duckdb.DuckDBPyConnection,
    year_min: int,
    year_max: int,
) -> pd.DataFrame:
    """年度別の財務指標集計統計 (デフォルト次元で 1書類=1行に正規化してから集計)."""
    return _conn.execute(
        f"""
        SELECT fiscal_year,
               COUNT(*)                 AS count,
               AVG(sales)               AS avg_sales,
               MEDIAN(sales)            AS med_sales,
               MIN(sales)               AS min_sales,
               MAX(sales)               AS max_sales,
               AVG(operating_profit)    AS avg_operating_profit,
               MEDIAN(operating_profit) AS med_operating_profit,
               AVG(net_profit)          AS avg_net_profit,
               MEDIAN(net_profit)       AS med_net_profit,
               AVG(employee_count)      AS avg_employee_count,
               MEDIAN(employee_count)   AS med_employee_count
        FROM {_T}
        WHERE fiscal_year BETWEEN ? AND ?
          AND scope = ? AND worker_type = ?
        GROUP BY fiscal_year
        ORDER BY fiscal_year
        """,
        [year_min, year_max, DEFAULT_SCOPE, DEFAULT_WORKER_TYPE],
    ).fetchdf()


# ------------------------------------------------------------------ #
#  人的資本指標 (Human Capital)
# ------------------------------------------------------------------ #


def query_hc_distribution(
    conn: duckdb.DuckDBPyConnection,
    metric: str,
    fiscal_year: int,
    *,
    scope: str = DEFAULT_SCOPE,
    worker_type: str = DEFAULT_WORKER_TYPE,
) -> pd.DataFrame:
    """指定年度・指定次元の HC 指標分布データ (NULL 除外)."""
    _validate_metric(metric, ALLOWED_HC_METRICS)
    return conn.execute(
        f"""
        SELECT edinet_code, company_name, {metric}
        FROM {_T}
        WHERE fiscal_year = ? AND {metric} IS NOT NULL
          AND scope = ? AND worker_type = ?
        """,
        [fiscal_year, scope, worker_type],
    ).fetchdf()


@st.cache_data(ttl=300)
def query_hc_trends(
    _conn: duckdb.DuckDBPyConnection,
    year_min: int,
    year_max: int,
    scope: str = DEFAULT_SCOPE,
    worker_type: str = DEFAULT_WORKER_TYPE,
) -> pd.DataFrame:
    """HC 指標の年度別平均推移 (次元別)."""
    return _conn.execute(
        f"""
        SELECT fiscal_year,
               AVG(female_manager_ratio)         AS avg_female_manager_ratio,
               AVG(male_childcare_leave_ratio)   AS avg_male_childcare_leave_ratio,
               AVG(gender_wage_gap)              AS avg_gender_wage_gap,
               COUNT(female_manager_ratio)       AS n_female_manager,
               COUNT(male_childcare_leave_ratio) AS n_male_childcare_leave,
               COUNT(gender_wage_gap)            AS n_gender_wage_gap
        FROM {_T}
        WHERE fiscal_year BETWEEN ? AND ?
          AND scope = ? AND worker_type = ?
        GROUP BY fiscal_year
        ORDER BY fiscal_year
        """,
        [year_min, year_max, scope, worker_type],
    ).fetchdf()


def query_hc_scatter(
    conn: duckdb.DuckDBPyConnection,
    fiscal_year: int,
    *,
    scope: str = DEFAULT_SCOPE,
    worker_type: str = DEFAULT_WORKER_TYPE,
) -> pd.DataFrame:
    """女性管理職比率 vs 男性育休取得率の散布図データ (次元別)."""
    return conn.execute(
        f"""
        SELECT company_name, female_manager_ratio,
               male_childcare_leave_ratio, employee_count
        FROM {_T}
        WHERE fiscal_year = ?
          AND female_manager_ratio IS NOT NULL
          AND male_childcare_leave_ratio IS NOT NULL
          AND scope = ? AND worker_type = ?
        """,
        [fiscal_year, scope, worker_type],
    ).fetchdf()


# ------------------------------------------------------------------ #
#  データ品質 (Data Quality)
# ------------------------------------------------------------------ #


@st.cache_data(ttl=300)
def query_coverage_matrix(
    _conn: duckdb.DuckDBPyConnection,
    fiscal_year: int,
    scope: str = DEFAULT_SCOPE,
    worker_type: str = DEFAULT_WORKER_TYPE,
) -> pd.DataFrame:
    """指標x企業のカバレッジマトリクス (1=有, 0=欠損)."""
    return _conn.execute(
        f"SELECT edinet_code, company_name, "
        f"  CASE WHEN sales IS NOT NULL THEN 1 ELSE 0 END AS sales, "
        f"  CASE WHEN operating_profit IS NOT NULL THEN 1 ELSE 0 END AS operating_profit, "
        f"  CASE WHEN net_profit IS NOT NULL THEN 1 ELSE 0 END AS net_profit, "
        f"  CASE WHEN employee_count IS NOT NULL THEN 1 ELSE 0 END AS employee_count, "
        f"  CASE WHEN female_manager_ratio IS NOT NULL THEN 1 ELSE 0 END "
        f"    AS female_manager_ratio, "
        f"  CASE WHEN male_childcare_leave_ratio IS NOT NULL THEN 1 ELSE 0 END "
        f"    AS male_childcare_leave_ratio, "
        f"  CASE WHEN gender_wage_gap IS NOT NULL THEN 1 ELSE 0 END AS gender_wage_gap "
        f"FROM {_T} "
        f"WHERE fiscal_year = ? AND scope = ? AND worker_type = ? "
        f"ORDER BY UPPER(company_name)",
        [fiscal_year, scope, worker_type],
    ).fetchdf()


@st.cache_data(ttl=300)
def query_completeness_over_time(
    _conn: duckdb.DuckDBPyConnection,
    scope: str = DEFAULT_SCOPE,
    worker_type: str = DEFAULT_WORKER_TYPE,
) -> pd.DataFrame:
    """年度別の各指標非 NULL 企業割合 (%) (次元で絞る)."""
    return _conn.execute(
        f"SELECT fiscal_year, "
        f"  COUNT(sales) * 100.0 / COUNT(*) AS sales_pct, "
        f"  COUNT(operating_profit) * 100.0 / COUNT(*) AS operating_profit_pct, "
        f"  COUNT(net_profit) * 100.0 / COUNT(*) AS net_profit_pct, "
        f"  COUNT(employee_count) * 100.0 / COUNT(*) AS employee_count_pct, "
        f"  COUNT(female_manager_ratio) * 100.0 / COUNT(*) AS female_manager_ratio_pct, "
        f"  COUNT(male_childcare_leave_ratio) * 100.0 / COUNT(*) "
        f"    AS male_childcare_leave_ratio_pct, "
        f"  COUNT(gender_wage_gap) * 100.0 / COUNT(*) AS gender_wage_gap_pct "
        f"FROM {_T} "
        f"WHERE scope = ? AND worker_type = ? "
        f"GROUP BY fiscal_year "
        f"ORDER BY fiscal_year",
        [scope, worker_type],
    ).fetchdf()


@st.cache_data(ttl=300)
def query_evidence_summary(_conn: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """metric_name x matched_by ごとの抽出根拠件数."""
    return _conn.execute(
        f"""
        SELECT metric_name, matched_by, COUNT(*) AS evidence_count
        FROM {_E}
        GROUP BY metric_name, matched_by
        ORDER BY metric_name, evidence_count DESC
        """
    ).fetchdf()


# ------------------------------------------------------------------ #
#  男性育休取得率の外れ値・参考値の集計
#  EDINET 正本が 100% 超や 0% を含むため、DB に保存された値は忠実なまま、
#  ダッシュボード側でユーザに気づかせるための専用クエリを切り出している。
# ------------------------------------------------------------------ #


@st.cache_data(ttl=300)
def query_male_childcare_outliers(_conn: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """男性育休取得率が 100% を超える書類を一覧で返す."""
    return _conn.execute(
        f"""
        SELECT company_name, edinet_code, fiscal_year, scope, worker_type,
               male_childcare_leave_ratio, doc_id, submitted_date, source_name
        FROM {_T}
        WHERE male_childcare_leave_ratio > 100
        ORDER BY male_childcare_leave_ratio DESC, UPPER(company_name)
        """
    ).fetchdf()


@st.cache_data(ttl=300)
def query_male_childcare_zero_summary(_conn: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """男性育休取得率が 0% の書類を年度別にカウントする."""
    return _conn.execute(
        f"""
        SELECT fiscal_year,
               COUNT(*) AS zero_count,
               COUNT(*) FILTER (WHERE scope = ? AND worker_type = ?) AS zero_reporting_all
        FROM {_T}
        WHERE male_childcare_leave_ratio = 0
        GROUP BY fiscal_year
        ORDER BY fiscal_year
        """,
        [DEFAULT_SCOPE, DEFAULT_WORKER_TYPE],
    ).fetchdf()


@st.cache_data(ttl=300)
def query_male_childcare_aggregation_anomalies(
    _conn: duckdb.DuckDBPyConnection,
) -> pd.DataFrame:
    """男性育休取得率で「複数観測値があり最大値が中央値と乖離している書類」を返す.

    XBRL の同一 element_id に対して contextRef 違いの複数値（連結子会社が
    複数並列）が記録されている場合、extractor は中央値で集約する。中央値と
    最大値が大きく乖離していれば「子会社のうち 1 社だけ外れ値（200% 等）」が
    含まれていた可能性が高く、原本確認の手がかりになる。
    """
    return _conn.execute(
        f"""
        WITH ratios AS (
            SELECT doc_id, company_name, fiscal_year, scope, worker_type,
                   TRY_CAST(raw_value AS DOUBLE) AS r
              FROM {_E}
             WHERE metric_name = 'male_childcare_leave_ratio'
               AND matched_by = 'element_id_match'
               AND TRY_CAST(raw_value AS DOUBLE) IS NOT NULL
        )
        SELECT doc_id, company_name, fiscal_year, scope, worker_type,
               COUNT(*) AS observation_count,
               ROUND(MIN(r) * 100, 2) AS min_pct,
               ROUND(MEDIAN(r) * 100, 2) AS median_pct,
               ROUND(MAX(r) * 100, 2) AS max_pct,
               ROUND((MAX(r) - MEDIAN(r)) * 100, 2) AS max_minus_median_pct
          FROM ratios
         GROUP BY doc_id, company_name, fiscal_year, scope, worker_type
        HAVING COUNT(*) >= 2 AND (MAX(r) - MEDIAN(r)) >= 0.5
         ORDER BY (MAX(r) - MEDIAN(r)) DESC, UPPER(company_name)
        """
    ).fetchdf()


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


# ====================================================================== #
#  v0.4 改修: ダッシュボードを「データを並べる」から「発見を提示する」へ
#  概要ハイライト、業種・規模比較、改善率、充足率診断、プリセット選択
# ====================================================================== #


@st.cache_data(ttl=300)
def query_available_industries(_conn: duckdb.DuckDBPyConnection) -> list[str]:
    """業種一覧を企業数の多い順で返す（フィルタ用）.

    NULL を除外し、デフォルト次元 (reporting_company, all) に絞ることで業種を
    重複なくカウントする。企業数が多い業種ほど選択候補として上位に並ぶ。
    """
    df = _conn.execute(
        f"""
        SELECT industry, COUNT(DISTINCT edinet_code) AS n
          FROM {_T}
         WHERE industry IS NOT NULL
           AND scope = ? AND worker_type = ?
         GROUP BY industry
         ORDER BY n DESC, industry
        """,
        [DEFAULT_SCOPE, DEFAULT_WORKER_TYPE],
    ).fetchdf()
    return df["industry"].tolist()


@st.cache_data(ttl=300)
def query_overview_highlights(_conn: duckdb.DuckDBPyConnection) -> dict:
    """概要ページの「データストーリー」3カード用集計を一括取得する.

    3 つの観点でデータの強い特徴を引き出す:
      1. 業種格差: 最新年度の女性管理職比率の業種別中央値（最高 vs 最低）
      2. 急速な改善: 男性育休取得率の年度推移（前年比の改善幅）
      3. 規模パラドックス: 売上階層別の女性管理職比率の中央値（規模↑で値↓）
    """
    industry_gap = _conn.execute(
        f"""
        SELECT industry,
               MEDIAN(female_manager_ratio) AS median_value,
               COUNT(*) AS n
          FROM {_T}
         WHERE fiscal_year = (SELECT MAX(fiscal_year) FROM {_T})
           AND scope = ? AND worker_type = ?
           AND female_manager_ratio IS NOT NULL
           AND industry IS NOT NULL
         GROUP BY industry
        HAVING COUNT(*) >= 5
         ORDER BY median_value DESC
        """,
        [DEFAULT_SCOPE, DEFAULT_WORKER_TYPE],
    ).fetchdf()

    improvement = _conn.execute(
        f"""
        SELECT fiscal_year,
               MEDIAN(male_childcare_leave_ratio) AS median_value,
               AVG(male_childcare_leave_ratio)    AS avg_value,
               COUNT(male_childcare_leave_ratio)  AS n
          FROM {_T}
         WHERE scope = ? AND worker_type = ?
           AND male_childcare_leave_ratio IS NOT NULL
           AND male_childcare_leave_ratio <= 100
         GROUP BY fiscal_year
         ORDER BY fiscal_year
        """,
        [DEFAULT_SCOPE, DEFAULT_WORKER_TYPE],
    ).fetchdf()

    size_paradox = _conn.execute(
        f"""
        SELECT {sales_tier_case_sql('sales')} AS tier,
               MEDIAN(female_manager_ratio) AS median_value,
               AVG(female_manager_ratio) AS avg_value,
               COUNT(*) AS n
          FROM {_T}
         WHERE fiscal_year = (SELECT MAX(fiscal_year) FROM {_T})
           AND scope = ? AND worker_type = ?
           AND female_manager_ratio IS NOT NULL
           AND sales IS NOT NULL
         GROUP BY tier
        """,
        [DEFAULT_SCOPE, DEFAULT_WORKER_TYPE],
    ).fetchdf()

    return {
        "industry_gap": industry_gap,
        "improvement": improvement,
        "size_paradox": size_paradox,
    }


@st.cache_data(ttl=300)
def query_industry_metric_summary(
    _conn: duckdb.DuckDBPyConnection,
    metric: str,
    fiscal_year: int,
    scope: str = DEFAULT_SCOPE,
    worker_type: str = DEFAULT_WORKER_TYPE,
    min_companies: int = 3,
) -> pd.DataFrame:
    """業種×指標の中央値・平均・件数を返す.

    指標名は動的に列名として埋め込むため許可リスト検証を行う。min_companies で
    集計対象とする業種の最小企業数を指定（少なすぎる業種を除外して安定化）。
    """
    _validate_metric(metric, ALLOWED_ALL_METRICS)
    return _conn.execute(
        f"""
        SELECT industry,
               MEDIAN({metric}) AS median_value,
               AVG({metric}) AS avg_value,
               COUNT(*) AS n
          FROM {_T}
         WHERE fiscal_year = ?
           AND scope = ? AND worker_type = ?
           AND {metric} IS NOT NULL
           AND industry IS NOT NULL
         GROUP BY industry
        HAVING COUNT(*) >= ?
         ORDER BY median_value DESC NULLS LAST
        """,
        [fiscal_year, scope, worker_type, min_companies],
    ).fetchdf()


@st.cache_data(ttl=300)
def query_size_tier_metric_summary(
    _conn: duckdb.DuckDBPyConnection,
    metric: str,
    fiscal_year: int,
    scope: str = DEFAULT_SCOPE,
    worker_type: str = DEFAULT_WORKER_TYPE,
) -> pd.DataFrame:
    """売上階層×指標の中央値・平均・件数を返す（規模パラドックス可視化用）."""
    _validate_metric(metric, ALLOWED_ALL_METRICS)
    return _conn.execute(
        f"""
        SELECT {sales_tier_case_sql('sales')} AS tier,
               MEDIAN({metric}) AS median_value,
               AVG({metric}) AS avg_value,
               COUNT(*) AS n
          FROM {_T}
         WHERE fiscal_year = ?
           AND scope = ? AND worker_type = ?
           AND {metric} IS NOT NULL
           AND sales IS NOT NULL
         GROUP BY tier
        """,
        [fiscal_year, scope, worker_type],
    ).fetchdf()


# 百分率系メトリクス（0〜100% に常識的範囲を制限すべきもの）
# 男性育休取得率は EDINET 原本に 200% 等の極端値が含まれるため、改善率ランキングでは除外する。
_HC_PERCENT_METRICS: set[str] = {
    "female_manager_ratio",
    "male_childcare_leave_ratio",
    "gender_wage_gap",
}


@st.cache_data(ttl=300)
def query_improvement_rate_ranking(
    _conn: duckdb.DuckDBPyConnection,
    metric: str,
    year_to: int,
    top_n: int = 10,
    scope: str = DEFAULT_SCOPE,
    worker_type: str = DEFAULT_WORKER_TYPE,
) -> pd.DataFrame:
    """前年比で最も改善した企業 TOP N を返す（差分 delta = year_to - year_to-1）.

    改善 = 値が上昇した方向。男女賃金格差のように「下がってほしい」指標もあるが
    ダッシュボード側で表現を反転する想定。ここでは純粋な delta で返す。

    HC 百分率系指標は 100% 超を含めるとランキングが外れ値レースになるため、
    SQL レベルで 0〜100% の範囲に絞り込む。財務指標は範囲が広いためフィルタしない。
    """
    _validate_metric(metric, ALLOWED_ALL_METRICS)
    extra_filter = ""
    if metric in _HC_PERCENT_METRICS:
        extra_filter = f"           AND {metric} BETWEEN 0 AND 100\n"
    return _conn.execute(
        f"""
        WITH curr AS (
            SELECT edinet_code, company_name, industry, {metric} AS value_to
              FROM {_T}
             WHERE fiscal_year = ?
               AND scope = ? AND worker_type = ?
               AND {metric} IS NOT NULL
{extra_filter}        ),
        prev AS (
            SELECT edinet_code, {metric} AS value_from
              FROM {_T}
             WHERE fiscal_year = ? - 1
               AND scope = ? AND worker_type = ?
               AND {metric} IS NOT NULL
{extra_filter}        )
        SELECT c.edinet_code, c.company_name, c.industry,
               p.value_from, c.value_to,
               (c.value_to - p.value_from) AS delta
          FROM curr c
          JOIN prev p USING (edinet_code)
         ORDER BY delta DESC NULLS LAST
         LIMIT ?
        """,
        [year_to, scope, worker_type, year_to, scope, worker_type, top_n],
    ).fetchdf()


@st.cache_data(ttl=300)
def query_overall_completeness_kpi(
    _conn: duckdb.DuckDBPyConnection,
    fiscal_year: int,
    scope: str = DEFAULT_SCOPE,
    worker_type: str = DEFAULT_WORKER_TYPE,
) -> dict:
    """データ品質ページの KPI（全体充足率の状況）を返す.

    full_pct = 7 指標すべてを揃えた企業の割合
    avg_completeness_pct = 各企業の充足率（7 指標中いくつ報告したか）の平均
    """
    row = _conn.execute(
        f"""
        SELECT
            COUNT(DISTINCT edinet_code) AS total_companies,
            COUNT(DISTINCT CASE
                WHEN sales IS NOT NULL
                  AND operating_profit IS NOT NULL
                  AND net_profit IS NOT NULL
                  AND employee_count IS NOT NULL
                  AND female_manager_ratio IS NOT NULL
                  AND male_childcare_leave_ratio IS NOT NULL
                  AND gender_wage_gap IS NOT NULL
                THEN edinet_code END) AS full_companies,
            AVG(
                (CASE WHEN sales IS NOT NULL THEN 1 ELSE 0 END
               + CASE WHEN operating_profit IS NOT NULL THEN 1 ELSE 0 END
               + CASE WHEN net_profit IS NOT NULL THEN 1 ELSE 0 END
               + CASE WHEN employee_count IS NOT NULL THEN 1 ELSE 0 END
               + CASE WHEN female_manager_ratio IS NOT NULL THEN 1 ELSE 0 END
               + CASE WHEN male_childcare_leave_ratio IS NOT NULL THEN 1 ELSE 0 END
               + CASE WHEN gender_wage_gap IS NOT NULL THEN 1 ELSE 0 END
                ) * 100.0 / 7
            ) AS avg_completeness_pct
          FROM {_T}
         WHERE fiscal_year = ?
           AND scope = ? AND worker_type = ?
        """,
        [fiscal_year, scope, worker_type],
    ).fetchone()
    total = row[0] or 0
    full = row[1] or 0
    return {
        "total_companies": total,
        "full_companies": full,
        "full_pct": (full / total * 100.0) if total else 0.0,
        "avg_completeness_pct": float(row[2] or 0),
    }


@st.cache_data(ttl=300)
def query_industry_completeness(
    _conn: duckdb.DuckDBPyConnection,
    fiscal_year: int,
    scope: str = DEFAULT_SCOPE,
    worker_type: str = DEFAULT_WORKER_TYPE,
    min_companies: int = 3,
) -> pd.DataFrame:
    """業種別の各指標充足率を返す.

    overall_pct = 7 指標を平均した「業種としての開示充足度」。最終ソート軸に
    使う。HC 3 指標だけ抽出した hc_pct も併せて返す（人的資本に絞った比較用）。
    """
    return _conn.execute(
        f"""
        SELECT industry,
               COUNT(*) AS n_companies,
               COUNT(sales) * 100.0 / COUNT(*) AS sales_pct,
               COUNT(operating_profit) * 100.0 / COUNT(*) AS operating_profit_pct,
               COUNT(net_profit) * 100.0 / COUNT(*) AS net_profit_pct,
               COUNT(employee_count) * 100.0 / COUNT(*) AS employee_count_pct,
               COUNT(female_manager_ratio) * 100.0 / COUNT(*) AS female_manager_ratio_pct,
               COUNT(male_childcare_leave_ratio) * 100.0 / COUNT(*)
                   AS male_childcare_leave_ratio_pct,
               COUNT(gender_wage_gap) * 100.0 / COUNT(*) AS gender_wage_gap_pct,
               (COUNT(sales) + COUNT(operating_profit) + COUNT(net_profit)
                + COUNT(employee_count) + COUNT(female_manager_ratio)
                + COUNT(male_childcare_leave_ratio) + COUNT(gender_wage_gap))
                * 100.0 / (COUNT(*) * 7) AS overall_pct,
               (COUNT(female_manager_ratio) + COUNT(male_childcare_leave_ratio)
                + COUNT(gender_wage_gap)) * 100.0 / (COUNT(*) * 3) AS hc_pct
          FROM {_T}
         WHERE fiscal_year = ?
           AND scope = ? AND worker_type = ?
           AND industry IS NOT NULL
         GROUP BY industry
        HAVING COUNT(*) >= ?
         ORDER BY overall_pct DESC
        """,
        [fiscal_year, scope, worker_type, min_companies],
    ).fetchdf()


@st.cache_data(ttl=300)
def query_size_completeness(
    _conn: duckdb.DuckDBPyConnection,
    fiscal_year: int,
    scope: str = DEFAULT_SCOPE,
    worker_type: str = DEFAULT_WORKER_TYPE,
) -> pd.DataFrame:
    """売上階層別の充足率を返す（大企業ほど開示が進んでいるかを診断）.

    人的資本 3 指標に絞った hc_overall_pct と、財務 4 指標の充足率を返す。
    """
    return _conn.execute(
        f"""
        SELECT {sales_tier_case_sql('sales')} AS tier,
               COUNT(*) AS n_companies,
               COUNT(female_manager_ratio) * 100.0 / COUNT(*) AS female_manager_ratio_pct,
               COUNT(male_childcare_leave_ratio) * 100.0 / COUNT(*)
                   AS male_childcare_leave_ratio_pct,
               COUNT(gender_wage_gap) * 100.0 / COUNT(*) AS gender_wage_gap_pct,
               (COUNT(female_manager_ratio) + COUNT(male_childcare_leave_ratio)
                + COUNT(gender_wage_gap)) * 100.0 / (COUNT(*) * 3) AS hc_overall_pct,
               COUNT(operating_profit) * 100.0 / COUNT(*) AS operating_profit_pct,
               COUNT(employee_count) * 100.0 / COUNT(*) AS employee_count_pct
          FROM {_T}
         WHERE fiscal_year = ?
           AND scope = ? AND worker_type = ?
           AND sales IS NOT NULL
         GROUP BY tier
        """,
        [fiscal_year, scope, worker_type],
    ).fetchdf()


@st.cache_data(ttl=300)
def query_unreported_top_companies(
    _conn: duckdb.DuckDBPyConnection,
    fiscal_year: int,
    top_n: int = 20,
    scope: str = DEFAULT_SCOPE,
    worker_type: str = DEFAULT_WORKER_TYPE,
) -> pd.DataFrame:
    """売上 TOP のうち人的資本 3 指標のいずれかを未提出の企業を返す.

    「大企業なのに開示が進んでいない」という驚きを引き出すための一覧。
    missing_hc_count は HC 3 指標のうちいくつ未提出か（1〜3）。
    """
    return _conn.execute(
        f"""
        SELECT edinet_code, company_name, industry, sales,
               female_manager_ratio,
               male_childcare_leave_ratio,
               gender_wage_gap,
               (CASE WHEN female_manager_ratio IS NULL THEN 1 ELSE 0 END
              + CASE WHEN male_childcare_leave_ratio IS NULL THEN 1 ELSE 0 END
              + CASE WHEN gender_wage_gap IS NULL THEN 1 ELSE 0 END) AS missing_hc_count
          FROM {_T}
         WHERE fiscal_year = ?
           AND scope = ? AND worker_type = ?
           AND sales IS NOT NULL
           AND (female_manager_ratio IS NULL
                OR male_childcare_leave_ratio IS NULL
                OR gender_wage_gap IS NULL)
         ORDER BY sales DESC
         LIMIT ?
        """,
        [fiscal_year, scope, worker_type, top_n],
    ).fetchdf()


@st.cache_data(ttl=300)
def query_company_completeness(
    _conn: duckdb.DuckDBPyConnection,
    fiscal_year: int,
    industry_filter: tuple[str, ...] = (),
    scope: str = DEFAULT_SCOPE,
    worker_type: str = DEFAULT_WORKER_TYPE,
) -> pd.DataFrame:
    """企業別の充足率テーブル.

    industry_filter は @st.cache_data がハッシュできるよう tuple で受け取る
    （空 tuple なら全業種）。reported_count は 7 指標中報告した数。
    """
    base_sql = f"""
        SELECT edinet_code, company_name, industry, sales,
               (CASE WHEN sales IS NOT NULL THEN 1 ELSE 0 END
              + CASE WHEN operating_profit IS NOT NULL THEN 1 ELSE 0 END
              + CASE WHEN net_profit IS NOT NULL THEN 1 ELSE 0 END
              + CASE WHEN employee_count IS NOT NULL THEN 1 ELSE 0 END
              + CASE WHEN female_manager_ratio IS NOT NULL THEN 1 ELSE 0 END
              + CASE WHEN male_childcare_leave_ratio IS NOT NULL THEN 1 ELSE 0 END
              + CASE WHEN gender_wage_gap IS NOT NULL THEN 1 ELSE 0 END) AS reported_count
          FROM {_T}
         WHERE fiscal_year = ?
           AND scope = ? AND worker_type = ?
    """
    params: list[object] = [fiscal_year, scope, worker_type]
    if industry_filter:
        placeholders = ", ".join(["?"] * len(industry_filter))
        base_sql += f"           AND industry IN ({placeholders})\n"
        params.extend(industry_filter)
    base_sql += " ORDER BY reported_count DESC, sales DESC NULLS LAST"
    df = _conn.execute(base_sql, params).fetchdf()
    df["completeness_pct"] = df["reported_count"] * 100.0 / 7
    return df


@st.cache_data(ttl=300)
def query_default_companies_by_industry(
    _conn: duckdb.DuckDBPyConnection,
    fiscal_year: int,
    top_n_industries: int = 5,
    per_industry: int = 1,
) -> list[str]:
    """業種代表企業の edinet_code リストを返す（売上規模上位の業種から、各業種の売上 TOP1）.

    財務指標ページのデフォルト企業選択で使う。業種ごとに 1 社ずつ売上TOP1を取り、
    業種は売上総額の大きい順に並べた上から `top_n_industries` 業種から選ぶ。
    """
    df = _conn.execute(
        f"""
        WITH ranked AS (
            SELECT edinet_code, company_name, industry, sales,
                   ROW_NUMBER() OVER (
                       PARTITION BY industry ORDER BY sales DESC NULLS LAST
                   ) AS rn
              FROM {_T}
             WHERE fiscal_year = ?
               AND scope = ? AND worker_type = ?
               AND sales IS NOT NULL
               AND industry IS NOT NULL
        ),
        top_industries AS (
            SELECT industry, SUM(sales) AS industry_total
              FROM {_T}
             WHERE fiscal_year = ?
               AND scope = ? AND worker_type = ?
               AND sales IS NOT NULL
               AND industry IS NOT NULL
             GROUP BY industry
             ORDER BY industry_total DESC
             LIMIT ?
        )
        SELECT r.edinet_code
          FROM ranked r
          JOIN top_industries t USING (industry)
         WHERE r.rn <= ?
         ORDER BY t.industry_total DESC, r.rn
        """,
        [
            fiscal_year, DEFAULT_SCOPE, DEFAULT_WORKER_TYPE,
            fiscal_year, DEFAULT_SCOPE, DEFAULT_WORKER_TYPE,
            top_n_industries, per_industry,
        ],
    ).fetchdf()
    return df["edinet_code"].tolist()


@st.cache_data(ttl=300)
def query_companies_by_preset(
    _conn: duckdb.DuckDBPyConnection,
    preset: str,
    fiscal_year: int,
    top_n: int = 10,
    scope: str = DEFAULT_SCOPE,
    worker_type: str = DEFAULT_WORKER_TYPE,
) -> list[str]:
    """プリセット別の企業 edinet_code リストを返す.

    preset:
      - "industry_rep": 業種代表（業種別売上TOP1を top_n 業種ぶん）
      - "sales_top10": 売上 TOP top_n
      - "operating_margin_top10": 営業利益率 TOP top_n
      - "growth_top10": 売上成長率 TOP top_n（前年比）
    """
    if preset == "industry_rep":
        return query_default_companies_by_industry(
            _conn, fiscal_year, top_n_industries=top_n, per_industry=1
        )
    if preset == "sales_top10":
        df = _conn.execute(
            f"""
            SELECT edinet_code
              FROM {_T}
             WHERE fiscal_year = ?
               AND scope = ? AND worker_type = ?
               AND sales IS NOT NULL
             ORDER BY sales DESC NULLS LAST
             LIMIT ?
            """,
            [fiscal_year, scope, worker_type, top_n],
        ).fetchdf()
        return df["edinet_code"].tolist()
    if preset == "operating_margin_top10":
        df = _conn.execute(
            f"""
            SELECT edinet_code
              FROM {_T}
             WHERE fiscal_year = ?
               AND scope = ? AND worker_type = ?
               AND sales IS NOT NULL AND sales > 0
               AND operating_profit IS NOT NULL
             ORDER BY (operating_profit * 1.0 / sales) DESC NULLS LAST
             LIMIT ?
            """,
            [fiscal_year, scope, worker_type, top_n],
        ).fetchdf()
        return df["edinet_code"].tolist()
    if preset == "growth_top10":
        df = _conn.execute(
            f"""
            WITH curr AS (
                SELECT edinet_code, sales AS sales_to
                  FROM {_T}
                 WHERE fiscal_year = ?
                   AND scope = ? AND worker_type = ?
                   AND sales IS NOT NULL AND sales > 0
            ),
            prev AS (
                SELECT edinet_code, sales AS sales_from
                  FROM {_T}
                 WHERE fiscal_year = ? - 1
                   AND scope = ? AND worker_type = ?
                   AND sales IS NOT NULL AND sales > 0
            )
            SELECT c.edinet_code,
                   (c.sales_to - p.sales_from) * 1.0 / p.sales_from AS growth_rate
              FROM curr c
              JOIN prev p USING (edinet_code)
             ORDER BY growth_rate DESC NULLS LAST
             LIMIT ?
            """,
            [fiscal_year, scope, worker_type, fiscal_year, scope, worker_type, top_n],
        ).fetchdf()
        return df["edinet_code"].tolist()
    return []


@st.cache_data(ttl=300)
def query_financial_summary_extended(
    _conn: duckdb.DuckDBPyConnection,
    year_min: int,
    year_max: int,
    industry_filter: tuple[str, ...] = (),
) -> pd.DataFrame:
    """年度別の財務指標集計統計を Q1/Q3 拡張版で返す.

    既存の query_financial_summary_stats と並行運用し、ダッシュボード側で
    箱ひげ図的な比較ができるよう四分位 (Q1, Q3) を追加。
    """
    base_sql = f"""
        SELECT fiscal_year,
               COUNT(*)                          AS count,
               AVG(sales)                        AS avg_sales,
               MEDIAN(sales)                     AS med_sales,
               quantile_cont(sales, 0.25)        AS q1_sales,
               quantile_cont(sales, 0.75)        AS q3_sales,
               AVG(operating_profit)             AS avg_operating_profit,
               MEDIAN(operating_profit)          AS med_operating_profit,
               quantile_cont(operating_profit, 0.25) AS q1_operating_profit,
               quantile_cont(operating_profit, 0.75) AS q3_operating_profit,
               AVG(net_profit)                   AS avg_net_profit,
               MEDIAN(net_profit)                AS med_net_profit,
               AVG(employee_count)               AS avg_employee_count,
               MEDIAN(employee_count)            AS med_employee_count
          FROM {_T}
         WHERE fiscal_year BETWEEN ? AND ?
           AND scope = ? AND worker_type = ?
    """
    params: list[object] = [year_min, year_max, DEFAULT_SCOPE, DEFAULT_WORKER_TYPE]
    if industry_filter:
        placeholders = ", ".join(["?"] * len(industry_filter))
        base_sql += f"           AND industry IN ({placeholders})\n"
        params.extend(industry_filter)
    base_sql += " GROUP BY fiscal_year ORDER BY fiscal_year"
    return _conn.execute(base_sql, params).fetchdf()


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
