# EDINET Data Pipeline

EDINET API v2 から有価証券報告書を取得し、財務指標と人的資本指標を PostgreSQL に蓄積するデータパイプラインです。運用系の正本は PostgreSQL に置き、分析用には Parquet と DuckDB を派生出力します。CLI を入口に `fetch -> process -> backfill -> export-analytics` を統一し、ローカル/Docker で再現できる構成にしています。

## 概要

このリポジトリは次の 2 層で構成されています。

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

金融庁「XBRLからCSVへの変換ツール」の仕様に基づく列構成です。実データ（複数日付の有価証券報告書CSV）で確認済みです。

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

9列は以下の4つの塊として読むと整理しやすいです。

| 塊 | 列 | 問い |
| --- | --- | --- |
| **何の値か** | 要素ID, 項目名 | どの指標・項目か |
| **いつ・どの粒度か** | コンテキストID, 相対年度, 連結・個別, 期間・時点 | どの期間・文脈の値か |
| **どういう単位か** | ユニットID, 単位 | 数値の単位は何か |
| **中身** | 値 | 実際の数値またはテキスト |

#### 現行パイプラインでの利用状況

現行実装が実際に使っているのは9列のうち **項目名・値・相対年度** の3列のみです。`項目名` または `値` が無いファイルは丸ごと無視されます。

#### 設計観点での列の仕分け

**本当に残すべき列（silver層）:**

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

### 2. データ抽出（Extraction）のロジック
抽出処理は大きく分けて「表データからの抽出」と「文章データからの抽出（フォールバック）」の2段構えになっています。

*   **A. 表データ（構造化データ）からの抽出:**
    CSVの各行を順番に見ていき、「相対年度」が当期のもので、「項目名」が事前定義されたキーワード（例：売上高、営業利益、従業員数、管理職に占める女性労働者の割合 など）と一致するデータを取得し、数値化します。
*   **B. 文章データからの抽出（人的資本指標のフォールバック）:**
    人的資本の情報（女性管理職比率など）は、自由記述のテキストブロック内に書かれていることが多々あります。表データから見つからなかった場合、テキスト内に「管理職に占める女性労働者の割合」という文字列が含まれているか探し、そこから後方800文字を切り出します。その後、不要な脚注番号や記号を除外してクリーンアップし、該当する指標のラベルのすぐ後ろに出現する最初の数値を抜き出します。

### 3. 分析データ化・出力（Analytics）のロジック
抽出されたデータは一旦PostgreSQLに保存され、その後データサイエンティストやBIツールが直接読み込みやすい形式（Parquet / DuckDB）に変換・出力されます。

*   **PostgreSQL に保持する主なデータ:**
    1.  **`raw_edinet_facts`:** 元CSVの1行 = 1レコードで保持する raw テーブルです。再抽出や監査の基礎になります。
    2.  **`metric_evidence`:** 「どのファイルの、どの文字列から、どういうロジックでその数値を拾ったか」という証拠（監査証跡）を記録したテーブルです。
    3.  **`financial_reports` / `human_capital_metrics`:** 抽出後の財務指標・人的資本指標を保持する運用テーブルです。

*   **分析用に出力される2つのデータセット:**
    1.  **`company_year_metrics`:** 企業・年度ごとの各指標（売上、利益、女性管理職比率など）をまとめたメインのテーブルです。
    2.  **`metric_evidence`:** 「どのファイルの、どの文字列から、どういうロジックでその数値を拾ったか」という証拠（監査証跡）を記録したテーブルです。

## 主な機能

- `edinet fetch`
  - 指定日の書類一覧を取得し、対象書類を `financial_reports` に登録・更新します。
- `edinet process`
  - 未処理キューを取得し、CSV ZIP から財務指標・人的資本指標を抽出します。
  - 元CSVの全行は `raw_edinet_facts` に保存します。
- `edinet backfill`
  - 日付範囲を日単位で `fetch -> process` し、途中停止後も再開できます。
- `edinet export-analytics`
  - PostgreSQL の分析スナップショットを Parquet と DuckDB に出力します。
- `edinet dashboard`
  - DuckDB をデータソースとした Streamlit ダッシュボードを起動します。
  - 財務指標の推移・企業比較、人的資本指標の分布・散布図、データ品質のカバレッジを可視化します。
