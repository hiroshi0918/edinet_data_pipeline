"""financial_reports に processing_started_at を追加し stale processing 復旧の土台を作る.

プロセスが kill / OOM / 電源断などで突然落ちると status='processing' のまま残る行が
発生する。本マイグレーションで claim 時刻を記録する processing_started_at 列を足し、
一定時間を超えた行を pending に戻すバッチ (db.reset_stale_processing) の判定根拠とする。

ビュー vw_company_year_metrics はカラムを明示列挙しており本列を参照しないため、
ビュー再構築は不要 (0003/0004 と異なり DROP→CREATE は走らせない)。
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0005_add_processing_started_at"
down_revision = "0004_add_industry_to_view"
branch_labels = None
depends_on = None


def _has_column(inspector: sa.Inspector, table: str, column: str) -> bool:
    """指定テーブルに列が存在するか (再実行時の冪等ガード。0003 と同じ方式)."""
    return any(c["name"] == column for c in inspector.get_columns(table))


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not _has_column(inspector, "financial_reports", "processing_started_at"):
        op.add_column(
            "financial_reports",
            sa.Column("processing_started_at", sa.DateTime(), nullable=True),
        )


def downgrade() -> None:
    op.drop_column("financial_reports", "processing_started_at")
