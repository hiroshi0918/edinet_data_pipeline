"""dashboard/datasource.py のテスト — ローカル優先・Releases フォールバックの解決ロジック.

ネットワークには一切アクセスせず、requests.head / requests.get を monkeypatch で差し替える。
@st.cache_data の TTL キャッシュは各テストの前後で clear して独立性を担保する。
"""

from __future__ import annotations

from pathlib import Path

import pytest

from edinet_pipeline.config import DEFAULT_DUCKDB_PATH
from edinet_pipeline.dashboard import datasource
from edinet_pipeline.dashboard.datasource import (
    DuckdbDownloadError,
    _local_duckdb_path,
    _sanitize_version,
    ensure_duckdb_file,
)

# ------------------------------------------------------------------ #
#  requests のフェイク (ネットワーク不要)
# ------------------------------------------------------------------ #


class _FakeHeadResponse:
    def __init__(self, status_code: int = 200, headers: dict[str, str] | None = None) -> None:
        self.status_code = status_code
        self.headers = headers or {}


class _FakeGetResponse:
    """requests.get(stream=True) の戻り値を模したコンテキストマネージャ."""

    def __init__(
        self,
        status_code: int = 200,
        content: bytes = b"DUCKDB-CONTENT",
        headers: dict[str, str] | None = None,
    ) -> None:
        self.status_code = status_code
        self._content = content
        self.headers = headers or {}

    def __enter__(self) -> _FakeGetResponse:
        return self

    def __exit__(self, *args: object) -> bool:
        return False

    def iter_content(self, chunk_size: int = 1) -> list[bytes]:
        return [self._content]


@pytest.fixture(autouse=True)
def _clear_version_cache():
    """HEAD バージョンの TTL キャッシュをテスト間で必ずリセットする."""
    datasource._cached_remote_version.clear()
    yield
    datasource._cached_remote_version.clear()