- 抽出根拠の保存
  - 指標の抽出元を `metric_evidence` に保存し、後から監査できます。
- 元CSV生データの保存
  - 元CSVの9列全行を `raw_edinet_facts` に保存し、後から再抽出・再監査できます。

## リポジトリ構成

```text
.
├── src/edinet_pipeline/
│   ├── cli.py            # edinet コマンドの入口
│   ├── client.py         # EDINET API クライアント
│   ├── config.py         # 環境変数と設定
│   ├── db.py             # PostgreSQL repository
│   ├── extractors.py     # 財務/人的資本指標の抽出
│   ├── jobs.py           # fetch/process/backfill の実行ロジック
│   ├── analytics.py      # Parquet / DuckDB エクスポート
│   └── dashboard/        # Streamlit ダッシュボード
│       ├── app.py        # マルチページアプリの入口
│       ├── data.py       # DuckDB クエリ関数群
│       ├── constants.py  # 共通定数（指標ラベル等）
│       ├── components/   # 共通 UI コンポーネント
│       └── pages/        # 各ページ (overview, financial, human_capital, data_quality)
├── alembic/              # DB migration
├── airflow/dags/         # 任意の Airflow DAG
├── tests/                # unit / integration tests
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

ダッシュボードは以下の 4 ページで構成されます。

| ページ | 内容 |
| --- | --- |
| 概要 | KPI カード（企業数・年度数・レコード数）、年度別処理ステータス分布 |
| 財務指標 | 売上高・営業利益・純利益・従業員数の推移（折れ線）、企業ランキング（棒）、集計統計テーブル |
| 人的資本指標 | 女性管理職比率・男性育休取得率・男女賃金格差の分布（ヒストグラム/箱ひげ図）、年度別平均推移、散布図 |
| データ品質 | 指標カバレッジヒートマップ、年度別充足率推移、抽出方法の分布 |

オプション:

| 引数 | 既定値 | 用途 |
| --- | --- | --- |
| `--port` | `8501` | サーバーポート番号 |
| `--host` | `localhost` | サーバーバインドアドレス |
| `--duckdb-path` | `artifacts/analytics/edinet_analytics.duckdb` | DuckDB ファイルパス |

注意:

- ダッシュボードは DuckDB ファイルのみ参照します。PostgreSQL や EDINET API キーは不要です。
- データを最新化するには先に `edinet export-analytics --format duckdb` を実行してください。

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

会社・年度・ソース単位の人的資本指標です。
`(edinet_code, fiscal_year, source_name)` は一意です。

| カラム名 | データ型 | 制約・デフォルト | 説明 |
| --- | --- | --- | --- |
| `id` | `Integer` | **PK** (Auto) | 内部サロゲートキー |
| `edinet_code` | `String(10)` | FK (`companies`) | 企業のEDINETコード |
| `fiscal_year` | `Integer` | NOT NULL | 対象となる決算年度（年） |
| `female_manager_ratio` | `Numeric(5,2)`| Nullable | 女性管理職比率 (%) |
| `male_childcare_leave_ratio`| `Numeric(5,2)`| Nullable | 男性の育児休業取得率 (%) |
| `gender_wage_gap` | `Numeric(5,2)`| Nullable | 男女間賃金格差 (%) |
| `engagement_score` | `Numeric(5,2)`| Nullable | エンゲージメントスコア |
| `source_name` | `String(100)` | `EDINET_CSV` | データ抽出元（デフォルトはEDINET_CSV） |

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
| `matched_by` | `String(50)` | NOT NULL | 一致ロジック（`item_name_match` や `text_fallback`） |

### `vw_company_year_metrics`

分析向けの結合済みビューです。企業、年度、財務指標、人的資本指標をまとめて参照できます。

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
SELECT COUNT(*) FROM analytics.company_year_metrics;
SELECT * FROM analytics.metric_evidence LIMIT 20;
SELECT fiscal_year, AVG(female_manager_ratio)
FROM analytics.company_year_metrics
GROUP BY fiscal_year
ORDER BY fiscal_year;
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
抽出に成功した売上高や女性管理職比率、育休取得率など、実際に分析に使うデータを企業・年度ごとに一覧するクエリです。

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
ORDER BY fiscal_year DESC, sales DESC NULLS LAST
LIMIT 20;
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
