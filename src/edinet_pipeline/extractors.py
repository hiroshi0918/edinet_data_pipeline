"""EDINET CSV からの指標抽出 — 3層戦略.

  Layer 1: 要素IDマッチ (jpcrp_cor:RatioOf...) — 構造化XBRL の決定論的抽出
  Layer 2: 項目名マッチ — 旧タクソノミー / カスタム項目名のフォールバック
  Layer 3: テキストブロックからの抽出 — Layer 1/2 で空のときの最終手段

Layer 3 の中ではさらに:
  3a. 正規表現ベース (extract_human_capital_from_text)
  3b. LLM ベース (LLM_FALLBACK_ENABLED=true 時のみ; llm_extractor 経由)
"""

from __future__ import annotations

import io
import re
import statistics
import unicodedata
import zipfile

import pandas as pd

from edinet_pipeline.models import (
    SCOPE_CONSOLIDATED_SUBSIDIARY,
    SCOPE_REPORTING_COMPANY,
    WORKER_TYPE_ALL,
    WORKER_TYPE_NON_REGULAR,
    WORKER_TYPE_REGULAR,
    HumanMetricRecord,
    MetricEvidenceRecord,
    ParsedDocument,
    RawFactRecord,
)

# 人的資本指標 (割合) の上限値 (%)。本文中の注釈番号などの誤検知を排除。
DEFAULT_HUMAN_METRIC_MAX_RATIO = 200.0

FINANCIAL_FIELDS = ("sales", "operating_profit", "net_profit", "employee_count")
HUMAN_FIELDS = (
    "female_manager_ratio",
    "male_childcare_leave_ratio",
    "gender_wage_gap",
)

# Layer 2: 項目名部分一致パターン
EXPLICIT_PATTERNS = {
    "sales": ("売上高", "営業収益", "売上収益", "完成工事高"),
    "operating_profit": ("営業利益", "営業損失"),
    "net_profit": ("当期純利益", "親会社株主に帰属する"),
    "employee_count": ("従業員数",),
    "female_manager_ratio": ("管理職に占める女性労働者の割合",),
    "male_childcare_leave_ratio": ("男性労働者の育児休業取得率", "男性の育児休業取得率"),
    "gender_wage_gap": ("男女の賃金の差異", "男女賃金差異"),
}

# 「当期」を含む値で当事業年度の指標を識別。
# 提出会社XBRL は「当期末」なので「当期」の部分一致でカバーされる。
CURRENT_PERIOD_MARKERS = ("当期", "当年", "当連結会計年度", "提出者", "当事業年度")

# 「従業員の状況」テキストブロックの項目名 (Layer 3 のトリガー)
EMPLOYEE_STATUS_BLOCK_LABEL = "従業員の状況"


# ------------------------------------------------------------------ #
#  Layer 1: 要素ID 分類器
# ------------------------------------------------------------------ #


def classify_element_id(element_id: str | None) -> tuple[str, str, str] | None:
    """XBRL 要素ID から (metric_name, scope, worker_type) を判定する.

    要素IDの構造例:
      jpcrp_cor:RatioOfFemaleEmployeesInManagerialPositionsMetricsOfReportingCompany
      jpcrp_cor:AllEmployees...RatioOfMaleEmployeesTakingChildcareLeaveMetricsOfReportingCompany
      jpcrp_cor:RegularEmployeesDifferencesInWagesBetweenMaleAndFemaleEmployeesMetricsOfReportingCompany

    判定不能なら None。
    """
    if not element_id:
        return None

    # scope (末尾サフィックス)
    if "MetricsOfReportingCompany" in element_id:
        scope = SCOPE_REPORTING_COMPANY
    elif "MetricsOfConsolidatedSubsidiaries" in element_id:
        scope = SCOPE_CONSOLIDATED_SUBSIDIARY
    else:
        return None

    # 指標種別 (中央サブストリング)
    if "RatioOfFemaleEmployeesInManagerialPositions" in element_id:
        metric = "female_manager_ratio"
        # 女性管理職比率は worker_type の区分なし → "all" に集約
        return (metric, scope, WORKER_TYPE_ALL)
    if "RatioOfMaleEmployeesTakingChildcareLeave" in element_id:
        metric = "male_childcare_leave_ratio"
    elif "DifferencesInWagesBetweenMaleAndFemaleEmployees" in element_id:
        metric = "gender_wage_gap"
    else:
        return None

    # worker_type (プレフィックス)
    local_part = element_id.split(":", 1)[-1]
    if local_part.startswith("AllEmployees"):
        worker_type = WORKER_TYPE_ALL
    elif local_part.startswith("RegularEmployees"):
        worker_type = WORKER_TYPE_REGULAR
    elif local_part.startswith("NonRegularEmployees"):
        worker_type = WORKER_TYPE_NON_REGULAR
    else:
        worker_type = WORKER_TYPE_ALL  # フォールバック

    return (metric, scope, worker_type)


