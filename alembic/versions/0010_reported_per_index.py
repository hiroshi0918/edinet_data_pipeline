"""会社シートが当期の株価収益率を引くときの部分索引.

raw_edinet_facts は書類あたり千行を超える。doc_id だけの索引だと、
同業他社の株価収益率を探すときに書類内の残りの行まで読む。
当期の株価収益率の2項目だけを索引に残す。
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0010_reported_per_index"
down_revision = "0009_company_stories"
branch_labels = None
depends_on = None

INDEX_NAME = "ix_raw_edinet_facts_reported_per"


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if INDEX_NAME in {index["name"] for index in inspector.get_indexes("raw_edinet_facts")}:
        return

    # CONCURRENTLY はトランザクションの外でしか実行できない。
    with op.get_context().autocommit_block():
        op.execute(
            sa.text(
                """
                CREATE INDEX CONCURRENTLY ix_raw_edinet_facts_reported_per
                    ON raw_edinet_facts (doc_id, item_name)
                    INCLUDE (raw_value)
                    WHERE relative_year = '当期'
                      AND item_name IN (
                        '株価収益率（IFRS）、経営指標等',
                        '株価収益率、経営指標等'
                      )
                """
            )
        )


def downgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute(sa.text(f"DROP INDEX CONCURRENTLY IF EXISTS {INDEX_NAME}"))
