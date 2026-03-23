from __future__ import annotations

import io
import zipfile

import pandas as pd
import pytest

from edinet_pipeline.extractors import (
    extract_human_capital_from_text,
    extract_numeric,
    parse_document_zip,
)
from edinet_pipeline.models import FilingFilters


def build_zip(entries: dict[str, object]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for path, payload in entries.items():
            if isinstance(payload, list):
                frame = pd.DataFrame(payload)
                content = frame.to_csv(index=False, sep="\t").encode("utf-16le")
            elif isinstance(payload, pd.DataFrame):
                content = payload.to_csv(index=False, sep="\t").encode("utf-16le")
            elif isinstance(payload, str):
                content = payload.encode("utf-8")
            else:
                content = payload
            archive.writestr(path, content)
    return buffer.getvalue()


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


def test_parse_document_zip_skips_irrelevant_files_and_invalid_columns() -> None:
    zip_bytes = build_zip(
        {
            "notes/readme.txt": "ignore me",
            "XBRL_TO_CSV/invalid.csv": pd.DataFrame([{"foo": "売上高", "bar": "100"}]),
            "XBRL_TO_CSV/jpcrp_valid.csv": [
                {"項目名": "売上高", "値": "1,234", "相対年度": "当期"},
                {"項目名": "従業員数", "値": "50", "相対年度": "提出者"},
            ],
        }
    )

    parsed = parse_document_zip(zip_bytes)

    assert parsed.financial_metrics["sales"] == 1234
    assert parsed.financial_metrics["employee_count"] == 50
    assert [record.metric_name for record in parsed.evidence] == ["sales", "employee_count"]


def test_parse_document_zip_ignores_non_current_rows_and_records_both_evidence_types() -> None:
    zip_bytes = build_zip(
        {
            "XBRL_TO_CSV/jpcrp_metrics.csv": [
                {"項目名": "売上高", "値": "1,000", "相対年度": "前期"},
                {"項目名": "男性労働者の育児休業取得率", "値": "81.0", "相対年度": "提出者"},
                {
                    "項目名": "補足文章",
                    "値": "管理職に占める女性労働者の割合 12.5 労働者の男女の賃金の差異(%) 75.5",
                    "相対年度": "提出者",
                },
            ]
        }
    )

    parsed = parse_document_zip(zip_bytes)

    assert parsed.financial_metrics["sales"] is None
    assert parsed.human_metrics == {
        "female_manager_ratio": 12.5,
        "male_childcare_leave_ratio": 81.0,
        "gender_wage_gap": 75.5,
    }
    assert {(record.metric_name, record.matched_by) for record in parsed.evidence} == {
        ("male_childcare_leave_ratio", "item_name_match"),
        ("female_manager_ratio", "text_fallback"),
        ("gender_wage_gap", "text_fallback"),
    }


def test_parse_document_zip_raises_when_no_candidate_csv_files_exist() -> None:
    zip_bytes = build_zip(
        {
            "reports/annual.csv": [
                {"項目名": "売上高", "値": "1,234", "相対年度": "当期"},
            ]
        }
    )

    with pytest.raises(ValueError, match="No candidate CSV files found in ZIP"):
        parse_document_zip(zip_bytes)