# ------------------------------------------------------------------ #
#  共通ユーティリティ
# ------------------------------------------------------------------ #


def empty_parsed_document() -> ParsedDocument:
    """全フィールドが None / 空リストの ParsedDocument を作成."""
    return ParsedDocument(
        financial_metrics={name: None for name in FINANCIAL_FIELDS},
        human_metrics=[],
        evidence=[],
        raw_facts=[],
    )


def normalize_text(value: object) -> str:
    """NFKC 正規化し前後空白を除去 (NaN/None は空文字列)."""
    if value is None or pd.isna(value):
        return ""
    return unicodedata.normalize("NFKC", str(value)).strip()


def stringify_raw(value: object) -> str | None:
    """値を文字列化 (NaN/None は None)."""
    if value is None or pd.isna(value):
        return None
    return str(value)


def extract_numeric(value: object) -> float | None:
    """文字列から数値を抽出. (1,000) は -1000、"-" や空は None."""
    text = normalize_text(value)
    if not text or text in {"-", "nan", "None", "－", "―"}:
        return None

    negative = False
    if text.startswith("(") and text.endswith(")"):
        negative = True
        text = text[1:-1]

    text = text.replace(",", "")
    match = re.search(r"[-+]?\d+(?:\.\d+)?", text)
    if not match:
        return None

    number = float(match.group())
    if negative and number > 0:
        return -number
    return number


def convert_to_percentage(value: float, unit_id: str | None) -> float:
    """unit_id='pure' (XBRLの割合表記 0.024) を ％ に換算 (×100)."""
    if unit_id and unit_id.strip().lower() == "pure":
        return value * 100.0
    return value


def is_relevant_relative_year(relative_year: str) -> bool:
    """relative_year が当期/当事業年度/当期末等を含むか.

    空文字列の場合は True (フィルタしない)。
    """
    normalized = normalize_text(relative_year)
    if not normalized:
        return True
    return any(marker in normalized for marker in CURRENT_PERIOD_MARKERS)


# ------------------------------------------------------------------ #
#  Layer 3a: 正規表現ベースのテキスト抽出 (旧来の fallback ロジック)
# ------------------------------------------------------------------ #


def _extract_label_value(
    section: str,
    labels: tuple[str, ...],
    *,
    other_labels: tuple[str, ...] = (),
    max_ratio: float = DEFAULT_HUMAN_METRIC_MAX_RATIO,
) -> float | None:
    """ラベル直後の最初の妥当な数値を抽出する.

    F=M同値バグ対策として `other_labels` を受け取り、ラベル直後の走査窓内に
    他のラベルが存在する場合はそこまでで打ち切る。これにより、
    「ラベル群が並んだあと数値群が来る」レイアウトで全ラベルが先頭の数値に
    マッチしてしまう問題を防ぐ。
    """
    for label in labels:
        start = section.find(label)
        if start == -1:
            continue
        after_label = section[start + len(label):]

        # 他ラベルの直前で打ち切り
        cutoff = len(after_label)
        for other in other_labels:
            if other in labels:
                continue
            pos = after_label.find(other)
            if pos != -1 and pos < cutoff:
                cutoff = pos
        window = after_label[:cutoff]

        # 邪魔な単位付き数字を除去
        cleaned = re.sub(
            r"\d+(?:\.\d+)?\s*(?:年|月|日|号|条|項|名|人|円|千円|百万円|歳|ヶ月)",
            "",
            window,
        )
        cleaned = re.sub(r"[\(（]?注[)）]?\s*\d+", "", cleaned)
        cleaned = re.sub(r"※\s*\d+", "", cleaned)
        cleaned = re.sub(r"[①②③④⑤⑥⑦⑧⑨⑩]", "", cleaned)

        for match in re.finditer(r"(-|\d+(?:\.\d+)?)", cleaned):
            token = match.group(1)
            if token == "-":
                return None
            try:
                val = float(token)
                if val > max_ratio:
                    continue
                return val
            except ValueError:
                continue
    return None


