"""extractors モジュールのテスト — 3層抽出戦略 (要素ID / 項目名 / テキスト) の検証."""

from __future__ import annotations

import io
import zipfile

import pandas as pd
import pytest

from edinet_pipeline.extractors import (
    classify_element_id,
    convert_to_percentage,
    extract_human_capital_from_text,
    extract_numeric,
    is_text_block_fact,
    merge_llm_records,
    parse_document_zip,
    parse_from_raw_facts,
)
from edinet_pipeline.models import (
    SCOPE_CONSOLIDATED_SUBSIDIARY,
    SCOPE_REPORTING_COMPANY,
    WORKER_TYPE_ALL,
    WORKER_TYPE_NON_REGULAR,
    WORKER_TYPE_REGULAR,
    FilingFilters,
    HumanMetricRecord,
)


def build_zip(entries: dict[str, object]) -> bytes:
    """テスト用の ZIP アーカイブをメモリ上に構築する."""
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


def _find_record(
    records: list[HumanMetricRecord], scope: str, worker_type: str,
) -> HumanMetricRecord | None:
    """テスト補助: (scope, worker_type) で HumanMetricRecord を検索."""
    for r in records:
        if r.scope == scope and r.worker_type == worker_type:
            return r
    return None


# ------------------------------------------------------------------ #
#  extract_numeric: 全角・カンマ・括弧付き数値のパース
# ------------------------------------------------------------------ #


def test_extract_numeric_handles_commas_full_width_and_parentheses() -> None:
    assert extract_numeric("１,２３４") == 1234.0
    assert extract_numeric("(1,234)") == -1234.0
    assert extract_numeric("営業利益 98.7") == 98.7


def test_extract_numeric_returns_none_for_missing_markers() -> None:
    assert extract_numeric("") is None
    assert extract_numeric("-") is None
    assert extract_numeric(None) is None
    assert extract_numeric("－") is None  # XBRLの全角ダッシュ


# ------------------------------------------------------------------ #
#  convert_to_percentage: pure 単位の ％ 換算
# ------------------------------------------------------------------ #


def test_convert_to_percentage_scales_pure_unit() -> None:
    """unit_id='pure' の値は ×100 されて % になる (XBRL の慣例)."""
    assert convert_to_percentage(0.024, "pure") == pytest.approx(2.4)
    assert convert_to_percentage(0.585, "pure") == pytest.approx(58.5)


def test_convert_to_percentage_passes_through_other_units() -> None:
    """pure 以外の単位 (JPY, %, None) はそのまま返す."""
    assert convert_to_percentage(1234.0, "JPY") == 1234.0
    assert convert_to_percentage(2.4, "%") == 2.4
    assert convert_to_percentage(2.4, None) == 2.4


# ------------------------------------------------------------------ #
#  classify_element_id: 要素ID の分類
# ------------------------------------------------------------------ #


def test_classify_element_id_recognizes_female_manager_ratio() -> None:
    """女性管理職比率の要素IDを正しく分類できる."""
    eid = "jpcrp_cor:RatioOfFemaleEmployeesInManagerialPositionsMetricsOfReportingCompany"
    assert classify_element_id(eid) == (
        "female_manager_ratio", SCOPE_REPORTING_COMPANY, WORKER_TYPE_ALL,
    )


def test_classify_element_id_recognizes_worker_type_prefix() -> None:
    """賃金差異の正規/非正規 worker_type が要素IDから判定される."""
    regular = (
        "jpcrp_cor:RegularEmployeesDifferencesInWagesBetweenMaleAndFemaleEmployees"
        "MetricsOfReportingCompany"
    )
    non_regular = (
        "jpcrp_cor:NonRegularEmployeesDifferencesInWagesBetweenMaleAndFemaleEmployees"
        "MetricsOfReportingCompany"
    )
    assert classify_element_id(regular) == (
        "gender_wage_gap", SCOPE_REPORTING_COMPANY, WORKER_TYPE_REGULAR,
    )
    assert classify_element_id(non_regular) == (
        "gender_wage_gap", SCOPE_REPORTING_COMPANY, WORKER_TYPE_NON_REGULAR,
    )


