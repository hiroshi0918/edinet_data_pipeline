from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any


@dataclass(frozen=True)
class FilingFilters:
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
    doc_id: str
    edinet_code: str
    filer_name: str
    submitted_date: date
    fiscal_year: int
    csv_available: bool
    source_metadata: dict[str, Any]


@dataclass(frozen=True)
class MetricEvidenceRecord:
    metric_name: str
    item_name: str
    raw_value: str
    relative_year: str
    source_file: str
    matched_by: str


@dataclass
class ParsedDocument:
    financial_metrics: dict[str, int | None] = field(default_factory=dict)
    human_metrics: dict[str, float | None] = field(default_factory=dict)
    evidence: list[MetricEvidenceRecord] = field(default_factory=list)
