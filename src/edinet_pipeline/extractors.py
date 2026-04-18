from __future__ import annotations

import io
import re
import unicodedata
import zipfile

import pandas as pd

from edinet_pipeline.models import MetricEvidenceRecord, ParsedDocument, RawFactRecord

# 人的資本指標 (割合) として受け入れる既定の上限値 (%)。
# 呼び出し側 (Settings.human_metric_max_ratio) から明示的に指定されない場合のフォールバック。
DEFAULT_HUMAN_METRIC_MAX_RATIO = 200.0

FINANCIAL_FIELDS = ("sales", "operating_profit", "net_profit", "employee_count")
HUMAN_FIELDS = (
    "female_manager_ratio",
    "male_childcare_leave_ratio",
    "gender_wage_gap",
)

EXPLICIT_PATTERNS = {
    "sales": ("売上高", "営業収益", "売上収益", "完成工事高"),
    "operating_profit": ("営業利益", "営業損失"),
    "net_profit": ("当期純利益", "親会社株主に帰属する"),
    "employee_count": ("従業員数",),
    "female_manager_ratio": ("管理職に占める女性労働者の割合",),
    "male_childcare_leave_ratio": ("男性労働者の育児休業取得率", "男性の育児休業取得率"),
    "gender_wage_gap": ("男女の賃金の差異", "男女賃金差異"),
}
CURRENT_PERIOD_MARKERS = ("当期", "当年", "当連結会計年度", "提出者")


def empty_parsed_document() -> ParsedDocument:
    return ParsedDocument(
        financial_metrics={name: None for name in FINANCIAL_FIELDS},
        human_metrics={name: None for name in HUMAN_FIELDS},
        evidence=[],
        raw_facts=[],
    )


def normalize_text(value: object) -> str:
    if value is None or pd.isna(value):
        return ""
    return unicodedata.normalize("NFKC", str(value)).strip()


def stringify_raw(value: object) -> str | None:
    if value is None or pd.isna(value):
        return None
    return str(value)


def extract_numeric(value: object) -> float | None:
    text = normalize_text(value)
    if not text or text in {"-", "nan", "None"}:
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


def parse_metric_tokens(compact_text: str) -> list[float | None]:
    normalized = normalize_text(compact_text).replace("－", "-").replace("―", "-")
    normalized = re.sub(r"[%％,]", "", normalized)
    tokens: list[float | None] = []
    for token in re.findall(r"-|\d+(?:\.\d+)?", normalized):
        if token == "-":
            tokens.append(None)
        else:
            tokens.append(float(token))
    return tokens


def is_relevant_relative_year(relative_year: str) -> bool:
    normalized = normalize_text(relative_year)
    if not normalized:
        return True
    return any(marker in normalized for marker in CURRENT_PERIOD_MARKERS)


def _extract_label_value(
    section: str,
    labels: tuple[str, ...],
    *,
    max_ratio: float = DEFAULT_HUMAN_METRIC_MAX_RATIO,
) -> float | None:
    for label in labels:
        start = section.find(label)
        if start == -1:
            continue
        after_label = section[start + len(label):]

        # 邪魔な「年」「号」「名」などの数字や注釈番号を除去
        cleaned = re.sub(r"\d+(?:\.\d+)?\s*(?:年|月|日|号|条|項|名|人|円|千円|百万円|歳|ヶ月)", "", after_label)
        cleaned = re.sub(r"[\(（]?注[)）]?\s*\d+", "", cleaned)
        cleaned = re.sub(r"※\s*\d+", "", cleaned)
        # 不要な記号も消す（例として "①" などの丸数字や、本文中の不要な注釈の名残）
        cleaned = re.sub(r"[①②③④⑤⑥⑦⑧⑨⑩]", "", cleaned)

        # 全ての数字（またはハイフン）を順番に見ていく
        for match in re.finditer(r"(-|\d+(?:\.\d+)?)", cleaned):
            token = match.group(1)
            if token == "-":
                return None
            try:
                val = float(token)
                # 割合としてあり得ない異常値は誤検知 (注釈番号など) の可能性が高いためスキップ。
                # 閾値は max_ratio (既定: Settings.human_metric_max_ratio) で調整可能。
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
    normalized = normalize_text(text)
    if "管理職に占める女性労働者の割合" not in normalized:
        return {}

    start = normalized.find("管理職に占める女性労働者の割合")
    section = normalized[start : start + 800]
    section = re.sub(r"[\(（]注[^)）]*[\)）]\s*[0-9０-９]?", "", section)
    section = re.sub(r"\s+", " ", section)

    metric_labels = [
        "労働者の男女の賃金の差異(%)",
        "男女の賃金の差異(%)",
        "労働者の男女賃金差異(%)",
    ]

    result = {}
    female_manager_ratio = _extract_label_value(
        section, ("管理職に占める女性労働者の割合",), max_ratio=max_ratio,
    )
    if female_manager_ratio is not None:
        result["female_manager_ratio"] = female_manager_ratio

    male_childcare_leave_ratio = _extract_label_value(
        section,
        ("男性労働者の育児休業取得率", "男性の育児休業取得率"),
        max_ratio=max_ratio,
    )
    if male_childcare_leave_ratio is not None:
        result["male_childcare_leave_ratio"] = male_childcare_leave_ratio

    gender_wage_gap = _extract_label_value(
        section, tuple(metric_labels), max_ratio=max_ratio,
    )
    if gender_wage_gap is not None:
        result["gender_wage_gap"] = gender_wage_gap

    return result


def parse_document_zip(
    zip_bytes: bytes,
    *,
    max_ratio: float = DEFAULT_HUMAN_METRIC_MAX_RATIO,
) -> ParsedDocument:
    parsed = empty_parsed_document()
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as archive:
        csv_files = [
            name
            for name in archive.namelist()
            if name.endswith(".csv")
            and (
                "jpcrp" in name.lower() or "jpaud" in name.lower() or "xbrl_to_csv" in name.lower()
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

                if not item_name and not raw_text:
                    continue

                for metric_name, patterns in EXPLICIT_PATTERNS.items():
                    if (
                        metric_name in parsed.financial_metrics
                        and parsed.financial_metrics[metric_name] is not None
                    ):
                        continue
                    if (
                        metric_name in parsed.human_metrics
                        and parsed.human_metrics[metric_name] is not None
                    ):
                        continue
                    if not is_relevant_relative_year(relative_year):
                        continue
                    if not any(pattern in item_name for pattern in patterns):
                        continue

                    numeric_value = extract_numeric(raw_value)
                    if numeric_value is None:
                        continue

                    evidence = MetricEvidenceRecord(
                        metric_name=metric_name,
                        item_name=item_name or metric_name,
                        raw_value=raw_text,
                        relative_year=relative_year,
                        source_file=csv_file,
                        matched_by="item_name_match",
                    )
                    parsed.evidence.append(evidence)

                    if metric_name in parsed.financial_metrics:
                        parsed.financial_metrics[metric_name] = int(round(numeric_value))
                    else:
                        parsed.human_metrics[metric_name] = numeric_value

                fallback_metrics = extract_human_capital_from_text(raw_text, max_ratio=max_ratio)
                for metric_name, metric_value in fallback_metrics.items():
                    if parsed.human_metrics[metric_name] is not None:
                        continue
                    parsed.human_metrics[metric_name] = metric_value
                    parsed.evidence.append(
                        MetricEvidenceRecord(
                            metric_name=metric_name,
                            item_name=item_name or metric_name,
                            raw_value=raw_text,
                            relative_year=relative_year,
                            source_file=csv_file,
                            matched_by="text_fallback",
                        )
                    )

    return parsed
