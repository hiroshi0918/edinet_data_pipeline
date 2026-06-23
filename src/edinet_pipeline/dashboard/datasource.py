"""ダッシュボードの DuckDB データソース解決 — ローカル優先・無ければ Releases から取得.

公開環境 (Streamlit Community Cloud) では DuckDB を git に同梱せず、GitHub Releases の
固定タグ `data-latest` に添付したアセットを実行時にダウンロードして使う。鮮度管理は
「リモートの ETag をバージョンとしてファイル名へ埋め込み + HEAD チェックを 1 時間 TTL で
キャッシュ」する方式を採る。ファイルパスが版ごとに変わることで data.get_connection の
`@st.cache_resource` キーが自然に切り替わるため、data.py のクエリ関数は一切変更不要。
最悪鮮度遅延 ≈ 65 分 (HEAD TTL 60 分 + query TTL 5 分) で週次更新には十分。

ローカル開発では従来どおり `edinet export-analytics` が生成した
artifacts/analytics/edinet_analytics.duckdb をそのまま使う (ネットワーク不要)。
"""

from __future__ import annotations

import logging
import os
import re
import tempfile
import uuid
from pathlib import Path

import requests
import streamlit as st

from edinet_pipeline.config import DEFAULT_DUCKDB_PATH

logger = logging.getLogger(__name__)

# GitHub Releases の固定タグ data-latest に添付された DuckDB アセット URL。
# 週次更新スクリプトが `gh release upload data-latest ... --clobber` で上書きする運用。
DEFAULT_DUCKDB_URL = (
    "https://github.com/hiroshi0918/edinet_data_pipeline/"
    "releases/download/data-latest/edinet_analytics.duckdb"
)

_CACHE_FILE_PREFIX = "edinet_analytics-"
_CACHE_FILE_SUFFIX = ".duckdb"
_HEAD_TIMEOUT_SECONDS = 15
_DOWNLOAD_TIMEOUT_SECONDS = 120
_DOWNLOAD_CHUNK_BYTES = 256 * 1024
# キャッシュに保持する最新バージョン数。HEAD 失敗時のフォールバックは最新 1 件で足りるため、
# 新版取得時に旧版を掃除してディスクを最小限に保つ。
_KEEP_CACHED_VERSIONS = 1


class DuckdbDownloadError(RuntimeError):
    """リモート DuckDB の取得に失敗し、利用可能なキャッシュも無い場合のエラー."""


def _duckdb_url() -> str:
    """ダウンロード元 URL (EDINET_DUCKDB_URL 環境変数で上書き可)."""
    return os.environ.get("EDINET_DUCKDB_URL", DEFAULT_DUCKDB_URL)


def _local_duckdb_path() -> Path:
    """ローカル開発用の DuckDB パス (EDINET_DUCKDB_PATH 環境変数 or 既定の artifacts パス)."""
    return Path(os.environ.get("EDINET_DUCKDB_PATH", DEFAULT_DUCKDB_PATH))


def _cache_dir() -> Path:
    """ダウンロードキャッシュ用ディレクトリ.

    EDINET_DUCKDB_CACHE_DIR があればそれを、無ければ OS の一時ディレクトリ配下の
    `edinet_dashboard/` を使う。Streamlit Cloud の /tmp は揮発するが、その場合も
    再起動時に再 DL するだけで自己回復する。
    """
    override = os.environ.get("EDINET_DUCKDB_CACHE_DIR")
    base = Path(override) if override else Path(tempfile.gettempdir()) / "edinet_dashboard"
    base.mkdir(parents=True, exist_ok=True)
    return base


def _sanitize_version(raw: str) -> str:
    """ETag / Last-Modified をファイル名に安全な識別子へ変換する.

    ETag は W/"..." の弱い検証子プレフィックスや引用符を含むため除去し、
    ファイル名に使えない文字を _ に置換する。
    """
    value = raw.strip()
    if value.startswith("W/"):
        value = value[2:]
    value = value.strip('"')
    safe = re.sub(r"[^A-Za-z0-9._-]", "_", value)
    return safe[:120] or "unknown"


def _remote_version(url: str) -> str | None:
    """HEAD リクエストでリモート版の識別子を得る (ETag 優先、無ければ Last-Modified).

    ネットワークエラー・非 200・識別ヘッダ皆無のいずれでも None を返す (失敗を握りつぶさず
    呼び出し側のフォールバック経路に委ねる)。
    """
    try:
        response = requests.head(url, timeout=_HEAD_TIMEOUT_SECONDS, allow_redirects=True)
    except requests.RequestException as exc:
        logger.warning("HEAD request failed for %s: %s", url, exc)
        return None
    if response.status_code != 200:
        logger.warning("HEAD request returned HTTP %s for %s", response.status_code, url)
        return None
    etag = response.headers.get("ETag")
    if etag:
        return _sanitize_version(etag)
    last_modified = response.headers.get("Last-Modified")
    if last_modified:
        return _sanitize_version(last_modified)
    return None


@st.cache_data(ttl=3600)
def _cached_remote_version(url: str) -> str | None:
    """_remote_version を 1 時間キャッシュし、HEAD の連打を防ぐ."""
    return _remote_version(url)


def _parse_content_length(raw: str | None) -> int | None:
    """Content-Length ヘッダを int に変換する (欠落・不正値なら検証をスキップする None)."""
    if raw is None:
        return None
    try:
        return int(raw)
    except ValueError:
        return None