def extract_human_capital_from_text(
    text: object,
    *,
    max_ratio: float = DEFAULT_HUMAN_METRIC_MAX_RATIO,
) -> dict[str, float]:
    """「従業員の状況」テキストから人的資本3指標を抽出 (regex ベース).

    抽出範囲を「管理職に占める女性労働者の割合」直後の 800 文字に限定し、
    各ラベル間の干渉を `_extract_label_value(other_labels=...)` で防ぐ。
    """
    normalized = normalize_text(text)
    anchor = "管理職に占める女性労働者の割合"
    if anchor not in normalized:
        return {}

    start = normalized.find(anchor)
    section = normalized[start : start + 800]
    section = re.sub(r"[\(（]注[^)）]*[\)）]\s*[0-9０-９]?", "", section)
    section = re.sub(r"\s+", " ", section)

    female_labels = ("管理職に占める女性労働者の割合",)
    male_labels = ("男性労働者の育児休業取得率", "男性の育児休業取得率")
    wage_labels = (
        "労働者の男女の賃金の差異(%)",
        "男女の賃金の差異(%)",
        "労働者の男女賃金差異(%)",
        "男女の賃金の差異",
    )
    all_labels = female_labels + male_labels + wage_labels

    result: dict[str, float] = {}
    female_value = _extract_label_value(
        section, female_labels, other_labels=all_labels, max_ratio=max_ratio,
    )
    if female_value is not None:
        result["female_manager_ratio"] = female_value

    male_value = _extract_label_value(
        section, male_labels, other_labels=all_labels, max_ratio=max_ratio,
    )
    if male_value is not None:
        result["male_childcare_leave_ratio"] = male_value

    wage_value = _extract_label_value(
        section, wage_labels, other_labels=all_labels, max_ratio=max_ratio,
    )
    if wage_value is not None:
        result["gender_wage_gap"] = wage_value

    return result


# ------------------------------------------------------------------ #
#  HumanMetricsBuilder — 多次元キーで複数行の HumanMetricRecord を集約
# ------------------------------------------------------------------ #


class HumanMetricsBuilder:
    """(scope, worker_type) ごとに HumanMetricRecord の値を集約するビルダー.

    値の保持には 2 つのモードがある:
      - observe (Layer 1 = element_id_match 用):
          XBRL の同一 element_id に対して contextRef 違いで複数値が並ぶケース
          （連結子会社が複数社並列で書かれる等）を全て蓄積し、to_records で
          中央値に集約する。外れ値（例: 連結子会社 18 社中 1 社だけ 200%）が
          採用値を爆発させるバグへの対処。
      - set_value (Layer 2/3 = item_name_match / text_fallback / LLM 用):
          first-wins。Layer 1 で 1 つでも観測があれば has_value=True となり、
          Layer 2/3 値は混入しないので信頼性順序は崩れない。
    """

    def __init__(self) -> None:
        # (scope, worker_type) -> {metric_name: list[float]}
        # 値のリスト。to_records 時点で中央値（1要素なら値そのもの）を採用。
        self._buckets: dict[tuple[str, str], dict[str, list[float]]] = {}

    def _ensure_bucket(self, scope: str, worker_type: str) -> dict[str, list[float]]:
        key = (scope, worker_type)
        if key not in self._buckets:
            self._buckets[key] = {name: [] for name in HUMAN_FIELDS}
        return self._buckets[key]

    def has_value(self, scope: str, worker_type: str, metric_name: str) -> bool:
        bucket = self._buckets.get((scope, worker_type))
        if bucket is None:
            return False
        return bool(bucket.get(metric_name))

    def has_any_value_for_reporting_company(self) -> bool:
        """提出会社の指標が1つでも入っているか (LLM フォールバック判定用)."""
        for (scope, _), bucket in self._buckets.items():
            if scope != SCOPE_REPORTING_COMPANY:
                continue
            if any(bucket.values()):
                return True
        return False

    def observe(
        self, scope: str, worker_type: str, metric_name: str, value: float,
    ) -> None:
        """Layer 1 用. 観測値をリストに追加 (first-wins チェックなし)."""
        self._ensure_bucket(scope, worker_type)[metric_name].append(value)

    def set_value(
        self, scope: str, worker_type: str, metric_name: str, value: float,
    ) -> bool:
        """Layer 2/3 用. 既に値があれば False を返してスキップ (first-wins)."""
        bucket = self._ensure_bucket(scope, worker_type)
        if bucket[metric_name]:
            return False
        bucket[metric_name].append(value)
        return True

    @staticmethod
    def _aggregate(values: list[float]) -> float | None:
        if not values:
            return None
        # 1 件のときは値そのもの。複数件は中央値で外れ値の影響を抑制する。
        return statistics.median(values)

    def to_records(self) -> list[HumanMetricRecord]:
        """累積した値を HumanMetricRecord のリストに変換 (中央値集約)."""
        return [
            HumanMetricRecord(
                scope=scope,
                worker_type=worker_type,
                female_manager_ratio=self._aggregate(values["female_manager_ratio"]),
                male_childcare_leave_ratio=self._aggregate(values["male_childcare_leave_ratio"]),
                gender_wage_gap=self._aggregate(values["gender_wage_gap"]),
            )
            for (scope, worker_type), values in sorted(self._buckets.items())
        ]


