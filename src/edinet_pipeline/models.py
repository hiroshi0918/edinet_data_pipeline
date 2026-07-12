"""ドメインモデル — パイプラインの主要な値オブジェクト/データクラスを定義.

設計方針:
  - すべて dataclass(frozen=True) で不変性を担保
  - HumanMetricRecord は (scope, worker_type) の次元情報を保持し、
    1書類が複数の人的資本レコードを持てるようにする
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any

# --- 次元の固定値定義 (DBの CHECK 制約と整合させる) -------------------- #

SCOPE_REPORTING_COMPANY = "reporting_company"
SCOPE_CONSOLIDATED_SUBSIDIARY = "consolidated_subsidiary"
ALLOWED_SCOPES = frozenset({SCOPE_REPORTING_COMPANY, SCOPE_CONSOLIDATED_SUBSIDIARY})

WORKER_TYPE_ALL = "all"
WORKER_TYPE_REGULAR = "regular"
WORKER_TYPE_NON_REGULAR = "non_regular"
ALLOWED_WORKER_TYPES = frozenset(
    {WORKER_TYPE_ALL, WORKER_TYPE_REGULAR, WORKER_TYPE_NON_REGULAR}
)


@dataclass(frozen=True)
class FilingFilters:
    """対象書類のフィルタ条件 (有価証券報告書のみ等)."""

    ordinance_code: str = "010"
    form_code: str = "030000"
    doc_description_prefix: str = "有価証券報告書－"

    def matches(self, document: dict[str, Any]) -> bool:
        doc_description = str(document.get("docDescription", ""))
        return (
            doc_description.startswith(self.doc_description_prefix)
            and str(document.get("ordinanceCode", "")) == self.ordinance_code
            and str(document.get("formCode", "")) == self.form_code
        )


@dataclass(frozen=True)
class DocumentRecord:
    """書類メタデータ (financial_reports へ upsert する単位)."""

    doc_id: str
    edinet_code: str
    filer_name: str
    submitted_date: date
    fiscal_year: int
    csv_available: bool
    source_metadata: dict[str, Any]


@dataclass(frozen=True)
class HumanMetricRecord:
    """人的資本指標レコード — 次元 (scope × worker_type) ごとに1行.

    Attributes:
        scope:        "reporting_company" or "consolidated_subsidiary"
        worker_type:  "all" / "regular" / "non_regular"
        female_manager_ratio:        女性管理職比率 (%)
        male_childcare_leave_ratio:  男性育休取得率 (%)
        gender_wage_gap:             男女の賃金差異 (%)
        average_annual_salary:       平均年間給与 (円)
        average_years_of_service:    平均勤続年数 (年)
        average_age:                 平均年齢 (歳)

    Note:
        female_manager_ratio は worker_type の区分を持たないため、
        慣例として worker_type="all" の行にのみ格納する。
        average_* の3指標は「従業員の状況」の提出会社単体開示のため、
        (reporting_company, all) の行にのみ格納する。
    """

    scope: str
    worker_type: str
    female_manager_ratio: float | None = None
    male_childcare_leave_ratio: float | None = None
    gender_wage_gap: float | None = None
    average_annual_salary: float | None = None
    average_years_of_service: float | None = None
    average_age: float | None = None


@dataclass(frozen=True)
class MetricEvidenceRecord:
    """指標抽出の根拠 (監査証跡) — どの行から、どの方式で抽出したか.

    Attributes:
        matched_by: "element_id_match" / "item_name_match" /
                    "text_fallback" / "llm_fallback"
        element_id: XBRL要素ID (element_id_match 時のみ非None)
        scope/worker_type: 次元情報 (HumanMetricRecord と対応)
    """

    metric_name: str
    item_name: str
    raw_value: str
    relative_year: str
    source_file: str
    matched_by: str
    element_id: str | None = None
    scope: str | None = None
    worker_type: str | None = None


@dataclass(frozen=True)
class RawFactRecord:
    """元CSVの1行を保存するためのレコード (raw_edinet_facts テーブル)."""

    source_file: str
    row_number: int
    element_id: str | None
    item_name: str | None
    context_id: str | None
    relative_year: str | None
    consolidation_type: str | None
    period_type: str | None
    unit_id: str | None
    unit_label: str | None
    raw_value: str | None


@dataclass
class ParsedDocument:
    """1書類分の解析結果コンテナ — extractor の出力 / repository の入力.

    Attributes:
        financial_metrics: 財務指標 (sales, operating_profit, net_profit, employee_count)
        human_metrics:     人的資本指標レコードのリスト (次元ごとに複数行)
        evidence:          各指標の抽出根拠
        raw_facts:         元CSVの全行 (監査・再抽出用)
        employee_status_text: 「従業員の状況 [テキストブロック]」の生テキスト.
            Layer 3b (LLM フォールバック) の入力候補として保持。
            jobs 層で参照され、LLM 抽出に渡される。
    """

    financial_metrics: dict[str, int | None] = field(default_factory=dict)
    human_metrics: list[HumanMetricRecord] = field(default_factory=list)
    evidence: list[MetricEvidenceRecord] = field(default_factory=list)
    raw_facts: list[RawFactRecord] = field(default_factory=list)
    employee_status_text: str | None = None