def test_classify_element_id_recognizes_consolidated_subsidiary_scope() -> None:
    """連結子会社サフィックスが scope を切り替える."""
    eid = (
        "jpcrp_cor:AllEmployeesRatioOfMaleEmployeesTakingChildcareLeave"
        "MetricsOfConsolidatedSubsidiaries"
    )
    assert classify_element_id(eid) == (
        "male_childcare_leave_ratio", SCOPE_CONSOLIDATED_SUBSIDIARY, WORKER_TYPE_ALL,
    )


def test_classify_element_id_returns_none_for_unrelated() -> None:
    assert classify_element_id(None) is None
    assert classify_element_id("jpcrp_cor:NetSales") is None
    assert classify_element_id("") is None


# ------------------------------------------------------------------ #
#  extract_human_capital_from_text: 自由記述テキストからの指標抽出
# ------------------------------------------------------------------ #


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


def test_extract_human_capital_from_text_avoids_f_equals_m_bug() -> None:
    """F=M同値バグ防止: 異なる指標が同じ数値を取らないこと.

    旧実装は「ラベル群+数値群」レイアウトで全ラベルが先頭の数値にマッチして
    F=M=W=5.2 という不正な結果を返していた。新実装は走査窓を他ラベル直前で
    打ち切るため、誤った同一値を返さない (取れない場合は None を返す).
    """
    text = (
        "管理職に占める女性労働者の割合(%) "
        "男性労働者の育児休業取得率(%) "
        "労働者の男女の賃金の差異(%) "
        "5.2 36.4 68.2"
    )
    metrics = extract_human_capital_from_text(text)
    f_val = metrics.get("female_manager_ratio")
    m_val = metrics.get("male_childcare_leave_ratio")
    w_val = metrics.get("gender_wage_gap")

    # 旧バグ: F=M=W=5.2 になっていた → このアサートで再発を防ぐ
    if f_val is not None and m_val is not None:
        assert f_val != m_val, "F=M same-value bug regressed"
    if f_val is not None and w_val is not None:
        assert f_val != w_val, "F=W same-value bug regressed"
    if m_val is not None and w_val is not None:
        assert m_val != w_val, "M=W same-value bug regressed"


def test_extract_human_capital_from_text_respects_max_ratio_override() -> None:
    text = (
        "管理職に占める女性労働者の割合 95.0 50.0 "
        "男性労働者の育児休業取得率 80.0 "
        "労働者の男女の賃金の差異(%) 75.5"
    )
    default_metrics = extract_human_capital_from_text(text)
    assert default_metrics["female_manager_ratio"] == 95.0

    tight_metrics = extract_human_capital_from_text(text, max_ratio=90.0)
    assert tight_metrics["female_manager_ratio"] == 50.0


# ------------------------------------------------------------------ #
#  FilingFilters
# ------------------------------------------------------------------ #


def test_filing_filters_accept_only_target_annual_reports() -> None:
    filters = FilingFilters()
    target = {
        "docDescription": "有価証券報告書－第10期(2023/04/01－2024/03/31)",
        "ordinanceCode": "010", "formCode": "030000",
    }
    non_target = {
        "docDescription": "四半期報告書－第1四半期",
        "ordinanceCode": "010", "formCode": "043000",
    }
    assert filters.matches(target) is True
    assert filters.matches(non_target) is False


# ------------------------------------------------------------------ #
#  parse_document_zip: 統合テスト
# ------------------------------------------------------------------ #


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
    assert [r.metric_name for r in parsed.evidence] == ["sales", "employee_count"]


def test_is_text_block_fact_detects_element_suffix_and_item_marker() -> None:
    """要素ID末尾 TextBlock / 項目名の『テキストブロック』を検出する."""
    assert is_text_block_fact(
        "jpcrp_cor:RevenuesFromExternalCustomersInformationForEachRegionTextBlock",
        "売上高、地域ごとの情報 [テキストブロック]",
    )
    # element_id が欠損していても項目名で検出できる (保険)
    assert is_text_block_fact(None, "売上高、地域ごとの情報 [テキストブロック]")
    # 通常の数値ファクトは誤検出しない
    assert not is_text_block_fact(
        "jpcrp_cor:NetSalesSummaryOfBusinessResults", "売上高、経営指標等"
    )


