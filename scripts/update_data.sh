#!/usr/bin/env bash
# EDINET パイプライン週次更新スクリプト (macOS / launchd 想定)
#
# launchd の最小環境でも動くよう PATH を明示し、Docker Desktop の起動待ち → 取得 →
# 処理 → エクスポート → GitHub Releases へのアップロードまでを一気通貫で実行する。
# Mac が週 1 回起きていればダッシュボードが自動更新される状態を作るのが目的。
#
# 前提: Docker Desktop インストール済み / `gh auth login` 済み / リポジトリ直下から実行。
# 注意: `date -v` は BSD/macOS 専用の構文。Linux では動かない。
set -euo pipefail

# launchd は PATH をほぼ空で起動するため、homebrew / system のパスを先頭に通す。
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:$PATH"

# ---- 通知ヘルパーと ERR トラップ (初期化失敗も必ず通知できるよう最初に設置) ------ #
# LOG_FILE はまだ未定義の段階でも参照されうるため ${LOG_FILE:-...} でデフォルト展開する。
# この時点の出力先は launchd の StandardErrorPath (logs/launchd.err.log)。
notify() {
    # osascript はGUIセッションのLaunchAgentから呼べる。失敗しても無視 (通知は副次的)。
    local title="$1" message="$2"
    osascript -e "display notification \"${message}\" with title \"${title}\"" 2>/dev/null || true
}

on_error() {
    local exit_code=$?
    local failed_line=$1
    echo "[ERROR] $(date '+%F %T') update_data.sh failed at line ${failed_line} (exit ${exit_code})"
    notify "EDINET 更新失敗" \
        "line ${failed_line} で失敗 (exit ${exit_code})。ログ: ${LOG_FILE:-logs/launchd.err.log}"
    exit "${exit_code}"
}
trap 'on_error ${LINENO}' ERR

# スクリプト位置からリポジトリルートを解決し、そこへ移動 (docker compose / .env を見つけるため)。
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${REPO_ROOT}"

# ---- ログ設定: 全出力をタイムスタンプ付きログファイルへリダイレクト -------------- #
mkdir -p logs
LOG_FILE="logs/update_data_$(date +%Y%m%d_%H%M%S).log"
exec >>"${LOG_FILE}" 2>&1

echo "==== $(date '+%F %T') EDINET weekly update start (root=${REPO_ROOT}) ===="

# ---- 1. Docker Desktop の起動を待つ -------------------------------------------- #
ensure_docker() {
    if docker info >/dev/null 2>&1; then
        echo "Docker daemon already running."
        return 0
    fi
    echo "Docker daemon not running; launching Docker Desktop..."
    open -ga Docker || true
    local waited=0
    local timeout=180
    while ! docker info >/dev/null 2>&1; do
        if [ "${waited}" -ge "${timeout}" ]; then
            echo "Docker did not become ready within ${timeout}s."
            return 1
        fi
        sleep 5
        waited=$((waited + 5))
    done
    echo "Docker is ready (after ${waited}s)."
}
ensure_docker

# ---- 2. DB コンテナを起動 (healthcheck が通るまで待つ) -------------------------- #
docker compose up -d --wait db

# ---- 3. パイプライン実行コマンドのプレフィックス -------------------------------- #
# .env の DATABASE_URL が localhost を指していてもコンテナ内では db: に固定する明示上書き。
RUN="docker compose run --rm -e DATABASE_URL=postgresql://user:password@db:5432/edinet_db app"

# ---- 4. スキーマ移行 ------------------------------------------------------------ #
echo "---- alembic upgrade head ----"
$RUN alembic upgrade head

# ---- 5. 直近 14 日のバックフィル (欠損週の自己回復) ----------------------------- #
# 14 日 trailing window: スリープ等で 1 週飛んでも翌週に取り戻せる。fetch は upsert で冪等。
# process-limit 200: backfill は日毎にキューが空になるまで内部ループするので取りこぼし無し、
# かつ 1 claim が stale 閾値 (既定 60 分) より十分速く終わり stale 復旧と干渉しない。
FROM_DATE="$(date -v-14d +%F)"
TO_DATE="$(date +%F)"
echo "---- edinet backfill --from ${FROM_DATE} --to ${TO_DATE} ----"
$RUN edinet backfill --from "${FROM_DATE}" --to "${TO_DATE}" --process-limit 200

# ---- 6. 失敗分の週次リトライ ---------------------------------------------------- #
echo "---- edinet process --retry-failed ----"
$RUN edinet process --limit 200 --retry-failed

# ---- 7. 業種マスタの更新 (軽量・非致命) ----------------------------------------- #
# 公式 URL は動的生成されることがあり失敗しうるため、失敗しても WARN で続行する。
# 確実に更新したい場合は EDINET_CODE_LIST_URL に有効な URL を設定するか、手動で
# `edinet update-industries --source-file ...` を実行する。
CODE_LIST_URL="${EDINET_CODE_LIST_URL:-https://disclosure2dl.edinet-fsa.go.jp/searchdocument/codelist/Edinetcode.zip}"
echo "---- edinet update-industries (non-fatal) ----"
$RUN edinet update-industries --source-url "${CODE_LIST_URL}" \
    || echo "[WARN] update-industries failed (non-fatal); continuing."

# ---- 8. 分析スナップショットを出力 (Parquet + DuckDB) --------------------------- #
echo "---- edinet export-analytics --format both ----"
$RUN edinet export-analytics --format both

# ---- 9. DuckDB を GitHub Releases の固定タグへ上書きアップロード ----------------- #
# data-latest が未作成 (初回・誤削除時) なら作ってから upload。これで毎回冪等に成功する。
echo "---- gh release upload data-latest (--clobber) ----"
if ! gh release view data-latest >/dev/null 2>&1; then
    echo "Release 'data-latest' not found; creating it."
    gh release create data-latest \
        --latest=false \
        --title "Analytics data (latest)" \
        --notes "週次更新の DuckDB スナップショット（--clobber 上書き運用）"
fi
gh release upload data-latest artifacts/analytics/edinet_analytics.duckdb --clobber

# ---- 10. 古いログを掃除 (90 日より古いものを削除) ------------------------------- #
find logs/ -name 'update_data_*.log' -mtime +90 -delete

# ---- 11. 成功通知 --------------------------------------------------------------- #
echo "==== $(date '+%F %T') EDINET weekly update done (${FROM_DATE} 〜 ${TO_DATE}) ===="
notify "EDINET 更新完了" "週次更新が完了しました (${FROM_DATE} 〜 ${TO_DATE})"