def _download_to(url: str, destination: Path) -> None:
    """url をストリーミング取得し .tmp 経由で destination へアトミックに配置する.

    analytics.export_duckdb_snapshot と同じ tmp → replace パターン。失敗時は tmp を
    掃除し DuckdbDownloadError を送出する (中途半端なファイルを残さない)。

    tmp ファイル名はプロセス横断で一意にする。Streamlit Cloud は再起動直後に同一スク
    リプトを並行実行することがあり、決定的な `{name}.tmp` だと複数スレッドが同じ tmp を
    奪い合い、先に replace した側が tmp を消費して後続が ENOENT で落ちる。各 DL 試行に
    固有の tmp を割り当てれば、各自の replace が成功し最後の書き手の正しいファイルが残る。
    """
    tmp_path = destination.parent / (
        f"{destination.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp"
    )
    try:
        with requests.get(url, stream=True, timeout=_DOWNLOAD_TIMEOUT_SECONDS) as response:
            if response.status_code != 200:
                raise DuckdbDownloadError(
                    f"Download failed for {url}: HTTP {response.status_code}"
                )
            expected_bytes = _parse_content_length(response.headers.get("Content-Length"))
            written_bytes = 0
            with tmp_path.open("wb") as handle:
                for chunk in response.iter_content(chunk_size=_DOWNLOAD_CHUNK_BYTES):
                    if chunk:
                        handle.write(chunk)
                        written_bytes += len(chunk)
        # iter_content はプロキシ切断などの早期 EOF を例外にせず正常終了扱いにするため、
        # サイズ検証なしだと破損ファイルを確定配置してしまう。空 or 不完全なら確定しない。
        if written_bytes == 0:
            raise DuckdbDownloadError(f"Downloaded an empty file from {url}")
        if expected_bytes is not None and written_bytes != expected_bytes:
            raise DuckdbDownloadError(
                f"Incomplete download from {url}: "
                f"got {written_bytes} bytes, expected {expected_bytes}"
            )
        tmp_path.replace(destination)
    except requests.RequestException as exc:
        raise DuckdbDownloadError(f"Download failed for {url}: {exc}") from exc
    except OSError as exc:
        # ディスク書き込み失敗 (容量不足・権限等) も「取得できなかった」として正規化し、
        # app.py 側の except (..., DuckdbDownloadError) で拾えるようにする。
        raise DuckdbDownloadError(f"Failed to write DuckDB file for {url}: {exc}") from exc
    finally:
        # 成功時は replace 済みで tmp は存在しない。失敗時のみ残骸を掃除する。
        if tmp_path.exists():
            tmp_path.unlink(missing_ok=True)


def _cleanup_old_versions(cache_dir: Path, keep: int) -> None:
    """mtime の新しい順に keep 個を残し、それ以外のキャッシュを best-effort で削除する."""
    files = sorted(
        cache_dir.glob(f"{_CACHE_FILE_PREFIX}*{_CACHE_FILE_SUFFIX}"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    for path in files[keep:]:
        try:
            path.unlink()
        except OSError as exc:
            logger.warning("Failed to remove old cache file %s: %s", path, exc)


def _latest_cached_file(cache_dir: Path) -> Path | None:
    """キャッシュ内で最も mtime が新しい DuckDB ファイルを返す (無ければ None)."""
    files = list(cache_dir.glob(f"{_CACHE_FILE_PREFIX}*{_CACHE_FILE_SUFFIX}"))
    if not files:
        return None
    return max(files, key=lambda path: path.stat().st_mtime)


def _clear_connection_cache() -> None:
    """新バージョン取得時に get_connection の @st.cache_resource を解放する (best-effort).

    旧接続を解放してから旧ファイルを掃除することで、ファイルハンドルの掴みっぱなしを避ける。
    data.py は datasource を import しないため循環参照は起きない。
    """
    try:
        from edinet_pipeline.dashboard.data import get_connection

        get_connection.clear()
    except Exception as exc:  # noqa: BLE001 - 解放失敗は致命ではないので握って続行
        logger.debug("get_connection.clear() skipped: %s", exc)


def ensure_duckdb_file() -> Path:
    """ダッシュボードが読む DuckDB ファイルのパスを解決する.

    解決順:
      1. ローカル版 (EDINET_DUCKDB_PATH / 既定 artifacts パス) が存在 → そのまま返す
         (開発フロー維持・ネットワーク不要)
      2. 無ければリモート版を HEAD で確認し、未取得なら cache_dir に DL して返す
      3. HEAD 失敗時はキャッシュ済み最新ファイルにフォールバック。皆無なら例外

    Raises:
        DuckdbDownloadError: リモート版を特定できず利用可能なキャッシュも無い場合
    """
    local_path = _local_duckdb_path()
    if local_path.exists():
        return local_path

    url = _duckdb_url()
    cache_dir = _cache_dir()
    version = _cached_remote_version(url)

    if version is not None:
        target = cache_dir / f"{_CACHE_FILE_PREFIX}{version}{_CACHE_FILE_SUFFIX}"
        if not target.exists():
            logger.info("Downloading DuckDB snapshot (version=%s) from %s", version, url)
            _download_to(url, target)
            # 新版を掴み直せるよう旧接続を解放してから旧版を掃除する
            _clear_connection_cache()
            _cleanup_old_versions(cache_dir, keep=_KEEP_CACHED_VERSIONS)
        return target

    cached = _latest_cached_file(cache_dir)
    if cached is not None:
        logger.warning(
            "Could not resolve remote version for %s; falling back to cached %s",
            url,
            cached,
        )
        return cached

    raise DuckdbDownloadError(
        f"Could not determine remote DuckDB version for {url} "
        "and no cached snapshot is available."
    )