def test_parse_document_zip_financial_skips_text_block_false_match() -> None:
    """財務指標がテキストブロック行に誤マッチして注釈番号を拾わないこと.

    銀行・保険の有報では「売上高、地域ごとの情報 [テキストブロック]」という
    自由記述行が存在し、その本文が "(1) 経常収益…" で始まる。項目名に「売上高」
    が部分一致するため、修正前は extract_numeric が "(1)" の 1 を sales として
    採用していた (sales=1 のゴミ)。テキストブロックを除外すれば sales は None。
    """
    zip_bytes = build_zip(
        {
            "XBRL_TO_CSV/jpcrp_bank.csv": [
                {
                    "要素ID": (
                        "jpcrp_cor:RevenuesFromExternalCustomers"
                        "InformationForEachRegionTextBlock"
                    ),
                    "項目名": "売上高、地域ごとの情報 [テキストブロック]",
                    "相対年度": "当期",
                    "値": (
                        "(1) 経常収益本邦の外部顧客に対する経常収益に区分した金額が"
                        "連結損益計算書の経常収益の90%を超えるため、記載を省略しております。"
                    ),
                },
            ],
        }
    )
    parsed = parse_document_zip(zip_bytes)
    assert parsed.financial_metrics["sales"] is None
    assert not any(e.metric_name == "sales" for e in parsed.evidence)


def test_parse_document_zip_real_sales_wins_over_preceding_text_block() -> None:
    """テキストブロック行が先頭にあっても、本物の数値行が first-wins で勝つこと.

    修正前は first-wins により、先に来たテキストブロック由来の 1 が後続の本物の
    売上高をロックアウトしていた。テキストブロックを財務マッチから外すことで、
    後続の「売上高、経営指標等」の実数値が採用される。
    """
    zip_bytes = build_zip(
        {
            "XBRL_TO_CSV/jpcrp_pharma.csv": [
                {
                    "要素ID": (
                        "jpcrp_cor:RevenuesFromExternalCustomers"
                        "InformationForEachRegionTextBlock"
                    ),
                    "項目名": "売上高、地域ごとの情報 [テキストブロック]",
                    "相対年度": "当期",
                    "値": "(1) 売上高 本邦の外部顧客への売上高が90%を超えるため省略。",
                },
                {
                    "項目名": "売上高、経営指標等",
                    "相対年度": "当期",
                    "値": "43,971,000,000",
                },
            ],
        }
    )
    parsed = parse_document_zip(zip_bytes)
    assert parsed.financial_metrics["sales"] == 43_971_000_000


def test_parse_from_raw_facts_reproduces_zip_extraction() -> None:
    """保存済み raw_facts から再抽出すると ZIP 経由と同一の結果になること.

    reprocess (CSV 再ダウンロードなしの再抽出) の忠実性を担保する。
    raw_edinet_facts に積まれた生行だけで、財務・人的資本・evidence が
    完全に再現できることを検証する。
    """
    zip_bytes = build_zip(
        {
            "XBRL_TO_CSV/jpcrp_main.csv": [
                {
                    "要素ID": (
                        "jpcrp_cor:RevenuesFromExternalCustomers"
                        "InformationForEachRegionTextBlock"
                    ),
                    "項目名": "売上高、地域ごとの情報 [テキストブロック]",
                    "相対年度": "当期",
                    "値": "(1) 経常収益…記載を省略しております。",
                },
                {"項目名": "売上高、経営指標等", "相対年度": "当期", "値": "1,234"},
                {"項目名": "従業員数", "相対年度": "提出者", "値": "50"},
                {
                    "項目名": "管理職に占める女性労働者の割合",
                    "相対年度": "提出者",
                    "値": "12.5",
                },
            ],
        }
    )
    via_zip = parse_document_zip(zip_bytes)
    # テキストブロックを飛ばし、後続の本物 1,234 を採用していること
    assert via_zip.financial_metrics["sales"] == 1234

    via_raw = parse_from_raw_facts(via_zip.raw_facts)
    assert via_raw.financial_metrics == via_zip.financial_metrics
    assert [
        (e.metric_name, e.raw_value, e.scope, e.worker_type) for e in via_raw.evidence
    ] == [
        (e.metric_name, e.raw_value, e.scope, e.worker_type) for e in via_zip.evidence
    ]
    assert via_raw.human_metrics == via_zip.human_metrics


