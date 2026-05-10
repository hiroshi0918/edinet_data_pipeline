"""llm_extractor モジュールのテスト — Ollama 呼び出し / キャッシュ / 結果変換 の検証.

実際の Ollama サーバへの接続は行わず、requests.post を mock する。
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from edinet_pipeline.config import Settings
from edinet_pipeline.llm_extractor import (
    _coerce_percentage,
    _compute_cache_key,
    extract_via_llm,
    llm_result_to_records,
)
from edinet_pipeline.models import (
    SCOPE_REPORTING_COMPANY,
    WORKER_TYPE_ALL,
    WORKER_TYPE_NON_REGULAR,
    WORKER_TYPE_REGULAR,
)


def _make_settings(*, llm_enabled: bool = True) -> Settings:
    """テスト用の Settings — DB/API キーはダミー、LLM 関連は実値."""
    return Settings(
        edinet_api_key="dummy",
        database_url="postgresql://user:pass@localhost/dummy",
        llm_enabled=llm_enabled,
        llm_endpoint="http://localhost:11434/api/generate",
        llm_model="qwen3.5:9b",
        llm_timeout=10,
    )


# ------------------------------------------------------------------ #
#  _coerce_percentage: 異常値の除外
# ------------------------------------------------------------------ #


def test_coerce_percentage_accepts_valid_range() -> None:
    assert _coerce_percentage(0) == 0.0
    assert _coerce_percentage(50.5) == 50.5
    assert _coerce_percentage(200) == 200.0
    assert _coerce_percentage("12.5") == 12.5  # 文字列も受け付ける


def test_coerce_percentage_rejects_out_of_range_or_invalid() -> None:
    assert _coerce_percentage(None) is None
    assert _coerce_percentage(-1) is None
    assert _coerce_percentage(201) is None
    assert _coerce_percentage("not a number") is None
    assert _coerce_percentage("abc") is None


# ------------------------------------------------------------------ #
#  _compute_cache_key: キャッシュキーの決定論性
# ------------------------------------------------------------------ #


def test_cache_key_is_deterministic_per_text_and_model() -> None:
    """同じ入力なら同じキー、モデル違いなら別キー."""
    text = "従業員の状況テキスト..."
    k1 = _compute_cache_key(text, "qwen3.5:9b")
    k2 = _compute_cache_key(text, "qwen3.5:9b")
    k3 = _compute_cache_key(text, "qwen2:7b")
    assert k1 == k2
    assert k1 != k3
    assert len(k1) == 64  # SHA256 hex


# ------------------------------------------------------------------ #
#  llm_result_to_records: JSON → HumanMetricRecord リスト変換
# ------------------------------------------------------------------ #


def test_llm_result_to_records_groups_wage_gap_by_worker_type() -> None:
    """賃金差異は worker_type 別に別レコード、3指標は all 行に集約."""
    payload = {
        "female_manager_ratio": 5.2,
        "male_childcare_leave_ratio": 36.4,
        "gender_wage_gap_all": 68.2,
        "gender_wage_gap_regular": 68.6,
        "gender_wage_gap_non_regular": 61.7,
    }
    records = llm_result_to_records(payload)
    by_key = {(r.scope, r.worker_type): r for r in records}

    all_record = by_key[(SCOPE_REPORTING_COMPANY, WORKER_TYPE_ALL)]
    assert all_record.female_manager_ratio == 5.2
    assert all_record.male_childcare_leave_ratio == 36.4
    assert all_record.gender_wage_gap == 68.2

    regular = by_key[(SCOPE_REPORTING_COMPANY, WORKER_TYPE_REGULAR)]
    assert regular.gender_wage_gap == 68.6
    assert regular.female_manager_ratio is None  # 集約されていない

    non_regular = by_key[(SCOPE_REPORTING_COMPANY, WORKER_TYPE_NON_REGULAR)]
    assert non_regular.gender_wage_gap == 61.7


def test_llm_result_to_records_skips_when_all_null() -> None:
    """全指標が None なら該当 worker_type のレコードを作らない."""
    payload = {
        "female_manager_ratio": None,
        "male_childcare_leave_ratio": None,
        "gender_wage_gap_all": None,
        "gender_wage_gap_regular": 68.6,  # これだけ非 None
    }
    records = llm_result_to_records(payload)
    assert len(records) == 1
    assert records[0].worker_type == WORKER_TYPE_REGULAR


# ------------------------------------------------------------------ #
#  extract_via_llm: Ollama 呼び出しの統合 (mock)
# ------------------------------------------------------------------ #


def _mock_ollama_response(json_payload: dict) -> MagicMock:
    """Ollama API レスポンスを模した Response オブジェクトを作成."""
    response = MagicMock()
    response.status_code = 200
    response.json.return_value = {"response": json.dumps(json_payload)}
    return response


def test_extract_via_llm_returns_records_when_enabled_and_response_valid() -> None:
    """正常系: enabled かつレスポンス OK で records が返る."""
    settings = _make_settings(llm_enabled=True)
    payload = {
        "female_manager_ratio": 5.2, "male_childcare_leave_ratio": 36.4,
        "gender_wage_gap_all": 68.2, "gender_wage_gap_regular": None,
        "gender_wage_gap_non_regular": None,
    }
    with patch("edinet_pipeline.llm_extractor.requests.post") as mock_post:
        mock_post.return_value = _mock_ollama_response(payload)
        result = extract_via_llm("従業員の状況...", settings=settings)

    assert result.cache_hit is False
    assert len(result.records) == 1
    assert result.records[0].female_manager_ratio == 5.2


def test_extract_via_llm_skipped_when_disabled() -> None:
    """LLM 無効化時は空結果を返し、Ollama 呼び出しが発生しない."""
    settings = _make_settings(llm_enabled=False)
    with patch("edinet_pipeline.llm_extractor.requests.post") as mock_post:
        result = extract_via_llm("text", settings=settings)
    assert result.records == []
    mock_post.assert_not_called()


def test_extract_via_llm_returns_empty_on_request_failure() -> None:
    """Ollama 接続失敗 (RequestException) でも例外を伝播しない."""
    import requests

    settings = _make_settings(llm_enabled=True)
    with patch("edinet_pipeline.llm_extractor.requests.post") as mock_post:
        mock_post.side_effect = requests.ConnectionError("connection refused")
        result = extract_via_llm("text", settings=settings)
    assert result.records == []
    assert result.cache_hit is False


def test_extract_via_llm_returns_empty_on_invalid_json() -> None:
    """Ollama が壊れた JSON を返しても例外を伝播せず空結果."""
    settings = _make_settings(llm_enabled=True)
    bad_response = MagicMock()
    bad_response.status_code = 200
    bad_response.json.return_value = {"response": "not valid json {"}
    with patch("edinet_pipeline.llm_extractor.requests.post") as mock_post:
        mock_post.return_value = bad_response
        result = extract_via_llm("text", settings=settings)
    assert result.records == []


def test_extract_via_llm_uses_cache_when_available() -> None:
    """キャッシュ接続を渡せば、2回目の呼び出しは Ollama を叩かない."""
    settings = _make_settings(llm_enabled=True)
    cached_payload = {
        "female_manager_ratio": 10.0, "male_childcare_leave_ratio": None,
        "gender_wage_gap_all": None, "gender_wage_gap_regular": None,
        "gender_wage_gap_non_regular": None,
    }

    # mock の DB 接続: SELECT で結果あり
    cursor_mock = MagicMock()
    cursor_mock.__enter__ = MagicMock(return_value=cursor_mock)
    cursor_mock.__exit__ = MagicMock(return_value=False)
    cursor_mock.fetchone.return_value = (cached_payload,)
    conn_mock = MagicMock()
    conn_mock.cursor.return_value = cursor_mock

    with patch("edinet_pipeline.llm_extractor.requests.post") as mock_post:
        result = extract_via_llm("text", settings=settings, cache_connection=conn_mock)

    assert result.cache_hit is True
    assert result.records[0].female_manager_ratio == 10.0
    mock_post.assert_not_called()  # キャッシュヒットなので Ollama 不要
