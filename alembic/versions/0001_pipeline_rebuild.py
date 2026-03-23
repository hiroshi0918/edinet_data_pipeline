from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0001_pipeline_rebuild"
down_revision = None
branch_labels = None
depends_on = None

STATUS_CHECK_NAME = "ck_financial_reports_status"
HUMAN_METRICS_UNIQUE_NAME = "uq_human_capital_metrics_company_year_source"


def _has_table(inspector: sa.Inspector, table_name: str) -> bool:
    return table_name in inspector.get_table_names()


def _has_column(inspector: sa.Inspector, table_name: str, column_name: str) -> bool:
    return any(column["name"] == column_name for column in inspector.get_columns(table_name))


def _has_check_constraint(inspector: sa.Inspector, table_name: str, constraint_name: str) -> bool:
    return any(
        constraint["name"] == constraint_name
        for constraint in inspector.get_check_constraints(table_name)
    )


def _has_unique_constraint(inspector: sa.Inspector, table_name: str, constraint_name: str) -> bool:
    return any(
        constraint["name"] == constraint_name
        for constraint in inspector.get_unique_constraints(table_name)
    )


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not _has_table(inspector, "companies"):
        op.create_table(
            "companies",
            sa.Column("edinet_code", sa.String(length=10), primary_key=True),
            sa.Column("company_name", sa.String(length=255), nullable=False),
            sa.Column("industry", sa.String(length=100), nullable=True),
            sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP")),
        )

    if not _has_table(inspector, "financial_reports"):
        op.create_table(
            "financial_reports",
            sa.Column("doc_id", sa.String(length=50), primary_key=True),
            sa.Column("edinet_code", sa.String(length=10), sa.ForeignKey("companies.edinet_code")),
            sa.Column("fiscal_year", sa.Integer(), nullable=False),
            sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
            sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("last_error", sa.Text(), nullable=True),
            sa.Column("processed_at", sa.DateTime(), nullable=True),
            sa.Column("sales", sa.BigInteger(), nullable=True),
            sa.Column("operating_profit", sa.BigInteger(), nullable=True),
            sa.Column("net_profit", sa.BigInteger(), nullable=True),
            sa.Column("employee_count", sa.Integer(), nullable=True),
            sa.Column("submitted_date", sa.Date(), nullable=False),
            sa.Column(
                "source_metadata",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=False,
                server_default=sa.text("'{}'::jsonb"),
            ),
        )
        op.create_check_constraint(
            STATUS_CHECK_NAME,
            "financial_reports",
            "status IN ('pending', 'processing', 'processed', 'skipped', 'failed')",
        )
    else:
        if not _has_column(inspector, "financial_reports", "status"):
            op.add_column(
                "financial_reports",
                sa.Column("status", sa.String(length=20), nullable=True, server_default="pending"),
            )
        if not _has_column(inspector, "financial_reports", "retry_count"):
            op.add_column(
                "financial_reports",
                sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
            )
        if not _has_column(inspector, "financial_reports", "last_error"):
            op.add_column("financial_reports", sa.Column("last_error", sa.Text(), nullable=True))
        if not _has_column(inspector, "financial_reports", "processed_at"):
            op.add_column(
                "financial_reports", sa.Column("processed_at", sa.DateTime(), nullable=True)
            )
        if not _has_column(inspector, "financial_reports", "source_metadata"):
            op.add_column(
                "financial_reports",
                sa.Column(
                    "source_metadata",
                    postgresql.JSONB(astext_type=sa.Text()),
                    nullable=False,
                    server_default=sa.text("'{}'::jsonb"),
                ),
            )

        inspector = sa.inspect(bind)
        if _has_column(inspector, "financial_reports", "processed"):
            op.execute(
                """
                UPDATE financial_reports
                SET status = CASE
                    WHEN processed IS TRUE THEN 'processed'
                    WHEN COALESCE(csv_available, TRUE) IS FALSE THEN 'skipped'
                    ELSE 'pending'
                END
                """
            )
            op.execute(
                """
                UPDATE financial_reports
                SET processed_at = CASE
                    WHEN processed IS TRUE THEN CURRENT_TIMESTAMP
                    ELSE processed_at
                END
                """
            )

        op.execute("UPDATE financial_reports SET status = COALESCE(status, 'pending')")
        op.execute("UPDATE financial_reports SET retry_count = COALESCE(retry_count, 0)")
        op.execute(
            """
            UPDATE financial_reports
            SET source_metadata = COALESCE(source_metadata, '{}'::jsonb)
            """
        )

        if not _has_check_constraint(sa.inspect(bind), "financial_reports", STATUS_CHECK_NAME):
            op.create_check_constraint(
                STATUS_CHECK_NAME,
                "financial_reports",
                "status IN ('pending', 'processing', 'processed', 'skipped', 'failed')",
            )

        inspector = sa.inspect(bind)
        if _has_column(inspector, "financial_reports", "processed"):
            op.drop_column("financial_reports", "processed")
        if _has_column(inspector, "financial_reports", "csv_available"):
            op.drop_column("financial_reports", "csv_available")

        op.alter_column(
            "financial_reports", "status", existing_type=sa.String(length=20), nullable=False
        )
        op.alter_column(
            "financial_reports",
            "source_metadata",
            existing_type=postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        )

    inspector = sa.inspect(bind)
    if not _has_table(inspector, "human_capital_metrics"):
        op.create_table(
            "human_capital_metrics",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("edinet_code", sa.String(length=10), sa.ForeignKey("companies.edinet_code")),
            sa.Column("fiscal_year", sa.Integer(), nullable=False),
            sa.Column("female_manager_ratio", sa.Numeric(5, 2), nullable=True),
            sa.Column("male_childcare_leave_ratio", sa.Numeric(5, 2), nullable=True),
            sa.Column("gender_wage_gap", sa.Numeric(5, 2), nullable=True),
            sa.Column("engagement_score", sa.Numeric(5, 2), nullable=True),
            sa.Column("source_name", sa.String(length=100), nullable=False),
        )
    else:
        if not _has_column(inspector, "human_capital_metrics", "source_name"):
            op.add_column(
                "human_capital_metrics",
                sa.Column(
                    "source_name",
                    sa.String(length=100),
                    nullable=False,
                    server_default="EDINET_CSV",
                ),
            )

    op.execute(
        """
        DELETE FROM human_capital_metrics older
        USING human_capital_metrics newer
        WHERE older.id < newer.id
          AND older.edinet_code = newer.edinet_code
          AND older.fiscal_year = newer.fiscal_year
          AND older.source_name = newer.source_name
        """
    )

    if not _has_unique_constraint(
        sa.inspect(bind), "human_capital_metrics", HUMAN_METRICS_UNIQUE_NAME
    ):
        op.create_unique_constraint(
            HUMAN_METRICS_UNIQUE_NAME,
            "human_capital_metrics",
            ["edinet_code", "fiscal_year", "source_name"],
        )

    inspector = sa.inspect(bind)
    if not _has_table(inspector, "metric_evidence"):
        op.create_table(
            "metric_evidence",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column(
                "doc_id",
                sa.String(length=50),
                sa.ForeignKey("financial_reports.doc_id", ondelete="CASCADE"),
            ),
            sa.Column("metric_name", sa.String(length=100), nullable=False),
            sa.Column("item_name", sa.Text(), nullable=False),
            sa.Column("raw_value", sa.Text(), nullable=False),
            sa.Column("relative_year", sa.String(length=100), nullable=True),
            sa.Column("source_file", sa.Text(), nullable=False),
            sa.Column("matched_by", sa.String(length=50), nullable=False),
        )

    op.execute(
        """
        CREATE OR REPLACE VIEW vw_company_year_metrics AS
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
            hm.female_manager_ratio,
            hm.male_childcare_leave_ratio,
            hm.gender_wage_gap,
            hm.source_name
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
    op.drop_table("metric_evidence")
    op.drop_constraint(HUMAN_METRICS_UNIQUE_NAME, "human_capital_metrics", type_="unique")
    op.drop_table("human_capital_metrics")
    op.drop_constraint(STATUS_CHECK_NAME, "financial_reports", type_="check")
    op.drop_table("financial_reports")
    op.drop_table("companies")