@pytest.fixture()
def cache_dir(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """ダウンロードキャッシュ先を tmp に固定する."""
    target = tmp_path / "cache"
    monkeypatch.setenv("EDINET_DUCKDB_CACHE_DIR", str(target))
    return target


@pytest.fixture()
def no_local_file(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """ローカル DuckDB が存在しない状態 (= リモート経路に入る) を作る."""
    monkeypatch.setenv("EDINET_DUCKDB_PATH", str(tmp_path / "nonexistent.duckdb"))


def _set_head(monkeypatch: pytest.MonkeyPatch, response: object) -> None:
    monkeypatch.setattr(datasource.requests, "head", lambda *a, **k: response)


def _set_get(monkeypatch: pytest.MonkeyPatch, response: object, counter: list[int]) -> None:
    def _fake_get(*args: object, **kwargs: object) -> object:
        counter[0] += 1
        return response

    monkeypatch.setattr(datasource.requests, "get", _fake_get)


# ------------------------------------------------------------------ #
#  _local_duckdb_path / _sanitize_version (旧 TestGetDuckdbPath の移設先)
# ------------------------------------------------------------------ #


class TestLocalDuckdbPath:
    def test_default_path(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("EDINET_DUCKDB_PATH", raising=False)
        assert _local_duckdb_path() == Path(DEFAULT_DUCKDB_PATH)

    def test_custom_path_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("EDINET_DUCKDB_PATH", "/custom/path/analytics.duckdb")
        assert _local_duckdb_path() == Path("/custom/path/analytics.duckdb")


class TestSanitizeVersion:
    def test_strips_weak_validator_and_quotes(self) -> None:
        assert _sanitize_version('W/"abc-123"') == "abc-123"

    def test_strips_plain_quotes(self) -> None:
        assert _sanitize_version('"deadbeef"') == "deadbeef"

    def test_replaces_unsafe_chars(self) -> None:
        # Last-Modified 形式のスペース・カンマ・コロンは _ に置換される
        assert _sanitize_version("Wed, 21 Oct 2015 07:28:00 GMT") == (
            "Wed__21_Oct_2015_07_28_00_GMT"
        )

    def test_empty_falls_back_to_unknown(self) -> None:
        assert _sanitize_version('""') == "unknown"


# ------------------------------------------------------------------ #
#  ensure_duckdb_file のシナリオ
# ------------------------------------------------------------------ #


def test_local_file_returns_directly_without_head(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """ローカル版が存在すれば HEAD を一切呼ばずそのパスを返すこと."""
    local = tmp_path / "edinet_analytics.duckdb"
    local.write_bytes(b"LOCAL")
    monkeypatch.setenv("EDINET_DUCKDB_PATH", str(local))

    def _fail_head(*args: object, **kwargs: object) -> object:
        raise AssertionError("HEAD must not be called when the local file exists")

    monkeypatch.setattr(datasource.requests, "head", _fail_head)

    assert ensure_duckdb_file() == local


def test_etag_triggers_versioned_download(
    monkeypatch: pytest.MonkeyPatch, cache_dir: Path, no_local_file: None
) -> None:
    """ETag を取得し、その版でキャッシュへ DL すること."""
    _set_head(monkeypatch, _FakeHeadResponse(headers={"ETag": '"abc123"'}))
    get_calls = [0]
    _set_get(monkeypatch, _FakeGetResponse(content=b"V1"), get_calls)

    result = ensure_duckdb_file()

    assert result == cache_dir / "edinet_analytics-abc123.duckdb"
    assert result.read_bytes() == b"V1"
    assert get_calls[0] == 1


def test_same_etag_skips_redownload(
    monkeypatch: pytest.MonkeyPatch, cache_dir: Path, no_local_file: None
) -> None:
    """同一 ETag の 2 回目は再ダウンロードしないこと."""
    _set_head(monkeypatch, _FakeHeadResponse(headers={"ETag": '"abc123"'}))
    get_calls = [0]
    _set_get(monkeypatch, _FakeGetResponse(content=b"V1"), get_calls)

    first = ensure_duckdb_file()
    datasource._cached_remote_version.clear()  # TTL を無効化し HEAD を再評価させる
    second = ensure_duckdb_file()

    assert first == second
    assert get_calls[0] == 1  # 2 回目はファイルが既存なので DL されない


def test_etag_change_downloads_new_and_cleans_old(
    monkeypatch: pytest.MonkeyPatch, cache_dir: Path, no_local_file: None
) -> None:
    """ETag が変わると新ファイルを DL し、旧版を掃除すること."""
    get_calls = [0]
    _set_head(monkeypatch, _FakeHeadResponse(headers={"ETag": '"v1"'}))
    _set_get(monkeypatch, _FakeGetResponse(content=b"V1"), get_calls)
    old = ensure_duckdb_file()
    assert old == cache_dir / "edinet_analytics-v1.duckdb"

    datasource._cached_remote_version.clear()
    _set_head(monkeypatch, _FakeHeadResponse(headers={"ETag": '"v2"'}))
    _set_get(monkeypatch, _FakeGetResponse(content=b"V2"), get_calls)
    new = ensure_duckdb_file()

    assert new == cache_dir / "edinet_analytics-v2.duckdb"
    assert new.read_bytes() == b"V2"
    assert not old.exists()  # 旧版は掃除されている
    assert get_calls[0] == 2


def test_etag_absent_uses_last_modified(
    monkeypatch: pytest.MonkeyPatch, cache_dir: Path, no_local_file: None
) -> None:
    """ETag が無ければ Last-Modified をバージョンに使うこと."""
    _set_head(
        monkeypatch,
        _FakeHeadResponse(headers={"Last-Modified": "Wed, 21 Oct 2015 07:28:00 GMT"}),
    )
    get_calls = [0]
    _set_get(monkeypatch, _FakeGetResponse(content=b"LM"), get_calls)

    result = ensure_duckdb_file()

    assert result == cache_dir / "edinet_analytics-Wed__21_Oct_2015_07_28_00_GMT.duckdb"


def test_head_failure_falls_back_to_cache(
    monkeypatch: pytest.MonkeyPatch, cache_dir: Path, no_local_file: None
) -> None:
    """HEAD 失敗時はキャッシュ済み最新ファイルにフォールバックすること."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    cached = cache_dir / "edinet_analytics-cached.duckdb"
    cached.write_bytes(b"CACHED")

    # ネットワークエラーを模して None を返させる
    def _raise_head(*args: object, **kwargs: object) -> object:
        raise datasource.requests.RequestException("boom")

    monkeypatch.setattr(datasource.requests, "head", _raise_head)

    assert ensure_duckdb_file() == cached


def test_truncated_download_raises_and_leaves_no_file(
    monkeypatch: pytest.MonkeyPatch, cache_dir: Path, no_local_file: None
) -> None:
    """Content-Length と実バイト数が食い違う (早期 EOF) 場合は確定配置せず例外を投げること."""
    _set_head(monkeypatch, _FakeHeadResponse(headers={"ETag": '"trunc"'}))
    get_calls = [0]
    # 本体は 2 バイトだが Content-Length は 999 → 不完全とみなす
    _set_get(
        monkeypatch,
        _FakeGetResponse(content=b"AB", headers={"Content-Length": "999"}),
        get_calls,
    )

    with pytest.raises(DuckdbDownloadError, match="Incomplete download"):
        ensure_duckdb_file()

    # 破損ファイルも .tmp 残骸も残っていないこと
    assert list(cache_dir.glob("*.duckdb")) == []
    assert list(cache_dir.glob("*.tmp")) == []


def test_head_failure_without_cache_raises(
    monkeypatch: pytest.MonkeyPatch, cache_dir: Path, no_local_file: None
) -> None:
    """HEAD 失敗かつキャッシュ皆無なら DuckdbDownloadError を送出すること."""
    monkeypatch.setattr(
        datasource.requests, "head", lambda *a, **k: _FakeHeadResponse(status_code=503)
    )

    with pytest.raises(DuckdbDownloadError):
        ensure_duckdb_file()
