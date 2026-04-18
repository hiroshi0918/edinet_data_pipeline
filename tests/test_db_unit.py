"""db モジュールの DB-less 単体テスト (SQL インジェクション防止・プール境界値)."""

from __future__ import annotations

import pytest

from edinet_pipeline.db import DatabasePool, PipelineRepository


class DummyConnection:
    """PipelineRepository.__init__ を通すためだけの最小スタブ."""


def test_replace_child_records_rejects_disallowed_table_name() -> None:
    """許可リスト外のテーブル名は ValueError で弾かれ、カーソル操作に入らないこと."""
    repository = PipelineRepository(DummyConnection())

    with pytest.raises(ValueError, match="Disallowed child table"):
        repository._replace_child_records(
            doc_id="S100AAAA",
            table="DROP TABLE users; --",
            columns=["doc_id"],
            rows=[("S100AAAA",)],
        )


def test_database_pool_rejects_invalid_sizes() -> None:
    """min > max / max < 1 / min < 0 の矛盾した設定は ValueError で拒否されること."""
    with pytest.raises(ValueError, match="Invalid pool size"):
        DatabasePool("postgresql://dummy", min_size=5, max_size=1)

    with pytest.raises(ValueError, match="Invalid pool size"):
        DatabasePool("postgresql://dummy", min_size=0, max_size=0)

    with pytest.raises(ValueError, match="Invalid pool size"):
        DatabasePool("postgresql://dummy", min_size=-1, max_size=2)
