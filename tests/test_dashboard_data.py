"""dashboard/data.py のユニットテスト — インメモリ DuckDB を使用."""

from __future__ import annotations

import duckdb
import pytest
import streamlit as st

from edinet_pipeline.dashboard.data import (
    query_available_companies,
    query_available_fiscal_years,
    query_company_comparison,
    query_completeness_over_time,
    query_coverage_matrix,
    query_evidence_summary,
    query_financial_summary_stats,
    query_financial_trends,
    query_hc_distribution,
    query_hc_scatter,
    query_hc_trends,
    query_kpi_summary,
    query_status_distribution,
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
            source_name VARCHAR
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE analytics.metric_evidence (
            doc_id VARCHAR,
            edinet_code VARCHAR,
            company_name VARCHAR,
            fiscal_year BIGINT,
            submitted_date DATE,
            report_status VARCHAR,
            metric_name VARCHAR,
            item_name VARCHAR,
            raw_value VARCHAR,
            relative_year VARCHAR,
            source_file VARCHAR,
            matched_by VARCHAR,
            element_id VARCHAR,
            scope VARCHAR,
            worker_type VARCHAR
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
             15.5, 30.0, 75.0, 'EDINET_CSV'),
            ('E00001', 'Company A', '電気機器', 2024, 'D002', '2025-03-15', 'processed',
             1200000, 120000, 60000, 520, 'reporting_company', 'all',
             18.0, 35.0, 78.0, 'EDINET_CSV'),
            ('E00002', 'Company B', '情報・通信業', 2023, 'D003', '2024-03-20', 'processed',
             500000, 50000, 25000, 200, 'reporting_company', 'all',
             NULL, NULL, NULL, 'EDINET_CSV'),
            ('E00002', 'Company B', '情報・通信業', 2024, 'D004', '2025-03-20', 'failed',
             NULL, NULL, NULL, NULL, 'reporting_company', 'all',
             NULL, NULL, NULL, 'EDINET_CSV'),
            ('E00003', 'Company C', 'サービス業', 2023, 'D005', '2024-03-25', 'skipped',
             NULL, NULL, NULL, NULL, 'reporting_company', 'all',
             NULL, NULL, NULL, 'EDINET_CSV')
        """
    )
    connection.execute(
        """
        INSERT INTO analytics.metric_evidence VALUES
            ('D001', 'E00001', 'Company A', 2023, '2024-03-15', 'processed',
             'sales', '売上高', '1000000', '当期', 'jpcrp.csv', 'item_name_match',
             'jpcrp_cor:NetSales', NULL, NULL),
            ('D001', 'E00001', 'Company A', 2023, '2024-03-15', 'processed',
             'female_manager_ratio', '管理職に占める女性', '15.5', '当期',
             'text_block.csv', 'text_fallback', NULL,
             'reporting_company', 'all'),
            ('D002', 'E00001', 'Company A', 2024, '2025-03-15', 'processed',
             'sales', '売上高', '1200000', '当期', 'jpcrp.csv', 'item_name_match',
             'jpcrp_cor:NetSales', NULL, NULL),
            ('D003', 'E00002', 'Company B', 2023, '2024-03-20', 'processed',
             'sales', '売上高', '500000', '当期', 'jpcrp.csv', 'item_name_match',
             'jpcrp_cor:NetSales', NULL, NULL)
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


class TestStatusDistribution:
    def test_groups_correctly(self, conn):
        df = query_status_distribution(conn)
        assert len(df) > 0
        assert set(df.columns) == {"fiscal_year", "status", "doc_count"}
        processed_2023 = df[(df["fiscal_year"] == 2023) & (df["status"] == "processed")]
        assert processed_2023["doc_count"].iloc[0] == 2


class TestFinancialTrends:
    def test_filters_by_company_and_year(self, conn):
        df = query_financial_trends(conn, ["E00001"], 2023, 2024)
        assert len(df) == 2
        assert all(df["edinet_code"] == "E00001")

    def test_empty_codes(self, conn):
        df = query_financial_trends(conn, [], 2023, 2024)
        assert len(df) == 0

    def test_year_range_filter(self, conn):
        df = query_financial_trends(conn, ["E00001"], 2024, 2024)
        assert len(df) == 1
        assert df["fiscal_year"].iloc[0] == 2024


class TestCompanyComparison:
    def test_ranks_by_metric(self, conn):
        df = query_company_comparison(conn, "sales", 2023, top_n=10)
        assert len(df) == 2
        assert df["sales"].iloc[0] >= df["sales"].iloc[1]

    def test_invalid_metric_raises(self, conn):
        with pytest.raises(ValueError, match="Invalid metric"):
            query_company_comparison(conn, "invalid_col", 2023)

    def test_top_n_limit(self, conn):
        df = query_company_comparison(conn, "sales", 2023, top_n=1)
        assert len(df) == 1


class TestFinancialSummaryStats:
    def test_returns_stats_per_year(self, conn):
        df = query_financial_summary_stats(conn, 2023, 2024)
        assert len(df) == 2
        assert "avg_sales" in df.columns
        assert "med_sales" in df.columns


class TestHcDistribution:
    def test_excludes_nulls(self, conn):
        df = query_hc_distribution(conn, "female_manager_ratio", 2023)
        assert len(df) == 1
        assert df["edinet_code"].iloc[0] == "E00001"

    def test_invalid_metric_raises(self, conn):
        with pytest.raises(ValueError, match="Invalid metric"):
            query_hc_distribution(conn, "sales", 2023)


class TestHcTrends:
    def test_returns_averages(self, conn):
        df = query_hc_trends(conn, 2023, 2024)
        assert len(df) == 2
        assert "avg_female_manager_ratio" in df.columns
        assert "n_female_manager" in df.columns


class TestHcScatter:
    def test_returns_scatter_data(self, conn):
        df = query_hc_scatter(conn, 2023)
        assert len(df) == 1
        assert "female_manager_ratio" in df.columns
        assert "male_childcare_leave_ratio" in df.columns

    def test_no_data_year(self, conn):
        df = query_hc_scatter(conn, 2020)
        assert len(df) == 0


class TestCoverageMatrix:
    def test_flags_missing_values(self, conn):
        df = query_coverage_matrix(conn, 2023)
        assert len(df) == 3
        company_b = df[df["edinet_code"] == "E00002"]
        assert company_b["female_manager_ratio"].iloc[0] == 0

        company_a = df[df["edinet_code"] == "E00001"]
        assert company_a["sales"].iloc[0] == 1


class TestCompletenessOverTime:
    def test_calculates_percentages(self, conn):
        df = query_completeness_over_time(conn)
        assert len(df) == 2
        assert "sales_pct" in df.columns
        row_2023 = df[df["fiscal_year"] == 2023]
        # 2023: 2/3 companies have sales → 66.67%
        assert 60.0 < row_2023["sales_pct"].iloc[0] < 70.0


class TestEvidenceSummary:
    def test_groups_by_matched_by(self, conn):
        df = query_evidence_summary(conn)
        assert len(df) > 0
        assert set(df.columns) == {"metric_name", "matched_by", "evidence_count"}
        sales_rows = df[df["metric_name"] == "sales"]
        assert sales_rows["evidence_count"].sum() == 3

    def test_empty_db(self, empty_conn):
        df = query_evidence_summary(empty_conn)
        assert len(df) == 0
