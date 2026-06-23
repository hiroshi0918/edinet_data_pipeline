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
ALLOWED_FINANCIAL_METRICS: set[str] = set(FINANCIAL_METRIC_LABELS.keys())

# 単一企業ランキング・財務軸併記で使う「意味のある」HC 2 指標。
# 男性育休取得率は集計タイミングで >100% 等のノイズが出るため、単一企業の
# ランキングや併記列からは外す (年度ごとの業種分布=箱ひげ図でのみ扱う)。
RANKING_HC_METRICS: tuple[str, ...] = ("female_manager_ratio", "gender_wage_gap")

# 規模×人的資本ページで使う財務軸 (純利益は規模指標として弱いため除く)
SIZE_AXIS_METRICS: tuple[str, ...] = ("sales", "operating_profit", "employee_count")

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

# Company Spotlight: 「理想クラスタ」の閾値定義
# 3 つの HC 指標すべてが業界の上位四分位 (P75) 以上、
# かつ営業利益率が業界の中央値 (P50) 以上の企業群を「理想クラスタ」と定義する。
IDEAL_CLUSTER_THRESHOLDS = {
    "hc_percentile": 75,
    "operating_margin_percentile": 50,
}

# 男性育休取得率の表示クリップ範囲 (%)
# EDINET 正本は 100% 超 (集計ミス疑い) を含むが、グラフは 0-100% にクリップする。
RATIO_DISPLAY_MIN = 0
RATIO_DISPLAY_MAX = 100

# --- ダッシュボード v0.4 改修で追加 -------------------------------------- #

# 売上規模階層 (円・連結子会社含む実額)
# 業種パラドックス (規模×女性管理職比率) や規模別の指標分布を可視化するための階層。
# 上端を None としているのは「1T以上」をDuckDB側で `sales >= 1e12` のように表現するため。
SALES_TIER_BOUNDARIES: list[tuple[float | None, float | None, str]] = [
    (None, 1_000_000_000, "1B未満"),
    (1_000_000_000, 10_000_000_000, "1B-10B"),
    (10_000_000_000, 100_000_000_000, "10B-100B"),
    (100_000_000_000, 1_000_000_000_000, "100B-1T"),
    (1_000_000_000_000, None, "1T以上"),
]
SALES_TIER_ORDER: list[str] = [tier[2] for tier in SALES_TIER_BOUNDARIES]


def sales_tier_case_sql(column: str = "sales") -> str:
    """売上カラムを SALES_TIER_BOUNDARIES に従い階層ラベルに変換する CASE 式を返す.

    DuckDB クエリ内で `{sales_tier_case_sql()} AS sales_tier` のように埋め込む。
    SQL インジェクション防止のため、column 引数はリテラル文字列のみ受け取る前提。
    """
    parts = ["CASE"]
    for low, high, label in SALES_TIER_BOUNDARIES:
        if low is None:
            parts.append(f"  WHEN {column} < {int(high)} THEN '{label}'")
        elif high is None:
            parts.append(f"  WHEN {column} >= {int(low)} THEN '{label}'")
        else:
            parts.append(f"  WHEN {column} < {int(high)} THEN '{label}'")
    parts.append("  ELSE NULL")
    parts.append("END")
    return "\n".join(parts)


# プリセット定義 (財務指標ページのデフォルト企業選択)
PRESET_LABELS: dict[str, str] = {
    "industry_rep": "業種代表（各業種の売上TOP1）",
    "sales_top10": "売上TOP10",
    "operating_margin_top10": "営業利益率TOP10",
    "growth_top10": "売上成長率TOP10",
    "custom": "カスタム（自分で選ぶ）",
}
DEFAULT_PRESET: str = "industry_rep"

# 概要ページのデータストーリーで使う「業種格差を見たい指標」のデフォルト
DEFAULT_HIGHLIGHT_METRIC: str = "female_manager_ratio"

# 業種比較・改善率ランキングで一度に表示する企業数の上限
DEFAULT_RANKING_TOP_N: int = 10

# 業種フィルタを「未指定」とみなす sentinel 値 (空リスト指定では全業種を意味する)
INDUSTRY_FILTER_ALL: list[str] = []
