"""vw_company_year_metrics に companies.industry 列を追加.

業界ピア比較を有効にするため、`companies.industry` を集計ビューにも露出させる。
PostgreSQL の CREATE OR REPLACE VIEW は列順序の変更・挿入を許さないため、
DROP → CREATE で再構築する (0003 と同じパターン)。
"""

from __future__ import annotations

from alembic import op

revision = "0004_add_industry_to_view"
down_revision = "0003_add_dimension_columns"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("DROP VIEW IF EXISTS vw_company_year_metrics")
    op.execute(
        """
        CREATE VIEW vw_company_year_metrics AS
        SELECT
            c.edinet_code,
            c.company_name,
            c.industry,
            fr.fiscal_year,
            fr.doc_id,
            fr.submitted_date,
            fr.status,
            fr.sales,
            fr.operating_profit,
            fr.net_profit,
            fr.employee_count,
            COALESCE(hm.scope, 'reporting_company') AS scope,
            COALESCE(hm.worker_type, 'all')         AS worker_type,
            hm.female_manager_ratio,
            hm.male_childcare_leave_ratio,
            hm.gender_wage_gap,
            COALESCE(hm.source_name, 'EDINET_CSV') AS source_name
        FROM financial_reports fr
        JOIN companies c
          ON c.edinet_code = fr.edinet_code
        LEFT JOIN human_capital_metrics hm
          ON hm.edinet_code = fr.edinet_code
         AND hm.fiscal_year = fr.fiscal_year
        """
    )


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS vw_company_year_metrics")
    # 0003 のビューを復元
    op.execute(
        """
        CREATE VIEW vw_company_year_metrics AS
        SELECT
            c.edinet_code,
            c.company_name,
            fr.fiscal_year,
            fr.doc_id,
            fr.submitted_date,
            fr.status,
            fr.sales,
            fr.operating_profit,
            fr.net_profit,
            fr.employee_count,
            COALESCE(hm.scope, 'reporting_company') AS scope,
            COALESCE(hm.worker_type, 'all')         AS worker_type,
            hm.female_manager_ratio,
            hm.male_childcare_leave_ratio,
            hm.gender_wage_gap,
            COALESCE(hm.source_name, 'EDINET_CSV') AS source_name
        FROM financial_reports fr
        JOIN companies c
          ON c.edinet_code = fr.edinet_code
        LEFT JOIN human_capital_metrics hm
          ON hm.edinet_code = fr.edinet_code
         AND hm.fiscal_year = fr.fiscal_year
        """
    )
