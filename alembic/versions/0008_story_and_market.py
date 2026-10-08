"""歩みと期待の点に使う列を足す.

証券コードと決算月は EDINET コード集約一覧から埋める。
発行済株式数は有報の経営指標、株価は equity_month_closes に後から入れる。
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0008_story_and_market"
down_revision = "0007_human_metrics_by_doc_id"
branch_labels = None
depends_on = None


def _has_column(inspector: sa.Inspector, table: str, column: str) -> bool:
    return any(col["name"] == column for col in inspector.get_columns(table))


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not _has_column(inspector, "companies", "securities_code"):
        op.add_column("companies", sa.Column("securities_code", sa.String(length=8), nullable=True))
    if not _has_column(inspector, "companies", "fiscal_month"):
        op.add_column("companies", sa.Column("fiscal_month", sa.Integer(), nullable=True))
    if not _has_column(inspector, "financial_reports", "shares_outstanding"):
        op.add_column(
            "financial_reports",
            sa.Column("shares_outstanding", sa.BigInteger(), nullable=True),
        )

    inspector = sa.inspect(bind)
    if "equity_month_closes" not in inspector.get_table_names():
        op.create_table(
            "equity_month_closes",
            sa.Column("securities_code", sa.String(length=8), nullable=False),
            sa.Column("fiscal_year", sa.Integer(), nullable=False),
            sa.Column("month", sa.Integer(), nullable=False),
            sa.Column("close_price", sa.Numeric(18, 4), nullable=False),
            sa.PrimaryKeyConstraint(
                "securities_code", "fiscal_year", "month", name="pk_equity_month_closes"
            ),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "equity_month_closes" in inspector.get_table_names():
        op.drop_table("equity_month_closes")
    if _has_column(inspector, "financial_reports", "shares_outstanding"):
        op.drop_column("financial_reports", "shares_outstanding")
    if _has_column(inspector, "companies", "fiscal_month"):
        op.drop_column("companies", "fiscal_month")
    if _has_column(inspector, "companies", "securities_code"):
        op.drop_column("companies", "securities_code")