def test_parse_document_zip_element_id_match_takes_priority() -> None:
    """要素IDマッチが項目名マッチより優先され、unit='pure' は ％ 換算されること."""
    zip_bytes = build_zip(
        {
            "XBRL_TO_CSV/jpcrp_structured.csv": [
                {
                    "要素ID": (
                        "jpcrp_cor:RatioOfFemaleEmployeesInManagerialPositions"
                        "MetricsOfReportingCompany"
                    ),
                    "項目名": "管理職に占める女性労働者の割合、提出会社の指標",
                    "相対年度": "当期末",
                    "ユニットID": "pure",
                    "値": "0.024",
                },
            ],
        }
    )
    parsed = parse_document_zip(zip_bytes)

    record = _find_record(parsed.human_metrics, SCOPE_REPORTING_COMPANY, WORKER_TYPE_ALL)
    assert record is not None
    assert record.female_manager_ratio == pytest.approx(2.4)
    assert any(e.matched_by == "element_id_match" for e in parsed.evidence)


def test_parse_document_zip_captures_consolidated_subsidiary_dimension() -> None:
    """連結子会社の指標が別の HumanMetricRecord として保存される."""
    zip_bytes = build_zip(
        {
            "XBRL_TO_CSV/jpcrp.csv": [
                {
                    "要素ID": (
                        "jpcrp_cor:RatioOfFemaleEmployeesInManagerialPositions"
                        "MetricsOfReportingCompany"
                    ),
                    "項目名": "管理職に占める女性労働者の割合、提出会社の指標",
                    "相対年度": "当期末",
                    "ユニットID": "pure",
                    "値": "0.052",
                },
                {
                    "要素ID": (
                        "jpcrp_cor:RatioOfFemaleEmployeesInManagerialPositions"
                        "MetricsOfConsolidatedSubsidiaries"
                    ),
                    "項目名": "管理職に占める女性労働者の割合、連結子会社の指標",
                    "相対年度": "当期末",
                    "ユニットID": "pure",
                    "値": "0.143",
                },
            ],
        }
    )
    parsed = parse_document_zip(zip_bytes)
    reporting = _find_record(parsed.human_metrics, SCOPE_REPORTING_COMPANY, WORKER_TYPE_ALL)
    subsidiary = _find_record(
        parsed.human_metrics, SCOPE_CONSOLIDATED_SUBSIDIARY, WORKER_TYPE_ALL,
    )
    assert reporting is not None and reporting.female_manager_ratio == pytest.approx(5.2)
    assert subsidiary is not None and subsidiary.female_manager_ratio == pytest.approx(14.3)


def test_parse_document_zip_separates_worker_types_for_wage_gap() -> None:
    """賃金差異が worker_type ごとに別レコードとして保存される."""
    zip_bytes = build_zip(
        {
            "XBRL_TO_CSV/jpcrp.csv": [
                {
                    "要素ID": (
                        "jpcrp_cor:AllEmployeesDifferencesInWagesBetweenMaleAnd"
                        "FemaleEmployeesMetricsOfReportingCompany"
                    ),
                    "項目名": "全労働者、労働者の男女の賃金の差異、提出会社の指標",
                    "相対年度": "当期末",
                    "ユニットID": "pure",
                    "値": "0.682",
                },
                {
                    "要素ID": (
                        "jpcrp_cor:RegularEmployeesDifferencesInWagesBetweenMaleAnd"
                        "FemaleEmployeesMetricsOfReportingCompany"
                    ),
                    "項目名": "正規雇用労働者、労働者の男女の賃金の差異、提出会社の指標",
                    "相対年度": "当期末",
                    "ユニットID": "pure",
                    "値": "0.686",
                },
                {
                    "要素ID": (
                        "jpcrp_cor:NonRegularEmployeesDifferencesInWagesBetweenMaleAnd"
                        "FemaleEmployeesMetricsOfReportingCompany"
                    ),
                    "項目名": "非正規雇用労働者、労働者の男女の賃金の差異、提出会社の指標",
                    "相対年度": "当期末",
                    "ユニットID": "pure",
                    "値": "0.617",
                },
            ],
        }
    )
    parsed = parse_document_zip(zip_bytes)

    all_record = _find_record(parsed.human_metrics, SCOPE_REPORTING_COMPANY, WORKER_TYPE_ALL)
    regular_record = _find_record(
        parsed.human_metrics, SCOPE_REPORTING_COMPANY, WORKER_TYPE_REGULAR,
    )
    non_regular_record = _find_record(
        parsed.human_metrics, SCOPE_REPORTING_COMPANY, WORKER_TYPE_NON_REGULAR,
    )
    assert all_record.gender_wage_gap == pytest.approx(68.2)
    assert regular_record.gender_wage_gap == pytest.approx(68.6)
    assert non_regular_record.gender_wage_gap == pytest.approx(61.7)


