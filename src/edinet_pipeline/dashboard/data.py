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
        ORDER BY company_name
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
        ORDER BY fiscal_year, company_name
        """,
        [*edinet_codes, year_min, year_max, DEFAULT_SCOPE, DEFAULT_WORKER_TYPE],
    ).fetchdf()


def query_company_comparison(
    conn: duckdb.DuckDBPyConnection,
    metric: str,
    fiscal_year: int,
    top_n: int = 20,
    *,
    scope: str = DEFAULT_SCOPE,
    worker_type: str = DEFAULT_WORKER_TYPE,
) -> pd.DataFrame:
    """指定年度・指定指標で企業をランキングする (HC指標は scope/worker_type で次元を選択可能)."""
    _validate_metric(metric, ALLOWED_ALL_METRICS)
    return conn.execute(
        f"""
        SELECT edinet_code, company_name, {metric}
        FROM {_T}
        WHERE fiscal_year = ? AND {metric} IS NOT NULL
          AND scope = ? AND worker_type = ?
        ORDER BY {metric} DESC
        LIMIT ?
        """,
        [fiscal_year, scope, worker_type, top_n],
    ).fetchdf()


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
        f"ORDER BY company_name",
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
        ORDER BY male_childcare_leave_ratio DESC, company_name
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
         ORDER BY (MAX(r) - MEDIAN(r)) DESC, company_name
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
         ORDER BY company_name
         LIMIT ?
        """,
        [pattern, limit],
    ).fetchdf()
