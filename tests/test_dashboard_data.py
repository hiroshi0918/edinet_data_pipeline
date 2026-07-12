"""dashboard/data.py のユニットテスト — インメモリ DuckDB を使用."""

from __future__ import annotations

import duckdb
import pytest
import streamlit as st

from edinet_pipeline.dashboard.data import (
    query_available_companies,
    query_available_fiscal_years,
    query_company_comparison,
    query_company_profile,
    query_financial_ranking_with_hc,
    query_hc_distribution_by_industry,
    query_kpi_summary,
)


@pytest.fixture(autouse=True)
def _clear_streamlit_cache():
    """各テスト前に Streamlit キャッシュをクリアする."""
    st.cache_data.clear()
    yield
    st.cache_data.clear()


def _create_analytics_schema(connection: duckdb.DuckDBPyConnection) -> None:
    """テスト用の analytics スキーマとテーブルを作成する.

    v0.3 で scope/worker_type/element_id 等の次元カラムが追加されているため、
    テスト用スキーマもそれに合わせて拡張する。
    """
    connection.execute("CREATE SCHEMA analytics")
    connection.execute(
        """
        CREATE TABLE analytics.company_year_metrics (
            edinet_code VARCHAR,
            company_name VARCHAR,
            industry VARCHAR,
            fiscal_year BIGINT,
            doc_id VARCHAR,
            submitted_date DATE,
            status VARCHAR,
            sales BIGINT,
            operating_profit BIGINT,
            net_profit BIGINT,
            employee_count BIGINT,
            scope VARCHAR,
            worker_type VARCHAR,
            female_manager_ratio DECIMAL(5,2),
            male_childcare_leave_ratio DECIMAL(5,2),
            gender_wage_gap DECIMAL(5,2),
            average_annual_salary DECIMAL(12,2),
            average_years_of_service DECIMAL(5,2),
            average_age DECIMAL(5,2),
            source_name VARCHAR
        )
        """
    )


@pytest.fixture()
def conn():
    """テストデータを投入したインメモリ DuckDB 接続を返す."""
    connection = duckdb.connect(":memory:")
    _create_analytics_schema(connection)
    connection.execute(
        """
        INSERT INTO analytics.company_year_metrics VALUES
            ('E00001', 'Company A', '電気機器', 2023, 'D001', '2024-03-15', 'processed',
             1000000, 100000, 50000, 500, 'reporting_company', 'all',
             15.5, 30.0, 75.0, 6500000, 12.3, 42.1, 'EDINET_CSV'),
            ('E00001', 'Company A', '電気機器', 2024, 'D002', '2025-03-15', 'processed',
             1200000, 120000, 60000, 520, 'reporting_company', 'all',
             18.0, 35.0, 78.0, 6800000, 12.8, 42.5, 'EDINET_CSV'),
            ('E00002', 'Company B', '情報・通信業', 2023, 'D003', '2024-03-20', 'processed',
             500000, 50000, 25000, 200, 'reporting_company', 'all',
             NULL, NULL, NULL, 4200000, 4.2, 36.5, 'EDINET_CSV'),
            ('E00002', 'Company B', '情報・通信業', 2024, 'D004', '2025-03-20', 'failed',
             NULL, NULL, NULL, NULL, 'reporting_company', 'all',
             NULL, NULL, NULL, NULL, NULL, NULL, 'EDINET_CSV'),
            ('E00003', 'Company C', 'サービス業', 2023, 'D005', '2024-03-25', 'skipped',
             NULL, NULL, NULL, NULL, 'reporting_company', 'all',
             NULL, NULL, NULL, NULL, NULL, NULL, 'EDINET_CSV')
        """
    )
    yield connection
    connection.close()


@pytest.fixture()
def empty_conn():
    """空のスキーマのみのインメモリ DuckDB 接続."""
    connection = duckdb.connect(":memory:")
    _create_analytics_schema(connection)
    yield connection
    connection.close()


class TestAvailableCompanies:
    def test_returns_all_companies(self, conn):
        df = query_available_companies(conn)
        assert len(df) == 3
        assert set(df["edinet_code"]) == {"E00001", "E00002", "E00003"}

    def test_empty_db(self, empty_conn):
        df = query_available_companies(empty_conn)
        assert len(df) == 0


class TestAvailableFiscalYears:
    def test_returns_sorted_years(self, conn):
        years = query_available_fiscal_years(conn)
        assert years == [2023, 2024]

    def test_empty_db(self, empty_conn):
        years = query_available_fiscal_years(empty_conn)
        assert years == []