def test_parse_document_zip_ignores_non_current_rows_and_uses_text_fallback() -> None:
    """前期データは無視し、項目名マッチとテキストフォールバックの両方が動作する."""
    zip_bytes = build_zip(
        {
            "XBRL_TO_CSV/jpcrp_metrics.csv": [
                {"項目名": "売上高", "値": "1,000", "相対年度": "前期"},
                {"項目名": "男性労働者の育児休業取得率", "値": "81.0", "相対年度": "提出者"},
                {
                    "項目名": "従業員の状況 [テキストブロック]",
                    "値": (
                        "管理職に占める女性労働者の割合 12.5 "
                        "男性労働者の育児休業取得率 81.0 "
                        "労働者の男女の賃金の差異(%) 75.5"
                    ),
                    "相対年度": "提出者",
                },
            ]
        }
    )
    parsed = parse_document_zip(zip_bytes)
    assert parsed.financial_metrics["sales"] is None  # 前期は無視

    # reporting_company × all に集約される
    reporting_all = _find_record(
        parsed.human_metrics, SCOPE_REPORTING_COMPANY, WORKER_TYPE_ALL,
    )
    assert reporting_all is not None
    assert reporting_all.male_childcare_leave_ratio == 81.0
    assert reporting_all.female_manager_ratio == 12.5
    assert reporting_all.gender_wage_gap == 75.5

    # employee_status_text が保持されている (LLM への入力候補)
    assert parsed.employee_status_text is not None
    assert "管理職に占める女性労働者の割合" in parsed.employee_status_text


def test_parse_document_zip_collects_raw_facts_with_all_available_columns() -> None:
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
    assert parsed.raw_facts[0].element_id == "jpcrp_cor:NetSales"


def test_parse_document_zip_raises_when_no_candidate_csv_files_exist() -> None:
    zip_bytes = build_zip(
        {"reports/annual.csv": [{"項目名": "売上高", "値": "1,234", "相対年度": "当期"}]},
    )
    with pytest.raises(ValueError, match="No candidate CSV files found in ZIP"):
        parse_document_zip(zip_bytes)


# ------------------------------------------------------------------ #
#  merge_llm_records: LLM 結果のマージ
# ------------------------------------------------------------------ #


def test_merge_llm_records_fills_only_missing_fields() -> None:
    """既存値がある指標は LLM 値で上書きされない (first-wins)."""
    zip_bytes = build_zip(
        {
            "XBRL_TO_CSV/jpcrp.csv": [
                {
                    "要素ID": (
                        "jpcrp_cor:RatioOfFemaleEmployeesInManagerialPositions"
                        "MetricsOfReportingCompany"
                    ),
                    "項目名": "管理職に占める女性労働者の割合、提出会社の指標",
                    "相対年度": "当期末",
                    "ユニットID": "pure",
                    "値": "0.052",  # → 5.2%
                },
            ],
        }
    )
    parsed = parse_document_zip(zip_bytes)

    # LLM が違う値 (99.0) を返したと仮定
    llm_records = [
        HumanMetricRecord(
            scope=SCOPE_REPORTING_COMPANY, worker_type=WORKER_TYPE_ALL,
            female_manager_ratio=99.0,  # 既存値 5.2 が温存されるべき
            male_childcare_leave_ratio=70.0,  # 新規で埋まる
        ),
    ]
    filled = merge_llm_records(parsed, llm_records)

    record = _find_record(parsed.human_metrics, SCOPE_REPORTING_COMPANY, WORKER_TYPE_ALL)
    assert record.female_manager_ratio == pytest.approx(5.2)  # 上書きされていない
    assert record.male_childcare_leave_ratio == 70.0  # 新規に埋まった
    assert filled == 1


def test_merge_llm_records_returns_zero_for_empty_input() -> None:
    zip_bytes = build_zip(
        {"XBRL_TO_CSV/jpcrp.csv": [{"項目名": "売上高", "値": "1,000", "相対年度": "当期"}]},
    )
    parsed = parse_document_zip(zip_bytes)
    assert merge_llm_records(parsed, []) == 0
