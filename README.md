# EDINET Data Pipeline

EDINET API v2 から有価証券報告書を取得し、財務指標と人的資本指標を PostgreSQL に蓄積するデータパイプラインです。運用系の正本は PostgreSQL に置き、分析用には Parquet と DuckDB を派生出力します。CLI を入口に `fetch -> process -> backfill -> export-analytics` を統一し、ローカル/Docker で再現できる構成にしています。

> **データの出典について**
>
> 本リポジトリに同梱されている `artifacts/analytics/edinet_analytics.duckdb` は、EDINET（金融庁）が公開する有価証券報告書を本パイプラインで加工・集計したものです。元データの出典は金融庁 EDINET (<https://disclosure2.edinet-fsa.go.jp/>) であり、本リポジトリの分析結果は金融庁の公式見解ではありません。

> **初めてこのリポジトリを読む方へ**
>
> 本 README は CLI とセットアップを網羅したリファレンスです。「コードを読んで動きを理解したい」場合は、まず以下を順に読むのが最短ルートです。
>
> 1. [docs/CODE_MAP.md](docs/CODE_MAP.md) — モジュール責務、依存グラフ、推奨される読む順序
> 2. [docs/DATA_FLOW.md](docs/DATA_FLOW.md) — 1 書類が API → DB → Parquet/DuckDB → ダッシュボードへ流れる過程の時系列解説
> 3. 実装本体は `src/edinet_pipeline/` 配下を `models.py → config.py → cli.py → ...` の順で読むと理解しやすいです（詳細は CODE_MAP.md 参照）。

## 概要

このリポジトリは次の 3 層で構成されています。

- 運用レイヤー
  - EDINET API から書類一覧と CSV ZIP を取得
  - PostgreSQL に書類状態、財務指標、人的資本指標、抽出根拠を保存
  - `pending / processing / processed / skipped / failed` の状態で再実行可能に運用
- 分析レイヤー
  - PostgreSQL のスナップショットを Parquet と DuckDB にエクスポート
  - Notebook、ローカル SQL、BI の前段として利用
- 可視化レイヤー
  - DuckDB をデータソースとした Streamlit ダッシュボード
  - 財務指標の推移・比較、人的資本指標の分布・トレンド、データ品質をインタラクティブに可視化

現時点の対象帳票は「有価証券報告書」のみです。

### 分析対象期間

運用正本に入っているのは、主に **提出日 2024-01-04 以降** の有価証券報告書です（`fiscal_year` は期末日 `periodEnd` の西暦。3 月期なら 2024-03-31 → 2024 年度）。

| 提出 | 入っているか | 備考 |
| --- | --- | --- |
| 2022 暦年 | 基本的に無し | パイプライン開始前。サンプル `S100PUDO`（セプテーニ 2022-12 提出）は `edinet import-local` で補完できる |
| 2023 年提出の一部 | あり（薄い） | 2024 年初の取り込み開始直後 |
| 2024-01 以降 | あり | 分析の主対象 |

2022 年提出分をまとめて足す場合（EDINET API が必要）:

```bash
edinet backfill --from 2022-01-01 --to 2022-12-31 --process-limit 20
edinet export-analytics --format both
```

手元の CSV ZIP を 1 通だけ足す場合:

```bash
edinet import-local \
  --zip docs/samples/edinet_csv/S100PUDO/S100PUDO.zip \
  --doc-id S100PUDO \
  --edinet-code E05206 \
  --filer-name '株式会社セプテーニ・ホールディングス' \
  --submitted-date 2022-12-21 \
  --fiscal-year 2022
```

## アーキテクチャ

```mermaid
graph LR
    A[EDINET API v2]
    B[edinet fetch]
    C[edinet process]
    D[(PostgreSQL)]
    E[edinet export-analytics]
    F[Parquet]
    G[DuckDB]
    H[edinet dashboard]

    A --> B
    A --> C
    B --> D
    C --> D
    E --> D
    E --> F
    E --> G
    G --> H
```

## データ抽出・分析のロジック

本データパイプラインは、以下の流れでEDINETからデータを取得し、分析可能な形式に変換しています。

### 1. 取得する「元データ」について
*   **対象書類:** EDINET API v2を利用し、主に「有価証券報告書」を対象とします。
*   **データ形式:** APIから書類の実体データ（CSVが複数格納されたZIPファイル）をダウンロードします。ZIP内のCSVはUTF-16LE / タブ区切りのTSV形式です。
*   **対象ファイル:** ZIP内にある `jpcrp`, `jpaud`, `xbrl_to_csv` といった名前が含まれるCSVファイルが解析対象です。

#### CSVのカラム構成（9列）

| # | 列名 | 意味 | 実データ例 | 補足 |
| --- | --- | --- | --- | --- |
| 1 | `要素ID` | XBRL上の要素を識別するID | `jpdei_cor:NumberOfSubmissionDEI` | 機械判定向けの主キーに近い列 |
| 2 | `項目名` | 要素IDに対応する日本語名 | `売上高、経営指標等` | 人が読むための主ラベル。変換ツール側の名称であり、開示本文そのままではない |
| 3 | `コンテキストID` | 値がどの期間・時点・文脈に属するかを示すID | `CurrentYearDuration`, `FilingDateInstant` | 相対年度・連結/個別・期間/時点の元になる列 |
| 4 | `相対年度` | 提出日基準で見た相対的な年度・時点 | `当期`, `前期`, `当期末`, `提出日時点` | 当期判定に使用 |
| 5 | `連結・個別` | 連結値か個別値か | `連結`, `個別`, `その他` | DEIやテキストブロックでは「その他」が多い |
| 6 | `期間・時点` | フロー項目かストック項目か | `期間`, `時点` | 売上高は「期間」、従業員数や期末残高は「時点」 |
| 7 | `ユニットID` | XBRL上の単位ID | `JPY`, `pure`, `-` | 生の単位識別子 |
| 8 | `単位` | ユニットIDを人間向け表示にしたもの | `円` | `JPY`→`円`、`pure`→空欄 になる例あり |
| 9 | `値` | 実際のインスタンス値 | `17628035000`, `0.333`, 長文テキスト | 数値だけでなく監査報告書などのテキストブロックも入る |

以下の4つの塊で見ると整理しやすい

| 塊 | 列 | 問い |
| --- | --- | --- |
| **何の値か** | 要素ID, 項目名 | どの指標・項目か |
| **いつ・どの粒度か** | コンテキストID, 相対年度, 連結・個別, 期間・時点 | どの期間・文脈の値か |
| **どういう単位か** | ユニットID, 単位 | 数値の単位は何か |
| **中身** | 値 | 実際の数値またはテキスト |

#### 現行パイプラインでの利用状況

現行実装が実際に使っているのは9列のうち **項目名・値・相対年度** の3列のみです。
`項目名` または `値` が無いファイルは丸ごと無視されます。

#### 設計観点での列の仕分け

**本当に残すべき列（整形済み中間層）:**

| 列 | 理由 |
| --- | --- |
| `要素ID` | 項目名は表記揺れや接尾辞があるため、機械判定の軸は本来これに寄せるべき |
| `項目名` | 人間が監査・デバッグするときに必要 |
| `相対年度` | 当期判定にすでに使用中。下流でも最も使いやすい期間軸 |
| `連結・個別` | 売上や利益で連結と個別が混ざると数値の意味が変わる |
| `期間・時点` | フロー/ストック項目の取り違えを防ぐ |
| `値` | 元の文字列をそのまま持つ方が再抽出や監査に有利 |

**将来使える列:**

| 列 | 理由 |
| --- | --- |
| `コンテキストID` | 厳密な再現・重複排除・XBRL再照合に有効 |
| `ユニットID` | 一般化したファクトテーブルを作るなら重要（`JPY` `pure` 等の機械判定） |
| `単位` | 表示や人間の確認には便利だが、固定指標だけを抜く現行パイプラインでは優先度は一段下 |

> **現行方針:** raw層では `raw_edinet_facts` テーブルに9列をすべて保持します。抽出ロジック自体は引き続き主に `項目名` `値` `相対年度` を使い、監査用には `metric_evidence` を別で保持します。

### 2. データ抽出（Extraction）のロジック — 3層戦略

人的資本指標は v0.3 から **要素ID → 項目名 → テキスト** の3層フォールバック方式で抽出します。決定論的に取れる構造化XBRLを優先し、テキスト解析や LLM は最終手段に格下げしました。

*   **Layer 1: 要素ID完全一致（最優先）**
    CSV の `要素ID` 列が `jpcrp_cor:RatioOfFemaleEmployeesInManagerialPositionsMetricsOfReportingCompany` のような XBRL タクソノミー識別子と一致するかを判定します。識別子のサフィックス (`MetricsOfReportingCompany` / `MetricsOfConsolidatedSubsidiaries`) から **scope** を、プレフィックス (`AllEmployees` / `RegularEmployees` / `NonRegularEmployees`) から **worker_type** を導出し、`(scope, worker_type)` の次元キーで `human_capital_metrics` テーブルに格納します。`unit='pure'` の値（割合表記 0.024）は ×100 で % に換算します。
    従業員情報3指標（**平均年間給与・平均勤続年数・平均年齢**、`jpcrp_cor:AverageAnnualSalaryInformationAboutReportingCompanyInformationAboutEmployees` 等）もこの層でのみ抽出します。これらは割合ではないため pure→% 換算は行わず、「12年3ヶ月」のように年・月が別要素IDで開示されるケースは `年 + 月/12` に合成します。
*   **Layer 2: 項目名部分一致（旧タクソノミー救済）**
    Layer 1 で取れなかった行に対し、`項目名` 列に「管理職に占める女性労働者の割合」等のキーワードが含まれるかを判定します。財務指標（売上高・営業利益・当期純利益・従業員数）もこの層で抽出されます。
*   **Layer 3a: テキストフォールバック（regex）**
    `従業員の状況 [テキストブロック]` のような自由記述テキストに対し、ラベル直後の数値を正規表現で抽出します。複数ラベルが並ぶ表形式テキストでの「F=M=W同値バグ」を防ぐため、走査窓を他ラベル直前で打ち切る方式を採用しています。
*   **Layer 3b: LLM フォールバック（任意）**
    `LLM_FALLBACK_ENABLED=true` を設定すると、Layer 1/2 で提出会社の指標が1つも取れていない書類のみ、ローカル LLM (Ollama / `qwen3.5:9b`) でテキストブロックから JSON 形式で値を抽出します。SHA256(テキスト+モデル名) でキャッシュされ、同じテキストの2回目以降は無料です。LLM 呼び出しが失敗してもパイプラインは止まりません。

抽出方法は `metric_evidence.matched_by` 列に `element_id_match` / `item_name_match` / `text_fallback` / `llm_fallback` のいずれかとして記録され、後から監査できます。

### 3. 分析データ化・出力（Analytics）のロジック
抽出されたデータは一旦PostgreSQLに保存され、その後データサイエンティストやBIツールが直接読み込みやすい形式（Parquet / DuckDB）に変換・出力されます。

*   **PostgreSQL に保持する主なデータ:**
    1.  **`raw_edinet_facts`:** 元CSVの1行 = 1レコードで保持する raw テーブルです。再抽出や監査の基礎になります。
    2.  **`metric_evidence`:** 「どのファイルの、どの文字列から、どういうロジックでその数値を拾ったか」という証拠（監査証跡）を記録したテーブルです。`element_id` / `scope` / `worker_type` も記録され、Layer 1〜3 のどれで取得したかを追跡できます。
    3.  **`financial_reports` / `human_capital_metrics`:** 抽出後の財務指標・人的資本指標を保持する運用テーブルです。`human_capital_metrics` は v0.3 から `(scope, worker_type)` の次元キーを持ち、提出会社/連結子会社・全労働者/正規/非正規 の組合せで複数行を持ちます。
    4.  **`llm_extraction_cache`:** Layer 3b (LLM 抽出) の結果を SHA256 キーで永続化するキャッシュテーブル。

*   **分析用に出力される2つのデータセット:**
    1.  **`company_year_metrics`:** 企業・年度・**(scope, worker_type)** ごとの各指標をまとめたテーブル。1 書類につき最大 6 行 (`reporting_company`/`consolidated_subsidiary` × `all`/`regular`/`non_regular`)。
    2.  **`metric_evidence`:** 「どのファイルの、どの文字列から、どういうロジックでその数値を拾ったか」という証拠（監査証跡）を記録したテーブルです。

## 主な機能

- `edinet fetch`
  - 指定日の書類一覧を取得し、対象書類を `financial_reports` に登録・更新します。
- `edinet process`
  - 未処理キューを取得し、CSV ZIP から **3層抽出戦略** (要素ID → 項目名 → テキスト) で財務指標・人的資本指標を抽出します。
  - `LLM_FALLBACK_ENABLED=true` 時は Layer 1/2 で取れなかった書類のみ Ollama 経由で再抽出 (Layer 3b)。
  - 元CSVの全行は `raw_edinet_facts` に保存します。
- `edinet backfill`
  - 日付範囲を日単位で `fetch -> process` し、途中停止後も再開できます。
- `edinet reprocess`
  - 保存済み `raw_edinet_facts` から再抽出し、抽出ロジック修正を再ダウンロードなしで反映します。
- `edinet import-local`
  - 手元の CSV ZIP を API なしで 1 書類として正本へ取り込みます。
- `edinet export-analytics`
  - PostgreSQL の分析スナップショットを Parquet と DuckDB に出力します。
- `edinet dashboard`
  - DuckDB をデータソースとした Streamlit ダッシュボードを起動します。
  - 財務指標の推移・企業比較、人的資本指標の分布・散布図、データ品質のカバレッジを可視化します。
  - サイドバーで `scope` (提出会社 / 連結子会社) と `worker_type` (全労働者 / 正規 / 非正規) を切り替えられます。
- 抽出根拠の保存
  - 指標の抽出元を `metric_evidence` に保存し、`matched_by` (`element_id_match` / `item_name_match` / `text_fallback` / `llm_fallback`) で抽出方法を区別できます。
- 元CSV生データの保存
  - 元CSVの9列全行を `raw_edinet_facts` に保存し、後から再抽出・再監査できます。
- LLM 抽出のキャッシュ
  - 同じテキストブロックに対する LLM 呼び出しは `llm_extraction_cache` (SHA256 キー) で再利用されます。

## リポジトリ構成

```text
.
├── src/edinet_pipeline/
│   ├── cli.py            # edinet コマンドの入口
│   ├── client.py         # EDINET API クライアント
│   ├── config.py         # 環境変数と設定 (LLM 設定含む)
│   ├── db.py             # PostgreSQL repository (多次元 upsert 対応)
│   ├── extractors.py     # 3層抽出戦略 (要素ID / 項目名 / テキスト)
│   ├── llm_extractor.py  # Layer 3b: Ollama 連携 + SHA256 キャッシュ
│   ├── jobs.py           # fetch/process/backfill の実行ロジック
│   ├── analytics.py      # Parquet / DuckDB エクスポート
│   └── dashboard/        # Streamlit ダッシュボード
│       ├── app.py        # マルチページアプリの入口
│       ├── data.py       # DuckDB クエリ関数群 (scope/worker_type フィルタ)
│       ├── constants.py  # 共通定数 (指標ラベル + 次元ラベル)
│       ├── components/   # 共通 UI (フィルタ・次元セレクタ)
│       └── views/        # 各ページ (overview, financial, human_capital, data_quality, company_spotlight)
├── alembic/              # DB migration (0001 / 0002 / 0003 / 0004)
├── airflow/dags/         # 任意の Airflow DAG
├── tests/                # unit / integration tests
├── notebooks/            # 01_eda_basics, 02_extraction_quality_check
├── docker-compose.yml    # app, db, optional airflow
├── pyproject.toml        # 依存管理、pytest、ruff 設定
└── README.md
```

互換維持のため `python src/fetch_edinet.py` と `python src/extract_metrics.py` も残していますが、正規の入口は `edinet` CLI です。

## 前提環境

- Docker / Docker Compose で実行する場合
  - Docker Desktop など、Compose が使える環境
- ローカル Python で実行する場合
  - Python 3.10 以上
  - PostgreSQL 15 相当
- EDINET API キー
  - EDINET の開発者向けサイトで取得したキー

## 環境変数

`.env.example` をコピーして `.env` を作成します。

```bash
cp .env.example .env
```

主要な設定値:

| 変数 | 必須 | 用途 | 既定値 |
| --- | --- | --- | --- |
| `EDINET_API_KEY` | Yes | EDINET API キー | なし |
| `DATABASE_URL` | Yes | PostgreSQL 接続先 | なし |
| `EDINET_REQUEST_TIMEOUT` | No | API タイムアウト秒 | `30` |
| `EDINET_RETRY_COUNT` | No | API 再試行回数 | `3` |
| `EDINET_BACKOFF_SECONDS` | No | API 再試行時の待機係数 | `2` |
| `PROCESS_SLEEP_SECONDS` | No | 書類ごとの待機秒 | `1` |
| `LOG_LEVEL` | No | ログレベル | `INFO` |
| `ANALYTICS_OUTPUT_DIR` | No | Parquet / DuckDB の出力先 | `artifacts/analytics` |
| `STALE_PROCESSING_MINUTES` | No | `processing` のまま停滞した行を `pending` へ自動回収する経過分の閾値 | `60` |
| `EDINET_DUCKDB_URL` | No | ダッシュボードが取得する DuckDB の GitHub Releases アセット URL | `data-latest` の `edinet_analytics.duckdb` |
| `EDINET_DUCKDB_CACHE_DIR` | No | リモート DuckDB のダウンロードキャッシュ先 | OS 一時ディレクトリ配下 `edinet_dashboard/` |
| `EDINET_CODE_LIST_URL` | No | 週次更新スクリプトの `update-industries` が使う Edinetcode.zip の URL | 金融庁の公式集約一覧 URL |
| `LLM_FALLBACK_ENABLED` | No | LLM フォールバック層を有効化 (`true` / `false`) | `false` |
| `LLM_ENDPOINT` | No | Ollama API エンドポイント | `http://localhost:11434/api/generate` |
| `LLM_MODEL` | No | 使用する Ollama モデル名 | `qwen3.5:9b` |
| `LLM_TIMEOUT` | No | LLM リクエストのタイムアウト秒 | `120` |

**LLM フォールバックの利用方法:**

1. ホストで Ollama を起動: `ollama serve`
2. モデルを取得: `ollama pull qwen3.5:9b`
3. `.env` に `LLM_FALLBACK_ENABLED=true` を追加
4. `edinet process` を再実行 — Layer 1/2 で取れなかった書類のみ自動的に LLM が呼ばれる

LLM の結果は `llm_extraction_cache` テーブルに SHA256 キーで永続化されるため、同じテキストブロックを持つ書類を再処理しても 2 回目以降は無料です。

`.env.example` の `DATABASE_URL` は Compose 上の `app` コンテナから使う前提で `@db` を使っています。

```env
EDINET_API_KEY=replace_with_your_edinet_api_key
DATABASE_URL=postgresql://user:password@db:5432/edinet_db
EDINET_REQUEST_TIMEOUT=30
EDINET_RETRY_COUNT=3
EDINET_BACKOFF_SECONDS=2
PROCESS_SLEEP_SECONDS=1
LOG_LEVEL=INFO
ANALYTICS_OUTPUT_DIR=artifacts/analytics
```

ホスト環境から直接 `edinet` を実行する場合は、必要に応じて `DATABASE_URL=postgresql://user:password@localhost:5432/edinet_db` のように切り替えてください。

## 最短セットアップ

### 1. コンテナを起動

```bash
docker compose up -d --build
```

### 2. スキーマを作成 / 移行

```bash
docker compose exec app alembic upgrade head
```

### 3. 書類一覧を取得

```bash
docker compose exec app edinet fetch --date 2024-03-29
```

### 4. 未処理キューを処理

```bash
docker compose exec app edinet process --limit 20
```

### 5. 分析用データを出力

```bash
docker compose exec app edinet export-analytics --format both
```

### 6. ダッシュボードで可視化

```bash
pip install -e '.[viz]'
edinet dashboard
```

ブラウザで `http://localhost:8501` を開くと、4 ページ構成のダッシュボードが表示されます。

### 7. 取り込み状況を確認

```bash
docker compose exec db psql -U user -d edinet_db -c "
SELECT status, COUNT(*) AS reports
FROM financial_reports
GROUP BY status
ORDER BY status;
"
```

## 典型的な運用フロー

単日取り込み:

```bash
docker compose exec app edinet fetch --date 2024-03-29
docker compose exec app edinet process --limit 20
docker compose exec app edinet export-analytics --format both
edinet dashboard
```

月次バックフィル:

```bash
docker compose exec app edinet backfill --from 2024-03-01 --to 2024-03-31 --process-limit 20
docker compose exec app edinet export-analytics --format both
```

失敗済みの再処理:

```bash
docker compose exec app edinet process --limit 20 --retry-failed
docker compose exec app edinet export-analytics --format both
```

## 無人運用（週次自動更新）

「Mac が週 1 回起きていれば、公開中のダッシュボードが自動で最新化される」状態を作るための仕組みです。`scripts/update_data.sh` が Docker 起動 → 取得 → 処理 → エクスポート → GitHub Releases へのアップロードまでを一気通貫で実行し、macOS の launchd（LaunchAgent）が毎週月曜 09:00 にそれを起動します。

**前提:**

- macOS（`scripts/update_data.sh` は `date -v` など BSD/macOS 専用構文を使用）
- Docker Desktop インストール済み（スクリプトが未起動なら自動で起動を待ちます）
- `gh auth login` 済み（DuckDB を Releases にアップロードするため）

**スクリプトの動作:**

1. Docker Desktop の起動を待つ（最大 180 秒）→ `db` コンテナを healthcheck が通るまで起動
2. `alembic upgrade head`
3. 直近 **14 日**の `backfill`（欠損週の自己回復。`fetch` は upsert で冪等）
4. `process --retry-failed`（失敗分の週次リトライ）
5. `update-industries`（軽量・**非致命**: 失敗しても WARN で続行）
6. `export-analytics --format both`
7. `gh release upload data-latest ... --clobber`（DuckDB を Releases に上書き）

ログは `logs/update_data_YYYYmmdd_HHMMSS.log`（90 日より古いものは自動削除）、成功・失敗は macOS 通知で知らせます。

**launchd へのインストール:**

```bash
# リポジトリ直下で実行。__REPO_ROOT__ を実パスに置換して LaunchAgents へ配置
sed "s|__REPO_ROOT__|$(pwd)|g" scripts/com.hiroshi0918.edinet-update.plist \
  > ~/Library/LaunchAgents/com.hiroshi0918.edinet-update.plist
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.hiroshi0918.edinet-update.plist

# 手動試走（予定を待たず即実行）
launchctl kickstart -k gui/$(id -u)/com.hiroshi0918.edinet-update

# 登録確認 / 解除
launchctl list | grep edinet
launchctl bootout gui/$(id -u) ~/Library/LaunchAgents/com.hiroshi0918.edinet-update.plist
```

**注意点:**

- **スリープ・電源オフ時の予定**: Mac がスリープ中なら次のウェイク時にまとめて実行されます。電源オフだとその回はスキップされますが、`backfill` の 14 日 trailing window により翌週の実行で自己回復します。
- **6 月のピーク**: 提出が集中する時期は週次で数千件になり、`PROCESS_SLEEP_SECONDS=1` のレート制御込みで実行に数時間かかることがあります（取りこぼしはありません）。
- **`process` の同時実行は避ける**: stale 復旧は claim 直前に走るため**同一プロセス内**の in-flight 行は誤回収しませんが、別プロセスが並行実行されると一方の処理中の行をもう一方が回収して二重処理しうる（書き込みは冪等なのでデータ破損はなく、API 時間の浪費のみ）。既定（週 1 回・`STALE_PROCESSING_MINUTES=60`）では起きません。週次スクリプトと手動 `process`／`backfill` を併走させない、`STALE_PROCESSING_MINUTES` は 1 バッチの最大処理時間より十分大きく保つ、を守ってください。
- **初回の Release**: 週次スクリプトは `data-latest` が無ければ自動で `gh release create` してから upload するため、原則として事前作成は不要です。手動で先に作る場合は `gh release create data-latest --latest=false` を使ってください。
- **gh 認証が launchd から通らない場合**: GUI セッションの LaunchAgent なら通常 keychain にアクセスできますが、失敗するなら plist の `EnvironmentVariables` に `GH_TOKEN` を渡す方法があります（トークンを含むため公開リポジトリのテンプレートには記載していません）。

## CLI リファレンス

### `edinet fetch`

指定日の EDINET 書類一覧から、有価証券報告書だけを `financial_reports` に登録・更新します。

```bash
docker compose exec app edinet fetch --date 2024-03-29
```

挙動:

- `docDescription`, `ordinanceCode`, `formCode` で対象帳票を絞り込みます。
- `csvFlag=1` の書類は `pending`、CSV 非対応は `skipped` で登録します。
- 同日を再実行しても `doc_id` 単位で再利用するため、重複挿入しません。

### `edinet process`

キューから `pending` の書類を取り出して処理します。

```bash
docker compose exec app edinet process --limit 20
docker compose exec app edinet process --limit 20 --retry-failed
```

挙動:

- CSV ZIP をダウンロードし、財務指標と人的資本指標を抽出します。
- 元CSVの全行を `raw_edinet_facts` に洗い替え保存します。
- 抽出結果を `financial_reports`、`human_capital_metrics`、`metric_evidence` に書き込みます。
- `--retry-failed` を付けた場合のみ `failed` も再処理対象になります。

### `edinet backfill`

日付範囲を日単位で `fetch -> process` します。

```bash
docker compose exec app edinet backfill --from 2024-03-01 --to 2024-03-31 --process-limit 20
docker compose exec app edinet backfill --from 2024-03-01 --to 2024-03-31 --process-limit 20 --retry-failed
```

挙動:

- 指定範囲を inclusive で処理します。
- `pending / failed / processed / skipped` の状態を使って再入可能に動きます。
- 処理途中で停止しても、同じコマンドを再実行すれば継続できます。

### `edinet export-analytics`

運用 DB のスナップショットから Parquet と DuckDB を生成します。

```bash
docker compose exec app edinet export-analytics --format both
docker compose exec app edinet export-analytics --format parquet
docker compose exec app edinet export-analytics --format duckdb
```

挙動:

- `PostgreSQL` は正本です。
- `Parquet` は配布・再利用しやすい列指向フォーマットです。
- `DuckDB` はローカル SQL 分析用のスナップショット DB です。
- `both` は同じ PostgreSQL snapshot を 1 回だけ読み、Parquet と DuckDB を両方更新します。
- v1 では `process/backfill` 完了後に自動更新しません。必要なタイミングで明示実行します。

### `edinet update-industries`

EDINET API のレスポンスには業種フィールドが含まれないため、金融庁が別途配布する「EDINETコード集約一覧 (`Edinetcode.zip`)」を取り込んで `companies.industry` を埋めるためのコマンドです。`--source-url` か `--source-file` のいずれかが必須です（相互排他）。

```bash
# 事前にダウンロードした ZIP を取り込む（推奨）
docker compose run --rm app edinet update-industries \
  --source-file /app/artifacts/edinet_code/Edinetcode_YYYYMMDD.zip

# URL から直接取得する（公式ダウンロード URL を指定）
docker compose run --rm app edinet update-industries --source-url https://...
```

挙動:

- ZIP 内 Shift-JIS CSV を解凍し、「ＥＤＩＮＥＴコード」「提出者業種」列を抽出。
- `companies` に存在する `edinet_code` だけが `UPDATE` 対象（`UPDATE ... FROM (VALUES %s)` の 1 SQL で一括更新）。
- 取り込み後は `edinet export-analytics --format duckdb` を実行して DuckDB の `industry` 列も更新してください（`vw_company_year_metrics` 経由で反映されます）。
- 公式ダウンロード URL は JavaScript で動的生成されるため、ブラウザでダウンロードして `--source-file` で渡す運用が確実です。

### `edinet reset-stale`

プロセスが kill / OOM / 電源断などで突然落ちると、書類が `processing` ステータスのまま取り残され、二度と再処理されずキューが滞留します。このコマンドは閾値より古い `processing` 行（および `processing_started_at` が NULL の旧データ）を `pending` へ戻します。

```bash
# 既定の閾値 (STALE_PROCESSING_MINUTES 環境変数、未設定なら 60 分) で復旧
docker compose run --rm app edinet reset-stale

# 閾値を分単位で明示指定
docker compose run --rm app edinet reset-stale --minutes 30
```

- 復旧した件数は `stale_processing_reset: count=N` として標準出力に表示されます。
- `edinet process` / `edinet backfill` は実行のたび claim の直前に同じ回収処理を自動で走らせるため、無人運用では通常このコマンドを手で叩く必要はありません（手動復旧・観測用）。

### `edinet dashboard`

DuckDB をデータソースとしたインタラクティブな分析ダッシュボードを起動します。

```bash
edinet dashboard
edinet dashboard --port 3000 --host 0.0.0.0
edinet dashboard --duckdb-path /path/to/edinet_analytics.duckdb
```

利用にはオプション依存のインストールが必要です。

```bash
pip install -e '.[viz]'
```

ダッシュボードは以下の 5 ページで構成されます。

| ページ | 内容 |
| --- | --- |
| 概要 | KPI カード（企業数・年度数・レコード数）、年度別処理ステータス分布 |
| 財務指標 | 売上高・営業利益・純利益・従業員数の推移（折れ線）、企業ランキング（棒）、集計統計テーブル |
| 人的資本指標 | 女性管理職比率・男性育休取得率・男女賃金格差の分布（ヒストグラム/箱ひげ図）、年度別平均推移、散布図、男性育休取得率の外れ値（100%超・0%報告・集計外れ値）の補足カード |
| 企業スポットライト | 単一企業を選んで peer と並べる。業界 peer (`industry` 列) と規模類似 peer（対数スケール ±0.3 dex）の両系列、4 種の「理想値」（業界 P75 / 規模 peer P75 / 理想クラスタ平均 / 業界トップ10）テーブル。持株会社は自動的に連結子会社 scope で評価。`industry` が未取得の場合は業界 peer のみ非表示で動作 |
| データ品質 | 指標カバレッジヒートマップ（凡例・hover 付き）、年度別充足率推移、抽出方法の分布（信頼性順の解説付き） |

オプション:

| 引数 | 既定値 | 用途 |
| --- | --- | --- |
| `--port` | `8501` | サーバーポート番号 |
| `--host` | `localhost` | サーバーバインドアドレス |
| `--duckdb-path` | `artifacts/analytics/edinet_analytics.duckdb` | DuckDB ファイルパス |

注意:

- ダッシュボードは DuckDB ファイルのみ参照します。PostgreSQL や EDINET API キーは不要です。
- データを最新化するには先に `edinet export-analytics --format duckdb` を実行してください。
- Docker から起動する場合は `--host 0.0.0.0` の指定が必須です（既定の `localhost` だとコンテナ内 loopback のみで待ち受けるため、ホスト側ブラウザからアクセスできません）。例: `docker compose run --rm -p 8501:8501 app edinet dashboard --host 0.0.0.0`

**DuckDB の配布方式（公開環境）:**

ローカルに `artifacts/analytics/edinet_analytics.duckdb` があればそれを直接読みます。無い場合（Streamlit Community Cloud など）は GitHub Releases の固定タグ `data-latest` に添付された `edinet_analytics.duckdb` を実行時にダウンロードして使います。

- リモートの ETag をバージョンとしてキャッシュファイル名に埋め込み、HEAD チェックを 1 時間キャッシュするため、最悪でも更新の約 65 分後には最新データが反映されます。
- ダウンロード先 URL は `EDINET_DUCKDB_URL`、キャッシュ先は `EDINET_DUCKDB_CACHE_DIR` で上書きできます。
- DuckDB は git に同梱しません（履歴肥大を避けるため）。最新化は週次更新スクリプトが `gh release upload data-latest ... --clobber` で Releases を上書きする運用です（[無人運用](#無人運用週次自動更新) を参照）。

## 状態管理

`financial_reports.status` は次の意味を持ちます。

| status | 意味 |
| --- | --- |
| `pending` | 取得対象として登録済み、未処理 |
| `processing` | 現在処理中 |
| `processed` | 正常に抽出完了 |
| `skipped` | CSV 非対応などで処理対象外 |
| `failed` | API / ZIP / CSV 解析エラーで失敗 |

補助列:

- `retry_count`
  - 失敗回数
- `last_error`
  - 直近の失敗理由
- `processed_at`
  - 処理完了時刻
- `source_metadata`
  - EDINET API の元レスポンス

## データモデル

### `companies`

企業マスタです。

| カラム名 | データ型 | 制約・デフォルト | 説明 |
| --- | --- | --- | --- |
| `edinet_code` | `String(10)` | **PK** | EDINETが付与する企業の一意な識別コード |
| `company_name` | `String(255)` | NOT NULL | 企業名 |
| `industry` | `String(100)` | Nullable | 業種 |
| `created_at` | `DateTime` | `CURRENT_TIMESTAMP` | レコードの登録日時 |

### `financial_reports`

書類メタデータと処理状態の主テーブルです。

| カラム名 | データ型 | 制約・デフォルト | 説明 |
| --- | --- | --- | --- |
| `doc_id` | `String(50)` | **PK** | 書類の固有ID（例: S100T6L2） |
| `edinet_code` | `String(10)` | FK (`companies`) | 提出した企業のEDINETコード |
| `fiscal_year` | `Integer` | NOT NULL | 対象となる決算年度（年） |
| `status` | `String(20)` | `pending` | 処理状態（`pending`/`processing`/`processed`/`skipped`/`failed`） |
| `retry_count` | `Integer` | `0` | エラーによる再試行回数 |
| `last_error` | `Text` | Nullable | 直近のエラーログ詳細 |
| `processed_at` | `DateTime` | Nullable | 処理の完了日時 |
| `sales` | `BigInteger` | Nullable | 抽出された「売上高」など |
| `operating_profit` | `BigInteger` | Nullable | 抽出された「営業利益」など |
| `net_profit` | `BigInteger` | Nullable | 抽出された「純利益」など |
| `employee_count` | `Integer` | Nullable | 抽出された「従業員数」 |
| `submitted_date` | `Date` | NOT NULL | 提出日 |
| `source_metadata` | `JSONB` | `'{}'` | EDINET APIからの元レスポンス情報 |

### `human_capital_metrics`

書類・**次元 (scope, worker_type)** ・ソース単位の人的資本指標です。
`(doc_id, scope, worker_type, source_name)` が一意です。同じ暦年の変則決算が 2 通あっても上書きしません。

| カラム名 | データ型 | 制約・デフォルト | 説明 |
| --- | --- | --- | --- |
| `id` | `Integer` | **PK** (Auto) | 内部サロゲートキー |
| `doc_id` | `String(50)` | FK (`financial_reports`) | 対象書類 |
| `edinet_code` | `String(10)` | FK (`companies`) | 企業のEDINETコード |
| `fiscal_year` | `Integer` | NOT NULL | 対象となる決算年度（年） |
| `scope` | `String(40)` | `reporting_company` | 開示範囲: `reporting_company` / `consolidated_subsidiary` |
| `worker_type` | `String(40)` | `all` | 労働者区分: `all` / `regular` / `non_regular` |
| `female_manager_ratio` | `Numeric(5,2)`| Nullable | 女性管理職比率 (%) — `worker_type='all'` 行にのみ格納 |
| `male_childcare_leave_ratio`| `Numeric(5,2)`| Nullable | 男性の育児休業取得率 (%) |
| `gender_wage_gap` | `Numeric(5,2)`| Nullable | 男女間賃金格差 (%) |
| `average_annual_salary` | `Numeric(12,2)`| Nullable | 平均年間給与 (円) — 提出会社単体、`(reporting_company, all)` 行にのみ格納 |
| `average_years_of_service` | `Numeric(5,2)`| Nullable | 平均勤続年数 (年) — 年+月の分離開示は `年 + 月/12` に合成 |
| `average_age` | `Numeric(5,2)`| Nullable | 平均年齢 (歳) — 同上 |
| `engagement_score` | `Numeric(5,2)`| Nullable | エンゲージメントスコア (将来用) |
| `source_name` | `String(100)` | `EDINET_CSV` | データ抽出元 |

EDINET XBRL は同一書類内に「提出会社/連結子会社」「全労働者/正規雇用/非正規雇用」の組合せで個別の値を持つため、1書類が最大 6 行を生成し得ます。

### `llm_extraction_cache`

Layer 3b (LLM フォールバック) の結果を SHA256 キャッシュするテーブル。

| カラム名 | データ型 | 制約 | 説明 |
| --- | --- | --- | --- |
| `text_hash` | `CHAR(64)` | **PK** | SHA256(モデル名 + テキスト本文) |
| `model` | `String(80)` | NOT NULL | 使用した Ollama モデル名 |
| `result` | `JSONB` | NOT NULL | LLM の生 JSON レスポンス |
| `created_at` | `DateTime` | `CURRENT_TIMESTAMP` | キャッシュ作成日時 |

### `raw_edinet_facts`

元CSVの1行 = 1レコードで保持する raw テーブルです。`process` 実行時に `doc_id` 単位で洗い替えします。

| カラム名 | データ型 | 制約・デフォルト | 説明 |
| --- | --- | --- | --- |
| `id` | `BigInteger` | **PK** (Auto) | 内部サロゲートキー |
| `doc_id` | `String(50)` | FK (`financial_reports`) | 抽出元の書類ID |
| `source_file` | `Text` | NOT NULL | ZIP内のCSVファイル名 |
| `row_number` | `Integer` | NOT NULL | CSV内の1始まり行番号 |
| `element_id` | `Text` | Nullable | 元CSVの `要素ID` |
| `item_name` | `Text` | Nullable | 元CSVの `項目名` |
| `context_id` | `Text` | Nullable | 元CSVの `コンテキストID` |
| `relative_year` | `String(100)` | Nullable | 元CSVの `相対年度` |
| `consolidation_type` | `String(20)` | Nullable | 元CSVの `連結・個別` |
| `period_type` | `String(20)` | Nullable | 元CSVの `期間・時点` |
| `unit_id` | `String(100)` | Nullable | 元CSVの `ユニットID` |
| `unit_label` | `String(100)` | Nullable | 元CSVの `単位` |
| `raw_value` | `Text` | Nullable | 元CSVの `値` |

補助制約:

- `UNIQUE (doc_id, source_file, row_number)`
- `doc_id` と `element_id / relative_year / consolidation_type / period_type` に索引あり

### `metric_evidence`

各指標がどのファイルの、どのテキスト・値に基づいて抽出されたかを保持する監査テーブルです。

| カラム名 | データ型 | 制約・デフォルト | 説明 |
| --- | --- | --- | --- |
| `id` | `Integer` | **PK** (Auto) | 内部サロゲートキー |
| `doc_id` | `String(50)` | FK (`financial_reports`) | 抽出元の書類ID |
| `metric_name` | `String(100)` | NOT NULL | 指標の内部名（例: `sales`, `female_manager_ratio`） |
| `item_name` | `Text` | NOT NULL | 元のCSV上の項目名 |
| `raw_value` | `Text` | NOT NULL | 正規化済みの抽出元のテキストまたは値 |
| `relative_year` | `String(100)` | Nullable | XBRL上の相対年度（当期、前期など） |
| `source_file` | `Text` | NOT NULL | 抽出元のCSVファイル名 |
| `matched_by` | `String(50)` | NOT NULL | 一致ロジック（`element_id_match` / `item_name_match` / `text_fallback` / `llm_fallback`） |
| `element_id` | `Text` | Nullable | XBRL 要素ID (Layer 1 で抽出されたときのみ) |
| `scope` | `String(40)` | Nullable | 抽出された値の `scope` 次元 |
| `worker_type` | `String(40)` | Nullable | 抽出された値の `worker_type` 次元 |

### `vw_company_year_metrics`

分析向けの結合済みビューです。企業、年度、財務指標、人的資本指標をまとめて参照できます。

> **重要**: v0.3 以降、人的資本側 (`human_capital_metrics`) が `(scope, worker_type)` の次元を持つようになったため、このビューは **1 書類につき最大 6 行** を返します（提出会社/連結子会社 × 全労働者/正規/非正規）。財務指標 (`sales` など) はその次元数だけ重複表示されるので、集計時は必ず `WHERE scope = 'reporting_company' AND worker_type = 'all'` で絞り込んでください。

## 分析用エクスポート

出力先は `ANALYTICS_OUTPUT_DIR` 配下です。

```text
artifacts/analytics/
├── parquet/
│   ├── company_year_metrics/
│   │   └── fiscal_year=2024/...
│   └── metric_evidence/
│       └── fiscal_year=2024/...
└── edinet_analytics.duckdb
```

Parquet:

- `company_year_metrics`
- `metric_evidence`

の 2 dataset を `fiscal_year` パーティションで出力します。

DuckDB:

- `analytics.company_year_metrics`
- `analytics.metric_evidence`

の 2 テーブルを実体化します。

DuckDB を直接開く例:

```bash
duckdb artifacts/analytics/edinet_analytics.duckdb
```

```sql
-- analytics.company_year_metrics は 1 書類につき最大 6 行 (scope × worker_type) を返すため、
-- 財務指標を集計するときは必ず scope/worker_type で絞り込む。
SELECT COUNT(*) FROM analytics.company_year_metrics
WHERE scope = 'reporting_company' AND worker_type = 'all';

SELECT * FROM analytics.metric_evidence LIMIT 20;

-- 提出会社・全労働者の女性管理職比率の年度別平均
SELECT fiscal_year, AVG(female_manager_ratio)
FROM analytics.company_year_metrics
WHERE scope = 'reporting_company' AND worker_type = 'all'
GROUP BY fiscal_year
ORDER BY fiscal_year;

-- 雇用形態別の賃金差異を比較 (提出会社のみ、2024年度)
SELECT worker_type,
       AVG(gender_wage_gap) AS avg_wage_gap,
       COUNT(gender_wage_gap) AS n
FROM analytics.company_year_metrics
WHERE scope = 'reporting_company' AND fiscal_year = 2024
GROUP BY worker_type
ORDER BY worker_type;

-- 抽出経路の分布 (Layer 1 がどの程度効いているかを確認)
SELECT metric_name, matched_by, COUNT(*) AS n
FROM analytics.metric_evidence
WHERE metric_name IN ('female_manager_ratio','male_childcare_leave_ratio','gender_wage_gap')
GROUP BY metric_name, matched_by
ORDER BY metric_name, n DESC;
```

## 運用・分析に役立つSQLクエリ集

### 1. 最近の取り込み（処理）ステータスを一覧表示する
各レポートが現在どのような状態（`pending`, `processed`, `failed` など）か、またエラーが発生していないかを確認するためのクエリです。

```bash
docker compose exec db psql -U user -d edinet_db -c "
SELECT doc_id, edinet_code, status, retry_count, last_error
FROM financial_reports
ORDER BY submitted_date, doc_id
LIMIT 30;
"
```

### 2. 抽出が完了した財務・人的資本データを一覧表示する
抽出に成功した売上高や女性管理職比率、育休取得率など、実際に分析に使うデータを企業・年度ごとに一覧するクエリです。`vw_company_year_metrics` は 1 書類につき最大 6 行 (scope × worker_type) を返すため、デフォルトの「提出会社・全労働者」で絞ります。

```bash
docker compose exec db psql -U user -d edinet_db -c "
SELECT
  company_name,
  fiscal_year,
  sales,
  operating_profit,
  net_profit,
  employee_count,
  female_manager_ratio,
  male_childcare_leave_ratio,
  gender_wage_gap
FROM vw_company_year_metrics
WHERE scope = 'reporting_company' AND worker_type = 'all'
ORDER BY fiscal_year DESC, sales DESC NULLS LAST
LIMIT 20;
"
```

連結子会社や正規/非正規の雇用区分を見たい場合は WHERE 句を変更します。

```bash
# 連結子会社の女性管理職比率
docker compose exec db psql -U user -d edinet_db -c "
SELECT company_name, fiscal_year, female_manager_ratio
FROM vw_company_year_metrics
WHERE scope = 'consolidated_subsidiary' AND worker_type = 'all'
  AND female_manager_ratio IS NOT NULL
ORDER BY fiscal_year DESC, female_manager_ratio DESC LIMIT 20;
"

# 正規/非正規ごとの賃金差異の比較
docker compose exec db psql -U user -d edinet_db -c "
SELECT company_name, fiscal_year, worker_type, gender_wage_gap
FROM vw_company_year_metrics
WHERE scope = 'reporting_company'
  AND gender_wage_gap IS NOT NULL
ORDER BY fiscal_year DESC, company_name, worker_type LIMIT 30;
"
```

### 3. 各指標が元ファイルの「どのテキスト」から抽出されたかを検証する
抽出されたデータがどのような元テキスト（証拠）に基づいて判断されたか、監査やデバッグを行うためのクエリです。

```bash
docker compose exec db psql -U user -d edinet_db -c "
SELECT
  me.doc_id,
  fr.edinet_code,
  me.metric_name,
  me.item_name,
  me.raw_value,
  me.relative_year,
  me.matched_by
FROM metric_evidence me
JOIN financial_reports fr
  ON fr.doc_id = me.doc_id
ORDER BY fr.fiscal_year DESC, me.doc_id, me.metric_name
LIMIT 30;
"
```

### 4. 処理に失敗・スキップされた書類の詳細（エラー理由）を確認する
エラー（`failed`）または対象外（`skipped`）となったレポートのIDやその理由（`last_error`）を確認し、リカバリ対応などを行うためのクエリです。

```bash
docker compose exec db psql -U user -d edinet_db -c "
SELECT doc_id, edinet_code, status, retry_count, last_error
FROM financial_reports
WHERE status IN ('failed', 'skipped')
ORDER BY submitted_date, doc_id;
"
```

## 開発

ローカル Python 環境での実行:

```bash
python -m pip install -e '.[dev]'
alembic upgrade head
ruff check .
pytest -q
```

ダッシュボード開発を含む場合:

```bash
python -m pip install -e '.[dev,viz]'
pytest tests/test_dashboard_data.py tests/test_dashboard_cli.py tests/test_dashboard_app.py -v
```

CLI の確認:

```bash
python -m edinet_pipeline --help
python -m edinet_pipeline export-analytics --help
python -m edinet_pipeline dashboard --help
```

CI では次を実行します。

- `ruff check .`
- `pytest -q`
- `gitleaks`

integration test は PostgreSQL を前提にしています。

## 任意の Airflow 実行

Airflow はデフォルトでは起動しません。必要な場合だけ profile を付けて起動します。

```bash
docker compose --profile airflow up airflow
```

同梱の DAG は次の順で実行します。

- `fetch_daily`
- `process_queue`
- `optional_backfill`

`EDINET_BACKFILL_START` を与えた場合だけ追加バックフィルを実行します。v1 では Airflow から `export-analytics` は自動実行しません。

## 互換ラッパー

旧スクリプトも一時的に利用できます。

```bash
TARGET_DATE=2024-03-29 docker compose exec app python src/fetch_edinet.py
docker compose exec app python src/extract_metrics.py --limit 20
```

ただし今後の機能追加は `edinet` CLI を前提に行います。

## トラブルシューティング

### `DATABASE_URL` で接続できない

- Compose 内から実行しているか確認する
- ホストから直接実行しているなら `@db` ではなく `@localhost` に切り替える

### `process` 実行後に対象が残る

- `failed` か `skipped` になっていないか確認する
- `failed` は `--retry-failed` を付けて再処理する

### Parquet / DuckDB が更新されない

- `process` や `backfill` の後に `edinet export-analytics --format both` を実行する
- v1 では分析出力は自動更新ではない

### ダッシュボードが起動しない

- `pip install -e '.[viz]'` で Streamlit と Plotly がインストール済みか確認する
- DuckDB ファイルが存在するか確認する（未エクスポートなら `edinet export-analytics --format duckdb` を先に実行する）

### スキーマ差分がある

```bash
docker compose exec app alembic upgrade head
```
