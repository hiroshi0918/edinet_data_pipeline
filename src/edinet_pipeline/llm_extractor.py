"""ローカルLLM (Ollama) を使った人的資本指標のフォールバック抽出.

要素IDマッチ・項目名マッチで取得できなかった書類の「従業員の状況
[テキストブロック]」から、qwen3.5:9b 等のモデルで JSON 形式で値を抽出する。

設計方針:
  - 厳密なフォールバック専用 — Layer 1/2 で値が取れた指標は LLM に渡さない
  - format=json でレスポンスを構造化強制 (Ollama の JSON モード)
  - SHA256(text+model) によるDBキャッシュ — 同一テキストの2回目以降は無料
  - タイムアウト/JSONパース失敗時はパイプラインを止めず、空dict を返す
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass

import psycopg2
import requests

from edinet_pipeline.config import Settings
from edinet_pipeline.logging_utils import log_event
from edinet_pipeline.models import (
    SCOPE_REPORTING_COMPANY,
    WORKER_TYPE_ALL,
    WORKER_TYPE_NON_REGULAR,
    WORKER_TYPE_REGULAR,
    HumanMetricRecord,
)

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------ #
#  LLM プロンプト定義
# ------------------------------------------------------------------ #

PROMPT_TEMPLATE = """あなたは有価証券報告書の解析アシスタントです。
以下の「従業員の状況」セクションのテキストから、提出会社（連結ではなく単体）の
次の指標を％（パーセント）の数値として抽出し、JSONで返してください。

抽出対象:
- female_manager_ratio: 管理職に占める女性労働者の割合 (%)
- male_childcare_leave_ratio: 男性労働者の育児休業取得率 (%)
- gender_wage_gap_all: 全労働者の男女の賃金の差異 (%)
- gender_wage_gap_regular: 正規雇用労働者の男女の賃金の差異 (%)
- gender_wage_gap_non_regular: 非正規・パート・有期労働者の男女の賃金の差異 (%)

ルール:
- 値がテキスト中に明示されていない場合は null
- 0〜200 の範囲外の値は null (異常値)
- 連結子会社のみの値しかない指標は null（提出会社の値が必要）
- 必ず以下のキー全てを含むJSONのみを返す

テキスト:
\"\"\"
{text}
\"\"\"

JSON:"""


@dataclass(frozen=True)
class LlmExtractionResult:
    """LLM抽出結果 — HumanMetricRecord のリストと、cache hit かどうかのフラグ."""

    records: list[HumanMetricRecord]
    cache_hit: bool


# ------------------------------------------------------------------ #
#  キャッシュ層 (llm_extraction_cache テーブル)
# ------------------------------------------------------------------ #


def _compute_cache_key(text: str, model: str) -> str:
    """テキストとモデル名の組み合わせから SHA256 キャッシュキーを生成."""
    raw = f"{model}\x00{text}".encode()
    return hashlib.sha256(raw).hexdigest()


def _load_from_cache(connection: psycopg2.extensions.connection, cache_key: str) -> dict | None:
    """キャッシュテーブルから過去の結果を取得 (なければ None)."""
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT result FROM llm_extraction_cache WHERE text_hash = %s",
            (cache_key,),
        )
        row = cursor.fetchone()
    return row[0] if row else None


def _save_to_cache(
    connection: psycopg2.extensions.connection,
    *,
    cache_key: str,
    model: str,
    result: dict,
) -> None:
    """LLM結果をキャッシュテーブルに保存 (ON CONFLICT で冪等)."""
    with connection.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO llm_extraction_cache (text_hash, model, result)
            VALUES (%s, %s, %s::jsonb)
            ON CONFLICT (text_hash) DO UPDATE SET
                model = EXCLUDED.model,
                result = EXCLUDED.result
            """,
            (cache_key, model, json.dumps(result, ensure_ascii=False)),
        )


# ------------------------------------------------------------------ #
#  Ollama 呼び出し
# ------------------------------------------------------------------ #


def _call_ollama(text: str, *, settings: Settings) -> dict | None:
    """Ollama API を呼び出して JSON レスポンスを返す.

    失敗時 (タイムアウト/接続エラー/JSONパース失敗) は None を返してパイプラインを止めない。
    """
    payload = {
        "model": settings.llm_model,
        "prompt": PROMPT_TEMPLATE.format(text=text[:6000]),  # 入力長を制限
        "format": "json",
        "stream": False,
        "options": {"temperature": 0.0},  # 決定論的に
    }
    try:
        response = requests.post(
            settings.llm_endpoint,
            json=payload,
            timeout=settings.llm_timeout,
        )
    except requests.RequestException as exc:
        log_event(logger, "warning", "llm_request_failed", error=str(exc))
        return None

    if response.status_code != 200:
        log_event(
            logger, "warning", "llm_http_error", status_code=response.status_code,
        )
        return None

    try:
        outer = response.json()
        inner_text = outer.get("response", "")
        return json.loads(inner_text)
    except (ValueError, KeyError) as exc:
        log_event(logger, "warning", "llm_response_parse_failed", error=str(exc))
        return None