# ------------------------------------------------------------------ #
#  メイン関数: ZIP → ParsedDocument
# ------------------------------------------------------------------ #


def parse_document_zip(
    zip_bytes: bytes,
    *,
    max_ratio: float = DEFAULT_HUMAN_METRIC_MAX_RATIO,
) -> ParsedDocument:
    """書類CSV ZIPをパースし、財務指標と人的資本指標を抽出する.

    抽出順序:
      Layer 1: element_id マッチ (要素ID完全一致)
      Layer 2: item_name マッチ (項目名部分一致) — financial 指標と HC を扱う
      Layer 3a: text_fallback (regex ベースのテキスト抽出)
    Layer 3b (LLM) は jobs.py 側で `text_block` を引数に呼び出される。
    """
    parsed = empty_parsed_document()
    hm_builder = HumanMetricsBuilder()
    employee_status_text: str | None = None  # Layer 3 の入力候補を保持
    employee_status_source: str | None = None  # 同上の出処 CSV ファイル名

    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as archive:
        csv_files = [
            name
            for name in archive.namelist()
            if name.endswith(".csv")
            and (
                "jpcrp" in name.lower() or "jpaud" in name.lower()
                or "xbrl_to_csv" in name.lower()
            )
        ]
        if not csv_files:
            raise ValueError("No candidate CSV files found in ZIP")

        for csv_file in csv_files:
            with archive.open(csv_file) as handle:
                frame = pd.read_csv(handle, encoding="utf-16le", sep="\t")

            extractable = "項目名" in frame.columns and "値" in frame.columns

            for row_number, row_dict in enumerate(frame.to_dict("records"), start=1):
                raw_fact = RawFactRecord(
                    source_file=csv_file,
                    row_number=row_number,
                    element_id=stringify_raw(row_dict.get("要素ID")),
                    item_name=stringify_raw(row_dict.get("項目名")),
                    context_id=stringify_raw(row_dict.get("コンテキストID")),
                    relative_year=stringify_raw(row_dict.get("相対年度")),
                    consolidation_type=stringify_raw(row_dict.get("連結・個別")),
                    period_type=stringify_raw(row_dict.get("期間・時点")),
                    unit_id=stringify_raw(row_dict.get("ユニットID")),
                    unit_label=stringify_raw(row_dict.get("単位")),
                    raw_value=stringify_raw(row_dict.get("値")),
                )
                parsed.raw_facts.append(raw_fact)

                if not extractable:
                    continue

                item_name = normalize_text(raw_fact.item_name)
                raw_value = raw_fact.raw_value
                raw_text = normalize_text(raw_value)
                relative_year = normalize_text(raw_fact.relative_year)

                # 「従業員の状況 [テキストブロック]」を Layer 3 のためにキャッシュ
                if (
                    EMPLOYEE_STATUS_BLOCK_LABEL in item_name
                    and "テキストブロック" in item_name
                    and raw_text
                ):
                    employee_status_text = raw_text
                    employee_status_source = csv_file

                if not item_name and not raw_text:
                    continue

                # ---- Layer 1: 要素IDマッチ (人的資本のみ) ---------------- #
                classification = classify_element_id(raw_fact.element_id)
                if classification is not None:
                    _try_apply_element_id_match(
                        hm_builder, parsed, classification,
                        raw_fact=raw_fact, item_name=item_name,
                        raw_text=raw_text, relative_year=relative_year,
                        csv_file=csv_file, max_ratio=max_ratio,
                    )
                    continue  # 要素IDで処理済みなので Layer 2 に降りない

                # ---- Layer 2: 項目名マッチ -------------------------------- #
                for metric_name, patterns in EXPLICIT_PATTERNS.items():
                    is_financial = metric_name in parsed.financial_metrics
                    if is_financial and parsed.financial_metrics[metric_name] is not None:
                        continue
                    if (
                        not is_financial
                        and hm_builder.has_value(
                            SCOPE_REPORTING_COMPANY, WORKER_TYPE_ALL, metric_name,
                        )
                    ):
                        continue
                    if not is_relevant_relative_year(relative_year):
                        continue
                    if not any(pattern in item_name for pattern in patterns):
                        continue

                    numeric_value = extract_numeric(raw_value)
                    if numeric_value is None:
                        continue

                    if is_financial:
                        parsed.financial_metrics[metric_name] = int(round(numeric_value))
                        parsed.evidence.append(
                            MetricEvidenceRecord(
                                metric_name=metric_name,
                                item_name=item_name or metric_name,
                                raw_value=raw_text,
                                relative_year=relative_year,
                                source_file=csv_file,
                                matched_by="item_name_match",
                                element_id=raw_fact.element_id,
                            )
                        )
                    else:
                        converted = convert_to_percentage(numeric_value, raw_fact.unit_id)
                        if 0.0 <= converted <= max_ratio:
                            if hm_builder.set_value(
                                SCOPE_REPORTING_COMPANY, WORKER_TYPE_ALL,
                                metric_name, converted,
                            ):
                                parsed.evidence.append(
                                    MetricEvidenceRecord(
                                        metric_name=metric_name,
                                        item_name=item_name or metric_name,
                                        raw_value=raw_text,
                                        relative_year=relative_year,
                                        source_file=csv_file,
                                        matched_by="item_name_match",
                                        element_id=raw_fact.element_id,
                                        scope=SCOPE_REPORTING_COMPANY,
                                        worker_type=WORKER_TYPE_ALL,
                                    )
                                )

    # ---- Layer 3a: regex によるテキストフォールバック (1書類1回) ----- #
    # 旧実装は CSV 全行に対して fallback regex を走らせていたが、人的資本の
    # 自由記述は「従業員の状況 [テキストブロック]」にしか入らないため、
    # ここでまとめて 1 回だけ実行することで N倍の重複処理を排除する。
    if employee_status_text and employee_status_source is not None:
        _apply_text_fallback(
            hm_builder, parsed,
            text=employee_status_text,
            source_file=employee_status_source,
            max_ratio=max_ratio,
        )

    parsed.human_metrics = hm_builder.to_records()
    parsed.employee_status_text = employee_status_text
    return parsed


