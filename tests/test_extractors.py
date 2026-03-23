from __future__ import annotations

from edinet_pipeline.extractors import extract_human_capital_from_text, extract_numeric
from edinet_pipeline.models import FilingFilters


def test_extract_numeric_handles_commas_full_width_and_parentheses() -> None:
    assert extract_numeric("１,２３４") == 1234.0
    assert extract_numeric("(1,234)") == -1234.0
    assert extract_numeric("営業利益 98.7") == 98.7


def test_extract_numeric_returns_none_for_missing_markers() -> None:
    assert extract_numeric("") is None
    assert extract_numeric("-") is None
    assert extract_numeric(None) is None


def test_extract_human_capital_from_text_uses_text_fallback() -> None:
    text = """
    管理職に占める女性労働者の割合 12.5
    男性労働者の育児休業取得率 80.0
    労働者の男女の賃金の差異(%) 75.5 80.1 90.2
    """
    metrics = extract_human_capital_from_text(text)
    assert metrics["female_manager_ratio"] == 12.5
    assert metrics["male_childcare_leave_ratio"] == 80.0
    assert metrics["gender_wage_gap"] == 75.5


def test_filing_filters_accept_only_target_annual_reports() -> None:
    filters = FilingFilters()
    target_document = {
        "docDescription": "有価証券報告書－第10期(2023/04/01－2024/03/31)",
        "ordinanceCode": "010",
        "formCode": "030000",
    }
    non_target_document = {
        "docDescription": "四半期報告書－第1四半期",
        "ordinanceCode": "010",
        "formCode": "043000",
    }

    assert filters.matches(target_document) is True
    assert filters.matches(non_target_document) is False