# ------------------------------------------------------------------ #
#  結果 → HumanMetricRecord 変換
# ------------------------------------------------------------------ #


def _coerce_percentage(value: object) -> float | None:
    """LLMの応答を % の float に変換. 異常値は None."""
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not 0.0 <= number <= 200.0:
        return None
    return number


def llm_result_to_records(payload: dict) -> list[HumanMetricRecord]:
    """LLMの JSON 応答を (scope, worker_type) ごとの HumanMetricRecord リストに変換.

    LLMには提出会社の値のみを抽出させるため、scope は常に reporting_company。
    worker_type は gender_wage_gap_* キーから推定する。
    """
    female_mgr = _coerce_percentage(payload.get("female_manager_ratio"))
    male_childcare = _coerce_percentage(payload.get("male_childcare_leave_ratio"))
    wage_all = _coerce_percentage(payload.get("gender_wage_gap_all"))
    wage_regular = _coerce_percentage(payload.get("gender_wage_gap_regular"))
    wage_non_regular = _coerce_percentage(payload.get("gender_wage_gap_non_regular"))

    records: list[HumanMetricRecord] = []
    # 全労働者行: 法定3指標がここに集約
    if any(v is not None for v in (female_mgr, male_childcare, wage_all)):
        records.append(
            HumanMetricRecord(
                scope=SCOPE_REPORTING_COMPANY,
                worker_type=WORKER_TYPE_ALL,
                female_manager_ratio=female_mgr,
                male_childcare_leave_ratio=male_childcare,
                gender_wage_gap=wage_all,
            )
        )
    # 正規雇用 / 非正規雇用は賃金差異のみ
    if wage_regular is not None:
        records.append(
            HumanMetricRecord(
                scope=SCOPE_REPORTING_COMPANY,
                worker_type=WORKER_TYPE_REGULAR,
                gender_wage_gap=wage_regular,
            )
        )
    if wage_non_regular is not None:
        records.append(
            HumanMetricRecord(
                scope=SCOPE_REPORTING_COMPANY,
                worker_type=WORKER_TYPE_NON_REGULAR,
                gender_wage_gap=wage_non_regular,
            )
        )
    return records


# ------------------------------------------------------------------ #
#  公開 API
# ------------------------------------------------------------------ #


def extract_via_llm(
    text: str,
    *,
    settings: Settings,
    cache_connection: psycopg2.extensions.connection | None = None,
) -> LlmExtractionResult:
    """テキストブロックから LLM で人的資本指標を抽出する.

    Args:
        text: 「従業員の状況 [テキストブロック]」の全文
        settings: Settings (llm_endpoint / llm_model / llm_timeout を参照)
        cache_connection: キャッシュ参照/書き込み用DB接続 (None ならキャッシュ無効)

    Returns:
        LlmExtractionResult (records は空リストの可能性あり)
    """
    if not settings.llm_enabled:
        return LlmExtractionResult(records=[], cache_hit=False)
    if not text or not text.strip():
        return LlmExtractionResult(records=[], cache_hit=False)

    cache_key = _compute_cache_key(text, settings.llm_model)

    # キャッシュ参照
    if cache_connection is not None:
        cached = _load_from_cache(cache_connection, cache_key)
        if cached is not None:
            return LlmExtractionResult(
                records=llm_result_to_records(cached),
                cache_hit=True,
            )

    # Ollama 呼び出し
    payload = _call_ollama(text, settings=settings)
    if payload is None:
        return LlmExtractionResult(records=[], cache_hit=False)

    # キャッシュ保存
    if cache_connection is not None:
        try:
            _save_to_cache(
                cache_connection, cache_key=cache_key,
                model=settings.llm_model, result=payload,
            )
            cache_connection.commit()
        except psycopg2.Error as exc:
            # キャッシュ保存失敗はパイプラインを止めない
            log_event(logger, "warning", "llm_cache_save_failed", error=str(exc))
            cache_connection.rollback()

    return LlmExtractionResult(
        records=llm_result_to_records(payload),
        cache_hit=False,
    )
