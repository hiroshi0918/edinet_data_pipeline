"""ダッシュボード共通定数 — 指標ラベル・テーブル名・カラー定義."""

from __future__ import annotations

from edinet_pipeline.analytics import (
    ANALYTICS_SCHEMA,
    COMPANY_YEAR_METRICS_DATASET,
    METRIC_EVIDENCE_DATASET,
)

# DuckDB テーブル名 (analytics.py の定数から導出)
TABLE_COMPANY_YEAR_METRICS = f"{ANALYTICS_SCHEMA}.{COMPANY_YEAR_METRICS_DATASET}"
TABLE_METRIC_EVIDENCE = f"{ANALYTICS_SCHEMA}.{METRIC_EVIDENCE_DATASET}"

# 指標ラベル (カラム名 → 日本語表示名)
FINANCIAL_METRIC_LABELS: dict[str, str] = {
    "sales": "売上高",
    "operating_profit": "営業利益",
    "net_profit": "純利益",
    "employee_count": "従業員数",
}

HC_METRIC_LABELS: dict[str, str] = {
    "female_manager_ratio": "女性管理職比率 (%)",
    "male_childcare_leave_ratio": "男性育休取得率 (%)",
    "gender_wage_gap": "男女賃金格差 (%)",
}

# HC はパーセント表記なしの短縮版 — ヒートマップや充足率グラフで使用
ALL_METRIC_LABELS: dict[str, str] = {
    **FINANCIAL_METRIC_LABELS,
    "female_manager_ratio": "女性管理職比率",
    "male_childcare_leave_ratio": "男性育休取得率",
    "gender_wage_gap": "男女賃金格差",
}

ALL_METRIC_COLUMNS: list[str] = list(ALL_METRIC_LABELS.keys())

# data.py のバリデーションに使う許可済み指標セット
ALLOWED_ALL_METRICS: set[str] = set(ALL_METRIC_LABELS.keys())
ALLOWED_HC_METRICS: set[str] = set(HC_METRIC_LABELS.keys())

# ステータスカラーマップ
STATUS_COLOR_MAP: dict[str, str] = {
    "processed": "#2ecc71",
    "pending": "#f39c12",
    "failed": "#e74c3c",
    "skipped": "#95a5a6",
    "processing": "#3498db",
}

# HC トレンド列のラベルマップ (既存定数から導出)
HC_TREND_LABEL_MAP: dict[str, str] = {
    f"avg_{k}": v for k, v in ALL_METRIC_LABELS.items() if k in HC_METRIC_LABELS
}

# --- 次元ラベル (v0.3 で追加) -------------------------------------- #

# 開示範囲 (scope) のラベル
SCOPE_LABELS: dict[str, str] = {
    "reporting_company": "提出会社",
    "consolidated_subsidiary": "連結子会社",
}

# 労働者区分 (worker_type) のラベル
WORKER_TYPE_LABELS: dict[str, str] = {
    "all": "全労働者",
    "regular": "正規雇用",
    "non_regular": "非正規雇用",
}

# デフォルト次元 (サイドバー初期値・analytics 既定行を表示)
DEFAULT_SCOPE = "reporting_company"
DEFAULT_WORKER_TYPE = "all"
