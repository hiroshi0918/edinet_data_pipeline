"""原文チェックを通った歩みの文章を書類単位で残す."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0009_company_stories"
down_revision = "0008_story_and_market"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "company_stories" in inspector.get_table_names():
        return
    op.create_table(
        "company_stories",
        sa.Column("doc_id", sa.String(length=50), primary_key=True),
        sa.Column("edinet_code", sa.String(length=10), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_table("company_stories")
