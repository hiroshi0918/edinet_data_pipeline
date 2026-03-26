"""データアクセス層 — DuckDB ファイルからの読み取り専用クエリ関数群."""

from __future__ import annotations

import duckdb
import pandas as pd
import streamlit as st

from edinet_pipeline.dashboard.constants import (
    ALLOWED_ALL_METRICS,
    ALLOWED_HC_METRICS,
    TABLE_COMPANY_YEAR_METRICS,
    TABLE_METRIC_EVIDENCE,
)

_T = TABLE_COMPANY_YEAR_METRICS
_E = TABLE_METRIC_EVIDENCE


@st.cache_resource
def get_connection(duckdb_path: str) -> duckdb.DuckDBPyConnection:
    """DuckDB ファイルへの読み取り専用接続を返す (Streamlit セッション間で再利用)."""
    return duckdb.connect(duckdb_path, read_only=True)


def _validate_metric(metric: str, allowed: set[str]) -> None:
    """metric が許可リストに含まれなければ ValueError を送出する."""
    if metric not in allowed:
        raise ValueError(f"Invalid metric: {metric}")


# ------------------------------------------------------------------ #
#  フィルター用ヘルパー
# ------------------------------------------------------------------ #


@st.cache_data(ttl=300)
def query_available_companies(_conn: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """フィルター用の企業一覧 (edinet_code, company_name) を返す."""
    return _conn.execute(
        f"SELECT DISTINCT edinet_code, company_name FROM {_T} ORDER BY company_name"
    ).fetchdf()


@st.cache_data(ttl=300)
def query_available_fiscal_years(_conn: duckdb.DuckDBPyConnection) -> list[int]:
    """フィルター用の年度リストを昇順で返す."""
    df = _conn.execute(
        f"SELECT DISTINCT fiscal_year FROM {_T} ORDER BY fiscal_year"
    ).fetchdf()
    return df["fiscal_year"].tolist()


# ------------------------------------------------------------------ #
#  概要 (Overview)
# ------------------------------------------------------------------ #


@st.cache_data(ttl=300)
def query_kpi_summary(_conn: duckdb.DuckDBPyConnection) -> dict:
    """KPI サマリー: 企業数、年度数、レコード数、最新提出日."""
    row = _conn.execute(
        f"SELECT "
        f"  COUNT(DISTINCT edinet_code) AS company_count, "
        f"  COUNT(DISTINCT fiscal_year) AS year_count, "
        f"  COUNT(*) AS total_records, "
        f"  MAX(submitted_date) AS latest_submission "
        f"FROM {_T}"
    ).fetchone()
    return {
        "company_count": row[0],
        "year_count": row[1],
        "total_records": row[2],
        "latest_submission": row[3],
    }


@st.cache_data(ttl=300)
def query_status_distribution(_conn: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """fiscal_year x status の件数分布."""
    return _conn.execute(
        f"SELECT fiscal_year, status, COUNT(*) AS doc_count "
        f"FROM {_T} "
        f"GROUP BY fiscal_year, status "
        f"ORDER BY fiscal_year, status"
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
    """選択企業の財務指標推移を返す."""
    if not edinet_codes:
        return pd.DataFrame()
    placeholders = ", ".join(["?"] * len(edinet_codes))
    return conn.execute(
        f"SELECT edinet_code, company_name, fiscal_year, "
        f"  sales, operating_profit, net_profit, employee_count "
        f"FROM {_T} "
        f"WHERE edinet_code IN ({placeholders}) "
        f"  AND fiscal_year BETWEEN ? AND ? "
        f"ORDER BY fiscal_year, company_name",
        [*edinet_codes, year_min, year_max],
    ).fetchdf()


def query_company_comparison(
    conn: duckdb.DuckDBPyConnection,
    metric: str,
    fiscal_year: int,
    top_n: int = 20,
) -> pd.DataFrame:
    """指定年度・指定指標で企業をランキングする."""
    _validate_metric(metric, ALLOWED_ALL_METRICS)
    return conn.execute(
        f"SELECT edinet_code, company_name, {metric} "
        f"FROM {_T} "
        f"WHERE fiscal_year = ? AND {metric} IS NOT NULL "
        f"ORDER BY {metric} DESC "
        f"LIMIT ?",
        [fiscal_year, top_n],
    ).fetchdf()


@st.cache_data(ttl=300)
def query_financial_summary_stats(
    _conn: duckdb.DuckDBPyConnection,
    year_min: int,
    year_max: int,
) -> pd.DataFrame:
    """年度別の財務指標集計統計."""
    return _conn.execute(
        f"SELECT fiscal_year, "
        f"  COUNT(*) AS count, "
        f"  AVG(sales) AS avg_sales, "
        f"  MEDIAN(sales) AS med_sales, "
        f"  MIN(sales) AS min_sales, "
        f"  MAX(sales) AS max_sales, "
        f"  AVG(operating_profit) AS avg_operating_profit, "
        f"  MEDIAN(operating_profit) AS med_operating_profit, "
        f"  AVG(net_profit) AS avg_net_profit, "
        f"  MEDIAN(net_profit) AS med_net_profit, "
        f"  AVG(employee_count) AS avg_employee_count, "
        f"  MEDIAN(employee_count) AS med_employee_count "
        f"FROM {_T} "
        f"WHERE fiscal_year BETWEEN ? AND ? "
        f"GROUP BY fiscal_year "
        f"ORDER BY fiscal_year",
        [year_min, year_max],
    ).fetchdf()


# ------------------------------------------------------------------ #
#  人的資本指標 (Human Capital)
# ------------------------------------------------------------------ #


def query_hc_distribution(
    conn: duckdb.DuckDBPyConnection,
    metric: str,
    fiscal_year: int,
) -> pd.DataFrame:
    """指定年度の HC 指標分布データ (NULL 除外)."""
    _validate_metric(metric, ALLOWED_HC_METRICS)
    return conn.execute(
        f"SELECT edinet_code, company_name, {metric} "
        f"FROM {_T} "
        f"WHERE fiscal_year = ? AND {metric} IS NOT NULL",
        [fiscal_year],
    ).fetchdf()


@st.cache_data(ttl=300)
def query_hc_trends(
    _conn: duckdb.DuckDBPyConnection,
    year_min: int,
    year_max: int,
) -> pd.DataFrame:
    """HC 指標の年度別平均推移."""
    return _conn.execute(
        f"SELECT fiscal_year, "
        f"  AVG(female_manager_ratio) AS avg_female_manager_ratio, "
        f"  AVG(male_childcare_leave_ratio) AS avg_male_childcare_leave_ratio, "
        f"  AVG(gender_wage_gap) AS avg_gender_wage_gap, "
        f"  COUNT(female_manager_ratio) AS n_female_manager, "
        f"  COUNT(male_childcare_leave_ratio) AS n_male_childcare_leave, "
        f"  COUNT(gender_wage_gap) AS n_gender_wage_gap "
        f"FROM {_T} "
        f"WHERE fiscal_year BETWEEN ? AND ? "
        f"GROUP BY fiscal_year "
        f"ORDER BY fiscal_year",
        [year_min, year_max],
    ).fetchdf()


def query_hc_scatter(
    conn: duckdb.DuckDBPyConnection,
    fiscal_year: int,
) -> pd.DataFrame:
    """女性管理職比率 vs 男性育休取得率の散布図データ."""
    return conn.execute(
        f"SELECT company_name, female_manager_ratio, "
        f"  male_childcare_leave_ratio, employee_count "
        f"FROM {_T} "
        f"WHERE fiscal_year = ? "
        f"  AND female_manager_ratio IS NOT NULL "
        f"  AND male_childcare_leave_ratio IS NOT NULL",
        [fiscal_year],
    ).fetchdf()


# ------------------------------------------------------------------ #
#  データ品質 (Data Quality)
# ------------------------------------------------------------------ #


@st.cache_data(ttl=300)
def query_coverage_matrix(
    _conn: duckdb.DuckDBPyConnection,
    fiscal_year: int,
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
        f"WHERE fiscal_year = ? "
        f"ORDER BY company_name",
        [fiscal_year],
    ).fetchdf()


@st.cache_data(ttl=300)
def query_completeness_over_time(_conn: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """年度別の各指標非 NULL 企業割合 (%)."""
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
        f"GROUP BY fiscal_year "
        f"ORDER BY fiscal_year"
    ).fetchdf()


@st.cache_data(ttl=300)
def query_evidence_summary(_conn: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """metric_name x matched_by ごとの抽出根拠件数."""
    return _conn.execute(
        f"SELECT metric_name, matched_by, COUNT(*) AS evidence_count "
        f"FROM {_E} "
        f"GROUP BY metric_name, matched_by "
        f"ORDER BY metric_name, evidence_count DESC"
    ).fetchdf()
