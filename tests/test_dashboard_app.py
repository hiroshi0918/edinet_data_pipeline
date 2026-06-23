"""dashboard/app.py のスモークテスト.

DuckDB パス解決ロジックは datasource.py へ移設したため、その検証は
test_dashboard_datasource.py (TestLocalDuckdbPath) に移っている。ここでは
app.py が副作用なく import でき、ページレジストリが健全であることを確認する。
"""

from __future__ import annotations

from edinet_pipeline.dashboard import app

_EXPECTED_PAGES = {
    "企業を調べる",
    "業種で比べる",
    "人的資本トップ/ボトム企業",
    "規模×人的資本",
    "企業スポットライト",
}


def test_pages_registry_has_expected_views() -> None:
    assert set(app._PAGES) == _EXPECTED_PAGES
    assert all(callable(render) for render in app._PAGES.values())
