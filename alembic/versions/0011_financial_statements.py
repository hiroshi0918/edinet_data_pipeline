"""財務諸表 (BS・PL・CF) の主要項目を書類単位で残す.

raw_edinet_facts から抽出する。1 書類は連結・IFRS・個別のどれか1つの基準で埋め、
基準の違う値は混ぜない。金額の単位は円。
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0011_financial_statements"
down_revision = "0010_reported_per_index"
branch_labels = None
depends_on = None

AMOUNT_COLUMNS = (
    "total_assets",
    "current_assets",
    "cash_and_deposits",
    "trade_receivables",
    "inventories",
    "noncurrent_assets",
    "property_plant_equipment",
    "intangible_assets",
    "goodwill",
    "investment_securities",
    "total_liabilities",
    "current_liabilities",
    "noncurrent_liabilities",
    "interest_bearing_debt",
    "net_assets",
    "retained_earnings",
    "net_sales",
    "cost_of_sales",
    "gross_profit",
    "sga_expenses",
    "operating_income",
    "ordinary_income",
    "net_income",
    "operating_cf",
    "investing_cf",
    "financing_cf",
)


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "financial_statements" in inspector.get_table_names():
        return
    op.create_table(
        "financial_statements",
        sa.Column(
            "doc_id",
            sa.String(length=50),
            sa.ForeignKey("financial_reports.doc_id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("edinet_code", sa.String(length=10), nullable=False),
        sa.Column("fiscal_year", sa.Integer(), nullable=False),
        sa.Column("accounting_standard", sa.String(length=10), nullable=False),
        sa.Column("basis", sa.String(length=20), nullable=False),
        *[sa.Column(name, sa.BigInteger(), nullable=True) for name in AMOUNT_COLUMNS],
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "accounting_standard IN ('jgaap', 'ifrs')",
            name="ck_financial_statements_standard",
        ),
        sa.CheckConstraint(
            "basis IN ('consolidated', 'non_consolidated')",
            name="ck_financial_statements_basis",
        ),
    )
    op.create_index(
        "ix_financial_statements_company_year",
        "financial_statements",
        ["edinet_code", "fiscal_year"],
    )


def downgrade() -> None:
    op.drop_index("ix_financial_statements_company_year", table_name="financial_statements")
    op.drop_table("financial_statements")