# ------------------------------------------------------------------ #
#  parse_document_zip 内部ヘルパー
# ------------------------------------------------------------------ #


def _try_apply_element_id_match(
    hm_builder: HumanMetricsBuilder,
    parsed: ParsedDocument,
    classification: tuple[str, str, str],
    *,
    raw_fact: RawFactRecord,
    item_name: str,
    raw_text: str,
    relative_year: str,
    csv_file: str,
    max_ratio: float,
) -> None:
    """Layer 1 (要素IDマッチ) の適用.

    同一 (scope, worker_type, metric_name) に対して contextRef 違いで複数値が
    並ぶケース（連結子会社が複数社並列）を全て観測リストに溜め、to_records
    で中央値に集約する。evidence には観測した全 raw_fact を記録するため、
    後段で「どの値が採用されたか」を辿れる。
    """
    metric_name, scope, worker_type = classification
    numeric_value = extract_numeric(raw_fact.raw_value)
    if numeric_value is None:
        return
    converted = convert_to_percentage(numeric_value, raw_fact.unit_id)
    if not (0.0 <= converted <= max_ratio):
        return
    hm_builder.observe(scope, worker_type, metric_name, converted)
    parsed.evidence.append(
        MetricEvidenceRecord(
            metric_name=metric_name,
            item_name=item_name or metric_name,
            raw_value=raw_text,
            relative_year=relative_year,
            source_file=csv_file,
            matched_by="element_id_match",
            element_id=raw_fact.element_id,
            scope=scope,
            worker_type=worker_type,
        )
    )


