"""human_capital_metrics を書類 (doc_id) 単位のキーに付け替える.

同じ periodEnd 暦年に変則決算が 2 通あると、旧 UNIQUE
(edinet_code, fiscal_year, scope, worker_type, source_name) では後勝ち上書き
になり、先に処理した期の人的資本が消える。書類 FK を主キー側に移し、
vw_company_year_metrics の JOIN も doc_id に切り替える。
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0007_human_metrics_by_doc_id"
down_revision = "0006_add_employee_info_metrics"
branch_labels = None
depends_on = None

OLD_UNIQUE = "uq_human_capital_metrics_company_year_scope_worker_source"
NEW_UNIQUE = "uq_human_capital_metrics_doc_scope_worker_source"

_VIEW_ON_DOC_ID = """
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
  ON hm.doc_id = fr.doc_id
"""

_VIEW_ON_COMPANY_YEAR = """
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


def _has_column(inspector: sa.Inspector, table: str, column: str) -> bool:
    return any(c["name"] == column for c in inspector.get_columns(table))


def _has_unique(inspector: sa.Inspector, table: str, name: str) -> bool:
    return any(c["name"] == name for c in inspector.get_unique_constraints(table))


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not _has_column(inspector, "human_capital_metrics", "doc_id"):
        op.add_column(
            "human_capital_metrics",
            sa.Column("doc_id", sa.String(length=50), nullable=True),
        )
        op.create_foreign_key(
            "fk_human_capital_metrics_doc_id",
            "human_capital_metrics",
            "financial_reports",
            ["doc_id"],
            ["doc_id"],
            ondelete="CASCADE",
        )

    # 同一 (会社, 年度) に複数書類がある場合は提出日が新しい方へ付ける。
    # 古い方は reprocess で書類ごとの値を埋め直す。
    op.execute(
        """
        UPDATE human_capital_metrics AS hm
           SET doc_id = picked.doc_id
          FROM (
                SELECT DISTINCT ON (edinet_code, fiscal_year)
                       edinet_code, fiscal_year, doc_id
                  FROM financial_reports
                 ORDER BY edinet_code, fiscal_year,
                          submitted_date DESC, doc_id DESC
               ) AS picked
         WHERE hm.edinet_code = picked.edinet_code
           AND hm.fiscal_year = picked.fiscal_year
           AND hm.doc_id IS NULL
        """
    )
    op.execute("DELETE FROM human_capital_metrics WHERE doc_id IS NULL")
    op.alter_column(
        "human_capital_metrics",
        "doc_id",
        existing_type=sa.String(length=50),
        nullable=False,
    )

    inspector = sa.inspect(bind)
    if _has_unique(inspector, "human_capital_metrics", OLD_UNIQUE):
        op.drop_constraint(OLD_UNIQUE, "human_capital_metrics", type_="unique")
    inspector = sa.inspect(bind)
    if not _has_unique(inspector, "human_capital_metrics", NEW_UNIQUE):
        op.create_unique_constraint(
            NEW_UNIQUE,
            "human_capital_metrics",
            ["doc_id", "scope", "worker_type", "source_name"],
        )

    op.execute("DROP VIEW IF EXISTS vw_company_year_metrics")
    op.execute(_VIEW_ON_DOC_ID)


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS vw_company_year_metrics")
    op.execute(_VIEW_ON_COMPANY_YEAR)

    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if _has_unique(inspector, "human_capital_metrics", NEW_UNIQUE):
        op.drop_constraint(NEW_UNIQUE, "human_capital_metrics", type_="unique")
    inspector = sa.inspect(bind)
    if not _has_unique(inspector, "human_capital_metrics", OLD_UNIQUE):
        # ダウングレード前に同一 (会社, 年度, 次元) の重複を落とす
        op.execute(
            """
            DELETE FROM human_capital_metrics older
            USING human_capital_metrics newer
            WHERE older.id < newer.id
              AND older.edinet_code = newer.edinet_code
              AND older.fiscal_year = newer.fiscal_year
              AND older.scope = newer.scope
              AND older.worker_type = newer.worker_type
              AND older.source_name = newer.source_name
            """
        )
        op.create_unique_constraint(
            OLD_UNIQUE,
            "human_capital_metrics",
            ["edinet_code", "fiscal_year", "scope", "worker_type", "source_name"],
        )

    op.drop_constraint(
        "fk_human_capital_metrics_doc_id",
        "human_capital_metrics",
        type_="foreignkey",
    )
    op.drop_column("human_capital_metrics", "doc_id")