class TestKpiSummary:
    def test_counts(self, conn):
        kpi = query_kpi_summary(conn)
        assert kpi["company_count"] == 3
        assert kpi["year_count"] == 2
        assert kpi["total_records"] == 5

    def test_empty_db(self, empty_conn):
        kpi = query_kpi_summary(empty_conn)
        assert kpi["company_count"] == 0
        assert kpi["total_records"] == 0


class TestCompanyComparison:
    def test_ranks_by_metric_descending(self, conn):
        df = query_company_comparison(conn, "sales", 2023, top_n=10)
        assert len(df) == 2
        assert df["sales"].iloc[0] >= df["sales"].iloc[1]

    def test_ranks_ascending_for_bottom(self, conn):
        df = query_company_comparison(conn, "sales", 2023, top_n=10, ascending=True)
        assert len(df) == 2
        # 昇順なので下位 (小さい順) が先頭に来る
        assert df["sales"].iloc[0] <= df["sales"].iloc[1]
        assert df["edinet_code"].iloc[0] == "E00002"

    def test_invalid_metric_raises(self, conn):
        with pytest.raises(ValueError, match="Invalid metric"):
            query_company_comparison(conn, "invalid_col", 2023)

    def test_top_n_limit(self, conn):
        df = query_company_comparison(conn, "sales", 2023, top_n=1)
        assert len(df) == 1

    def test_ranks_by_average_annual_salary(self, conn):
        """従業員情報3指標も許可リスト経由でランキングできること."""
        df = query_company_comparison(conn, "average_annual_salary", 2023, top_n=10)
        assert len(df) == 2
        assert df["edinet_code"].iloc[0] == "E00001"  # 650万 > 420万
        assert float(df["average_annual_salary"].iloc[0]) == pytest.approx(6500000)


class TestCompanyProfile:
    def test_includes_employee_info_columns(self, conn):
        """企業プロファイルに従業員情報3列が含まれること."""
        df = query_company_profile(conn, "E00001")
        assert {
            "average_annual_salary", "average_years_of_service", "average_age",
        } <= set(df.columns)
        row_2023 = df[df["fiscal_year"] == 2023].iloc[0]
        assert float(row_2023["average_years_of_service"]) == pytest.approx(12.3)
        assert float(row_2023["average_age"]) == pytest.approx(42.1)


class TestHcDistributionByIndustry:
    def test_returns_per_company_values_with_industry(self, conn):
        df = query_hc_distribution_by_industry(
            conn, "female_manager_ratio", 2023, min_companies=1
        )
        # 2023 で female_manager_ratio を持つのは E00001 (電気機器) のみ
        assert len(df) == 1
        assert set(df.columns) == {"industry", "edinet_code", "company_name", "value"}
        assert df["industry"].iloc[0] == "電気機器"
        assert float(df["value"].iloc[0]) == pytest.approx(15.5)

    def test_min_companies_filters_small_industries(self, conn):
        # どの業種も 5 社未満なので空になる
        df = query_hc_distribution_by_industry(
            conn, "female_manager_ratio", 2023, min_companies=5
        )
        assert len(df) == 0

    def test_invalid_metric_raises(self, conn):
        with pytest.raises(ValueError, match="Invalid metric"):
            query_hc_distribution_by_industry(conn, "sales", 2023)


class TestFinancialRankingWithHc:
    def test_top_ranking_includes_hc_columns(self, conn):
        df = query_financial_ranking_with_hc(conn, "sales", 2023, top_n=10)
        assert len(df) == 2
        assert {"value", "female_manager_ratio", "gender_wage_gap"} <= set(df.columns)
        assert df["value"].iloc[0] >= df["value"].iloc[1]

    def test_bottom_ranking_respects_min_value_floor(self, conn):
        # 売上 60 万円以上に限定 → E00002 (50 万) は除外され E00001 のみ
        df = query_financial_ranking_with_hc(
            conn, "sales", 2023, top_n=10, ascending=True, min_value=600000
        )
        assert len(df) == 1
        assert df["edinet_code"].iloc[0] == "E00001"

    def test_invalid_metric_raises(self, conn):
        # 財務指標以外 (HC) は許可リスト外
        with pytest.raises(ValueError, match="Invalid metric"):
            query_financial_ranking_with_hc(conn, "female_manager_ratio", 2023)
