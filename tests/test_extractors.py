"""extractors モジュールのテスト — CSV/ZIP パース・数値変換・人的資本テキスト抽出の検証."""

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
    """テスト用の ZIP アーカイブをメモリ上に構築する.

    entries の値は以下の型を受け付ける:
      - list[dict]:    → DataFrame に変換後、TSV (UTF-16LE) に変換
      - pd.DataFrame:  → TSV (UTF-16LE) に変換
      - str:           → UTF-8 バイト列に変換
      - bytes:         → そのまま書き込み
    """
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


# ------------------------------------------------------------------ #
#  extract_numeric: 全角・カンマ・括弧付き数値のパース
# ------------------------------------------------------------------ #


def test_extract_numeric_handles_commas_full_width_and_parentheses() -> None:
    """全角数字 / カンマ区切り / 括弧(負数) が正しく変換されること."""
    assert extract_numeric("１,２３４") == 1234.0
    assert extract_numeric("(1,234)") == -1234.0
    assert extract_numeric("営業利益 98.7") == 98.7


def test_extract_numeric_returns_none_for_missing_markers() -> None:
    """空文字列・ハイフン・None は欠損値 (None) として返すこと."""
    assert extract_numeric("") is None
    assert extract_numeric("-") is None
    assert extract_numeric(None) is None


# ------------------------------------------------------------------ #
#  extract_human_capital_from_text: 自由記述テキストからの指標抽出
# ------------------------------------------------------------------ #


def test_extract_human_capital_from_text_uses_text_fallback() -> None:
    """補足文章中のキーワードから人的資本指標を抽出できること."""
    text = """
    管理職に占める女性労働者の割合 12.5
    男性労働者の育児休業取得率 80.0
    労働者の男女の賃金の差異(%) 75.5 80.1 90.2
    """
    metrics = extract_human_capital_from_text(text)
    assert metrics["female_manager_ratio"] == 12.5
    assert metrics["male_childcare_leave_ratio"] == 80.0
    assert metrics["gender_wage_gap"] == 75.5


def test_extract_human_capital_from_text_respects_max_ratio_override() -> None:
    """max_ratio で異常値判定の閾値を絞れること (閾値以上の値は後続トークンにスキップ)."""
    text = (
        "管理職に占める女性労働者の割合 95.0 50.0 "
        "男性労働者の育児休業取得率 80.0 "
        "労働者の男女の賃金の差異(%) 75.5"
    )
    # 既定 (200) では最初に現れる 95.0 を採用
    default_metrics = extract_human_capital_from_text(text)
    assert default_metrics["female_manager_ratio"] == 95.0

    # 閾値を 90 に絞ると 95.0 は除外され、次トークンの 50.0 が採用される
    tight_metrics = extract_human_capital_from_text(text, max_ratio=90.0)
    assert tight_metrics["female_manager_ratio"] == 50.0


# ------------------------------------------------------------------ #
#  FilingFilters: 書類種別フィルタ (有価証券報告書のみ通す)
# ------------------------------------------------------------------ #


def test_filing_filters_accept_only_target_annual_reports() -> None:
    """有価証券報告書 (ordinanceCode=010, formCode=030000) のみ True を返すこと."""
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


# ------------------------------------------------------------------ #
#  parse_document_zip: ZIP → ParsedDocument の統合テスト
# ------------------------------------------------------------------ #


def test_parse_document_zip_skips_irrelevant_files_and_invalid_columns() -> None:
    """XBRL_TO_CSV/jpcrp_*.csv のみ処理対象とし、不正カラムのファイルを無視すること."""
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
    """前期データは無視し、項目名マッチとテキストフォールバックの両方で証跡を記録すること."""
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

    # 前期の売上高は取り込まれない
    assert parsed.financial_metrics["sales"] is None
    assert parsed.human_metrics == {
        "female_manager_ratio": 12.5,
        "male_childcare_leave_ratio": 81.0,
        "gender_wage_gap": 75.5,
    }
    # 抽出方法が item_name_match と text_fallback の 2 種類記録される
    assert {(record.metric_name, record.matched_by) for record in parsed.evidence} == {
        ("male_childcare_leave_ratio", "item_name_match"),
        ("female_manager_ratio", "text_fallback"),
        ("gender_wage_gap", "text_fallback"),
    }


def test_parse_document_zip_collects_raw_facts_with_all_available_columns() -> None:
    """元CSV行を raw_facts として保持し、9列の値を欠損込みで保存すること."""
    zip_bytes = build_zip(
        {
            "XBRL_TO_CSV/jpcrp_full.csv": [
                {
                    "要素ID": "jpcrp_cor:NetSales",
                    "項目名": "売上高、経営指標等",
                    "コンテキストID": "CurrentYearDuration",
                    "相対年度": "当期",
                    "連結・個別": "連結",
                    "期間・時点": "期間",
                    "ユニットID": "JPY",
                    "単位": "円",
                    "値": "1,234",
                }
            ],
        }
    )

    parsed = parse_document_zip(zip_bytes)

    assert len(parsed.raw_facts) == 1
    raw_fact = parsed.raw_facts[0]
    assert raw_fact.source_file == "XBRL_TO_CSV/jpcrp_full.csv"
    assert raw_fact.row_number == 1
    assert raw_fact.element_id == "jpcrp_cor:NetSales"
    assert raw_fact.item_name == "売上高、経営指標等"
    assert raw_fact.context_id == "CurrentYearDuration"
    assert raw_fact.relative_year == "当期"
    assert raw_fact.consolidation_type == "連結"
    assert raw_fact.period_type == "期間"
    assert raw_fact.unit_id == "JPY"
    assert raw_fact.unit_label == "円"
    assert raw_fact.raw_value == "1,234"


def test_parse_document_zip_raises_when_no_candidate_csv_files_exist() -> None:
    """XBRL_TO_CSV/ 配下に対象 CSV が無い場合 ValueError を送出すること."""
    zip_bytes = build_zip(
        {
            "reports/annual.csv": [
                {"項目名": "売上高", "値": "1,234", "相対年度": "当期"},
            ]
        }
    )

    with pytest.raises(ValueError, match="No candidate CSV files found in ZIP"):
        parse_document_zip(zip_bytes)
