"""human_capital_metrics に従業員情報3指標 (平均年間給与・平均勤続年数・平均年齢) を追加.

「従業員の状況」の提出会社単体開示から要素ID完全一致で抽出する3指標の格納先。
割合指標 (Numeric(5,2)) と異なり、平均年間給与は円単位で最大9桁を超えるため
Numeric(12,2) を採用する。

vw_company_year_metrics は列を明示列挙しているため、新列を露出するには
DROP → CREATE で再構築する (0004 と同じパターン)。
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0006_add_employee_info_metrics"
down_revision = "0005_add_processing_started_at"
branch_labels = None
depends_on = None

# (列名, 型) — 給与は円単位で桁が大きい、勤続年数/年齢は小数2桁で十分
_NEW_COLUMNS: list[tuple[str, sa.types.TypeEngine]] = [
    ("average_annual_salary", sa.Numeric(12, 2)),
    ("average_years_of_service", sa.Numeric(5, 2)),
    ("average_age", sa.Numeric(5, 2)),
]

_VIEW_WITH_EMPLOYEE_INFO = """
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
    hm.average_annual_salary,
    hm.average_years_of_service,
    hm.average_age,
    COALESCE(hm.source_name, 'EDINET_CSV') AS source_name
FROM financial_reports fr
JOIN companies c
  ON c.edinet_code = fr.edinet_code
LEFT JOIN human_capital_metrics hm
  ON hm.edinet_code = fr.edinet_code
 AND hm.fiscal_year = fr.fiscal_year
"""

# 0004 時点のビュー定義 (downgrade 用の復元)
_VIEW_WITHOUT_EMPLOYEE_INFO = """
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


def _has_column(inspector: sa.Inspector, table: str, column: str) -> bool:
    """指定テーブルに列が存在するか (再実行時の冪等ガード。0003 と同じ方式)."""
    return any(c["name"] == column for c in inspector.get_columns(table))


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    for column_name, column_type in _NEW_COLUMNS:
        if not _has_column(inspector, "human_capital_metrics", column_name):
            op.add_column(
                "human_capital_metrics",
                sa.Column(column_name, column_type, nullable=True),
            )

    op.execute("DROP VIEW IF EXISTS vw_company_year_metrics")
    op.execute(_VIEW_WITH_EMPLOYEE_INFO)


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS vw_company_year_metrics")
    op.execute(_VIEW_WITHOUT_EMPLOYEE_INFO)
    for column_name, _ in reversed(_NEW_COLUMNS):
        op.drop_column("human_capital_metrics", column_name)
