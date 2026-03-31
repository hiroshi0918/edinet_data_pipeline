from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0002_add_raw_edinet_facts"
down_revision = "0001_pipeline_rebuild"
branch_labels = None
depends_on = None


def _has_table(inspector: sa.Inspector, table_name: str) -> bool:
    return table_name in inspector.get_table_names()


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if _has_table(inspector, "raw_edinet_facts"):
        return

    op.create_table(
        "raw_edinet_facts",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "doc_id",
            sa.String(length=50),
            sa.ForeignKey("financial_reports.doc_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("source_file", sa.Text(), nullable=False),
        sa.Column("row_number", sa.Integer(), nullable=False),
        sa.Column("element_id", sa.Text(), nullable=True),
        sa.Column("item_name", sa.Text(), nullable=True),
        sa.Column("context_id", sa.Text(), nullable=True),
        sa.Column("relative_year", sa.String(length=100), nullable=True),
        sa.Column("consolidation_type", sa.String(length=20), nullable=True),
        sa.Column("period_type", sa.String(length=20), nullable=True),
        sa.Column("unit_id", sa.String(length=100), nullable=True),
        sa.Column("unit_label", sa.String(length=100), nullable=True),
        sa.Column("raw_value", sa.Text(), nullable=True),
        sa.UniqueConstraint(
            "doc_id",
            "source_file",
            "row_number",
            name="uq_raw_edinet_facts_doc_file_row",
        ),
    )
    op.create_index(
        "ix_raw_edinet_facts_doc_id",
        "raw_edinet_facts",
        ["doc_id"],
        unique=False,
    )
    op.create_index(
        "ix_raw_edinet_facts_lookup",
        "raw_edinet_facts",
        ["element_id", "relative_year", "consolidation_type", "period_type"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_raw_edinet_facts_lookup", table_name="raw_edinet_facts")
    op.drop_index("ix_raw_edinet_facts_doc_id", table_name="raw_edinet_facts")
    op.drop_table("raw_edinet_facts")