def _apply_text_fallback(
    hm_builder: HumanMetricsBuilder,
    parsed: ParsedDocument,
    *,
    text: str,
    source_file: str,
    max_ratio: float,
) -> None:
    """Layer 3a (regex テキスト抽出) の適用. 1 書類で 1 回だけ呼ばれる前提."""
    fallback_metrics = extract_human_capital_from_text(text, max_ratio=max_ratio)
    raw_text = normalize_text(text)
    for metric_name, metric_value in fallback_metrics.items():
        if not hm_builder.set_value(
            SCOPE_REPORTING_COMPANY, WORKER_TYPE_ALL, metric_name, metric_value,
        ):
            continue
        parsed.evidence.append(
            MetricEvidenceRecord(
                metric_name=metric_name,
                item_name=EMPLOYEE_STATUS_BLOCK_LABEL + " [テキストブロック]",
                raw_value=raw_text,
                relative_year="提出日時点",
                source_file=source_file,
                matched_by="text_fallback",
                scope=SCOPE_REPORTING_COMPANY,
                worker_type=WORKER_TYPE_ALL,
            )
        )


# ------------------------------------------------------------------ #
#  Layer 3b: LLM 抽出結果のマージ
# ------------------------------------------------------------------ #


def merge_llm_records(
    parsed: ParsedDocument,
    llm_records: list[HumanMetricRecord],
    *,
    source_file: str | None = None,
) -> int:
    """LLMで抽出した HumanMetricRecord を ParsedDocument にマージする.

    既存レコードと (scope, worker_type) が衝突する場合、空欄のフィールドのみ
    LLM 値で埋める (first-wins; element_id_match / item_name_match の値は温存)。

    Args:
        parsed: parse_document_zip の戻り値
        llm_records: LLM 抽出結果 (extract_via_llm の出力)
        source_file: evidence に記録するファイル名 (NULL 不可カラムの保護)

    Returns:
        新規にセットしたフィールド数 (0 ならマージで埋まったフィールドなし)
    """
    if not llm_records:
        return 0

    # 既存 records を HumanMetricsBuilder にリロードし、first-wins で LLM 値をマージ。
    # マージロジックを Builder に集約することで、parse_document_zip と同じ
    # 「同一キー・同一指標で初出値を保持する」セマンティクスを再利用する。
    builder = HumanMetricsBuilder()
    for rec in parsed.human_metrics:
        for metric_name in HUMAN_FIELDS:
            value = getattr(rec, metric_name)
            if value is not None:
                builder.set_value(rec.scope, rec.worker_type, metric_name, value)

    filled_count = 0
    for llm_rec in llm_records:
        for metric_name in HUMAN_FIELDS:
            llm_value = getattr(llm_rec, metric_name)
            if llm_value is None:
                continue
            if not builder.set_value(
                llm_rec.scope, llm_rec.worker_type, metric_name, llm_value,
            ):
                continue  # 既存値があり上書きしない
            filled_count += 1
            parsed.evidence.append(
                MetricEvidenceRecord(
                    metric_name=metric_name,
                    item_name=EMPLOYEE_STATUS_BLOCK_LABEL + " [テキストブロック]",
                    raw_value=str(llm_value),
                    relative_year="",
                    source_file=source_file or "(llm_fallback)",
                    matched_by="llm_fallback",
                    scope=llm_rec.scope,
                    worker_type=llm_rec.worker_type,
                )
            )

    parsed.human_metrics = builder.to_records()
    return filled_count
