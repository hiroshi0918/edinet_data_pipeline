"""logging_utils のテスト — 既存ハンドラの有無に関わらずレベルが反映されること."""

from __future__ import annotations

import logging

import pytest

from edinet_pipeline.logging_utils import configure_logging


@pytest.fixture(autouse=True)
def restore_root_logger():
    """各テストでルートロガーの状態を汚染しないよう、ハンドラとレベルを退避."""
    root = logging.getLogger()
    saved_handlers = list(root.handlers)
    saved_level = root.level
    try:
        yield
    finally:
        root.handlers = saved_handlers
        root.setLevel(saved_level)


def test_configure_logging_sets_root_level_when_already_initialized() -> None:
    """親プロセスが既に basicConfig 済みでも force=True により DEBUG が反映されること."""
    root = logging.getLogger()
    root.handlers = [logging.StreamHandler()]  # 事前ハンドラ済み状態を模擬
    root.setLevel(logging.WARNING)

    configure_logging("DEBUG")

    assert root.level == logging.DEBUG


def test_configure_logging_falls_back_to_info_for_unknown_level() -> None:
    """未知レベル名は INFO にフォールバックする (getattr の default 経由)."""
    configure_logging("NOT_A_LEVEL")

    assert logging.getLogger().level == logging.INFO
