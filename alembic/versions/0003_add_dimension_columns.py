"""人的資本指標に scope/worker_type 次元を追加し、LLM キャッシュ・evidence を拡張.

主な変更:
  1. human_capital_metrics に scope, worker_type を追加し UNIQUE 制約を再構成
  2. metric_evidence に element_id, scope, worker_type を追加
  3. llm_extraction_cache テーブル新設 (LLM 抽出結果の SHA256 キャッシュ)
  4. vw_company_year_metrics ビューを再構築 (scope/worker_type を選択可能に)
     ※ 単純 LEFT JOIN のため、(edinet_code, fiscal_year) ごとに人的資本側の
        次元数だけ行が増殖する。アプリ側で scope/worker_type を WHERE 句で絞る前提。
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0003_add_dimension_columns"
down_revision = "0002_add_raw_edinet_facts"
branch_labels = None
depends_on = None

OLD_HUMAN_METRICS_UNIQUE = "uq_human_capital_metrics_company_year_source"
NEW_HUMAN_METRICS_UNIQUE = (
    "uq_human_capital_metrics_company_year_scope_worker_source"
)
SCOPE_CHECK_NAME = "ck_human_capital_metrics_scope"
WORKER_TYPE_CHECK_NAME = "ck_human_capital_metrics_worker_type"


def _has_column(inspector: sa.Inspector, table: str, column: str) -> bool:
    return any(c["name"] == column for c in inspector.get_columns(table))


def _has_unique(inspector: sa.Inspector, table: str, name: str) -> bool:
    return any(c["name"] == name for c in inspector.get_unique_constraints(table))


def _has_check(inspector: sa.Inspector, table: str, name: str) -> bool:
    return any(c["name"] == name for c in inspector.get_check_constraints(table))


def _has_table(inspector: sa.Inspector, table: str) -> bool:
    return table in inspector.get_table_names()


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    # ---- human_capital_metrics: 次元カラム追加 ---------------------- #
    if not _has_column(inspector, "human_capital_metrics", "scope"):
        op.add_column(
            "human_capital_metrics",
            sa.Column(
                "scope", sa.String(length=40),
                nullable=False, server_default="reporting_company",
            ),
        )
    if not _has_column(inspector, "human_capital_metrics", "worker_type"):
        op.add_column(
            "human_capital_metrics",
            sa.Column(
                "worker_type", sa.String(length=40),
                nullable=False, server_default="all",
            ),
        )

    inspector = sa.inspect(bind)
    if not _has_check(inspector, "human_capital_metrics", SCOPE_CHECK_NAME):
        op.create_check_constraint(
            SCOPE_CHECK_NAME,
            "human_capital_metrics",
            "scope IN ('reporting_company', 'consolidated_subsidiary')",
        )
    if not _has_check(inspector, "human_capital_metrics", WORKER_TYPE_CHECK_NAME):
        op.create_check_constraint(
            WORKER_TYPE_CHECK_NAME,
            "human_capital_metrics",
            "worker_type IN ('all', 'regular', 'non_regular')",
        )

    # 旧 UNIQUE 制約を削除し、次元込みの新 UNIQUE 制約に置換
    inspector = sa.inspect(bind)
    if _has_unique(inspector, "human_capital_metrics", OLD_HUMAN_METRICS_UNIQUE):
        op.drop_constraint(
            OLD_HUMAN_METRICS_UNIQUE, "human_capital_metrics", type_="unique",
        )
    inspector = sa.inspect(bind)
    if not _has_unique(inspector, "human_capital_metrics", NEW_HUMAN_METRICS_UNIQUE):
        op.create_unique_constraint(
            NEW_HUMAN_METRICS_UNIQUE,
            "human_capital_metrics",
            ["edinet_code", "fiscal_year", "scope", "worker_type", "source_name"],
        )

    # ---- metric_evidence: element_id / scope / worker_type 追加 ----- #
    inspector = sa.inspect(bind)
    if not _has_column(inspector, "metric_evidence", "element_id"):
        op.add_column(
            "metric_evidence", sa.Column("element_id", sa.Text(), nullable=True),
        )
    if not _has_column(inspector, "metric_evidence", "scope"):
        op.add_column(
            "metric_evidence", sa.Column("scope", sa.String(length=40), nullable=True),
        )
    if not _has_column(inspector, "metric_evidence", "worker_type"):
        op.add_column(
            "metric_evidence", sa.Column("worker_type", sa.String(length=40), nullable=True),
        )

    # ---- LLM キャッシュテーブル新設 -------------------------------- #
    inspector = sa.inspect(bind)
    if not _has_table(inspector, "llm_extraction_cache"):
        op.create_table(
            "llm_extraction_cache",
            sa.Column("text_hash", sa.CHAR(length=64), primary_key=True),
            sa.Column("model", sa.String(length=80), nullable=False),
            sa.Column(
                "result", postgresql.JSONB(astext_type=sa.Text()), nullable=False,
            ),
            sa.Column(
                "created_at", sa.DateTime(),
                server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False,
            ),
        )

    # ---- vw_company_year_metrics 再構築 ----------------------------- #
    # PostgreSQL の CREATE OR REPLACE VIEW は既存カラムの順序変更/挿入を許さないため、
    # 新カラム (scope, worker_type) を中間位置に入れるには DROP → CREATE が必要。
    op.execute("DROP VIEW IF EXISTS vw_company_year_metrics")
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


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS vw_company_year_metrics")
    # 元のビューを復元
    op.execute(
        """
        CREATE OR REPLACE VIEW vw_company_year_metrics AS
        SELECT
            c.edinet_code, c.company_name, fr.fiscal_year, fr.doc_id,
            fr.submitted_date, fr.status, fr.sales, fr.operating_profit,
            fr.net_profit, fr.employee_count,
            hm.female_manager_ratio, hm.male_childcare_leave_ratio,
            hm.gender_wage_gap, hm.source_name
        FROM financial_reports fr
        JOIN companies c ON c.edinet_code = fr.edinet_code
        LEFT JOIN human_capital_metrics hm
          ON hm.edinet_code = fr.edinet_code
         AND hm.fiscal_year = fr.fiscal_year
        """
    )

    op.drop_table("llm_extraction_cache")

    op.drop_column("metric_evidence", "worker_type")
    op.drop_column("metric_evidence", "scope")
    op.drop_column("metric_evidence", "element_id")

    op.drop_constraint(
        NEW_HUMAN_METRICS_UNIQUE, "human_capital_metrics", type_="unique",
    )
    op.create_unique_constraint(
        OLD_HUMAN_METRICS_UNIQUE,
        "human_capital_metrics",
        ["edinet_code", "fiscal_year", "source_name"],
    )

    op.drop_constraint(WORKER_TYPE_CHECK_NAME, "human_capital_metrics", type_="check")
    op.drop_constraint(SCOPE_CHECK_NAME, "human_capital_metrics", type_="check")

    op.drop_column("human_capital_metrics", "worker_type")
    op.drop_column("human_capital_metrics", "scope")
