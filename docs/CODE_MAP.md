# コードマップ — このリポジトリを「どこから読めば動きを追えるか」のガイド

このプロジェクトを初めて読む人向けに、**最短でコードを理解するための地図**をまとめたドキュメントです。
各モジュールの責務、依存関係、典型的な読む順序、用語の対応表を提供します。

実装の動作仕様や CLI の使い方は [README.md](../README.md) を参照してください。

## 1. レイヤ構成（俯瞰）

```text
┌────────────────────────────────────────────────────────────────────┐
│  CLI 層           cli.py                                            │
│                   ↑ argparse で各サブコマンドへ振り分け             │
├────────────────────────────────────────────────────────────────────┤
│  ジョブ層         jobs.py             analytics.py                  │
│                   fetch/process       Parquet・DuckDB エクスポート  │
│                   /backfill                                         │
│                   industry_master.py                                │
│                   update-industries (EDINETコード集約一覧)          │
├────────────────────────────────────────────────────────────────────┤
│  ドメイン層       extractors.py    llm_extractor.py                 │
│                   3層抽出戦略       Layer 3b (Ollama)                │
│                   client.py        config.py                        │
│                   EDINET API       環境変数                          │
├────────────────────────────────────────────────────────────────────┤
│  データ層         db.py          models.py                          │
│                   PostgreSQL     データクラス                       │
│                   リポジトリ                                        │
├────────────────────────────────────────────────────────────────────┤
│  基盤             logging_utils.py                                  │
│                   構造化ログ                                        │
├────────────────────────────────────────────────────────────────────┤
│  可視化           dashboard/                                        │
│                   app.py / data.py / views/ / components/           │
│                   ↑ DuckDB を直接読んで Streamlit で表示            │
└────────────────────────────────────────────────────────────────────┘
```

各層は**下方向にしか依存しません**。たとえば `extractors.py` は `models.py` と
標準ライブラリ・pandas のみに依存し、`db.py` や `client.py` を呼び出しません。
これにより、層ごとに独立してテストできます。

## 2. 推奨される読む順序

知識ゼロから動作を理解したい場合、次の順番で読むのが最短です。

| 順 | ファイル | 読む狙い | 目安行数 |
| --- | --- | --- | --- |
| 1 | `models.py` | 全体で受け渡しされる「共通のレコード型」を頭に入れる (`HumanMetricRecord` 含む) | 139 |
| 2 | `config.py` | 環境変数と動作パラメータの全体像を把握する (LLM 設定含む) | 108 |
| 3 | `cli.py` | サブコマンドの一覧と、それぞれが呼び出す関数を確認する | 150 |
| 4 | `client.py` | EDINET API の HTTP レイヤを把握する（短くて読みやすい） | 128 |
| 5 | `extractors.py` | 3層抽出戦略 (要素ID / 項目名 / テキスト) を読む | 617 |
| 6 | `llm_extractor.py` | Layer 3b の Ollama 連携と SHA256 キャッシュを読む | 278 |
| 7 | `db.py` | 永続化層の責務を把握する（多次元 upsert の実装に注目） | 517 |
| 8 | `jobs.py` | 上記をどう組み合わせて 1 ジョブが動くかを読む（**最後に読むのが効率的**） | 414 |
| 9 | `analytics.py` | DB → Parquet/DuckDB の変換を読む | 310 |
| 10 | `dashboard/` | DuckDB から Streamlit までの可視化フロー (次元フィルタ含む) | - |

ジョブ全体の挙動は [DATA_FLOW.md](DATA_FLOW.md) で時系列に追えます。

## 3. モジュール別の責務サマリ

### 3.1 ドメイン・データ層

| ファイル | 責務 | 主要なクラス・関数 |
| --- | --- | --- |
| `models.py` | レイヤ間で受け渡す不変レコードの定義 | `DocumentRecord`, `ParsedDocument`, `RawFactRecord`, `MetricEvidenceRecord`, `HumanMetricRecord`, `FilingFilters` |
| `config.py` | 環境変数 → `Settings` への変換と、出力パスの導出 | `Settings.from_env()` |
| `client.py` | EDINET API への HTTP 通信（リトライ・タイムアウト・404 判定） | `EdinetClient`, `EdinetApiError`, `CsvUnavailableError` |
| `extractors.py` | CSV ZIP のパースと 3層抽出 (要素ID / 項目名 / テキスト) | `parse_document_zip`, `classify_element_id`, `convert_to_percentage`, `extract_human_capital_from_text`, `merge_llm_records` |
| `llm_extractor.py` | Layer 3b: Ollama によるテキストブロックからの指標抽出 + SHA256 キャッシュ | `extract_via_llm`, `llm_result_to_records` |
| `db.py` | PostgreSQL への CRUD、状態遷移、子テーブルの洗い替え | `PipelineRepository`, `DatabasePool`, `db_connection` |

### 3.2 ジョブ・CLI 層

| ファイル | 責務 | 主要な関数 |
| --- | --- | --- |
| `jobs.py` | 「fetch」「process」「backfill」の 3 つのジョブを実行する | `fetch_documents_for_date`, `process_documents`, `backfill_documents` |
| `analytics.py` | 運用 DB のスナップショットを Parquet と DuckDB へ出力（一時ディレクトリ → リネーム方式。Parquet は `rmtree → replace` のため厳密なアトミック性は無い） | `export_analytics`, `export_parquet_snapshot`, `export_duckdb_snapshot` |
| `industry_master.py` | EDINETコード集約一覧 (`Edinetcode.zip`) から `companies.industry` を一括更新する（API レスポンスに業種が無いため別取り込み経路） | `fetch_edinet_code_zip`, `parse_edinet_code_master`, `update_industries` |
| `cli.py` | argparse でサブコマンドを定義し、対応する関数を呼ぶ | `build_parser`, `main` |
| `logging_utils.py` | 構造化ログ（JSON 1 行）の出力ヘルパー | `configure_logging`, `log_event` |

### 3.3 可視化層（`dashboard/`）

| ファイル | 責務 |
| --- | --- |
| `dashboard/__init__.py` | Streamlit アプリを subprocess で起動するラッパー |
| `dashboard/app.py` | Streamlit のマルチページアプリのエントリポイント。データソースは `datasource.ensure_duckdb_file()` で解決 |
| `dashboard/datasource.py` | DuckDB の取得元解決。ローカル優先、無ければ GitHub Releases (`data-latest`) から ETag をバージョンに埋めて DL・キャッシュ。パスが版ごとに変わることで `data.get_connection` の `@st.cache_resource` キーが自然に切り替わる |
| `dashboard/data.py` | DuckDB へのクエリ関数群（read-only）。許可リスト検証は `models.ALLOWED_SCOPES`/`ALLOWED_WORKER_TYPES` を再利用 |
| `dashboard/constants.py` | テーブル名・指標ラベル・色などの共通定数。男性育休の表示クリップ範囲 `RATIO_DISPLAY_MIN/MAX`、理想クラスタ閾値 `IDEAL_CLUSTER_THRESHOLDS` も集約 |
| `dashboard/components/filters.py` | フィルター UI（年度選択など）の共通コンポーネント |
| `dashboard/views/overview.py` | 概要ページ（KPI、ステータス分布） |
| `dashboard/views/financial.py` | 財務指標の推移・ランキング |
| `dashboard/views/human_capital.py` | 人的資本指標の分布・散布図、男性育休取得率の外れ値注記（100% 超・0%・集計外れ値の 3 種カード） |
| `dashboard/views/company_spotlight.py` | 単一企業の peer 比較。業界 peer + 規模類似 peer（対数スケール ±0.3 dex）+ 理想クラスタ平均との差分を表示。持株会社は `detect_evaluation_scope` で自動的に連結子会社 scope に切替 |
| `dashboard/views/data_quality.py` | カバレッジヒートマップ、充足率の推移 |

> ディレクトリ名は `views/` です。Streamlit の `pages/` 規約と衝突しないよう
> あえて中立な名前を使っています（`pages/` だと自動検出機能が発動し、自前の
> `st.sidebar.radio` ナビゲーションと二重に並んでしまう）。

## 4. 主要な依存グラフ（簡略版）

```text
cli.py
 ├── jobs.fetch_documents_for_date
 │    ├── client.EdinetClient.fetch_documents
 │    ├── jobs.build_document_record   ── models.DocumentRecord
 │    └── db.PipelineRepository.upsert_document
 ├── jobs.process_documents
 │    ├── db.PipelineRepository.claim_documents_for_processing
 │    ├── client.EdinetClient.download_document_csv
 │    ├── extractors.parse_document_zip
 │    │    ├── extractors.classify_element_id     (Layer 1: 要素ID)
 │    │    ├── extractors.convert_to_percentage   (unit='pure' → ×100)
 │    │    └── extractors.extract_human_capital_from_text  (Layer 3a: regex)
 │    ├── jobs._maybe_run_llm_fallback             (Layer 3b: LLM_ENABLED 時のみ)
 │    │    ├── llm_extractor.extract_via_llm
 │    │    └── extractors.merge_llm_records
 │    └── db.PipelineRepository.{mark_processed,mark_failed,mark_skipped,
 │                               replace_raw_facts,replace_metric_evidence,
 │                               delete_human_metrics_for_doc,
 │                               upsert_human_metrics,reset_to_pending}
 ├── jobs.backfill_documents
 │    └── 上記 fetch + process を日付ごとにループ
 ├── analytics.export_analytics
 │    ├── analytics.load_analytics_frames
 │    │    └── db.PipelineRepository.fetch_*_rows  (industry 含む vw_company_year_metrics)
 │    ├── analytics.export_parquet_snapshot
 │    └── analytics.export_duckdb_snapshot
 └── industry_master.update_industries        (`edinet update-industries` で呼ばれる)
      ├── industry_master.fetch_edinet_code_zip   (URL or ローカル ZIP を取得)
      ├── industry_master.parse_edinet_code_master (Shift-JIS CSV → DataFrame)
      └── db.PipelineRepository.update_industries  (companies.industry を VALUES 句で一括 UPDATE)

dashboard/app.py
 └── dashboard/views/*.py
      └── dashboard/data.py.query_*
           ├── query_company_profile / search_company_by_name
           ├── query_industry_peers / query_size_peers (対数スケール ±0.3 dex)
           ├── query_ideal_cluster (3 HC P75 + 営業利益率 P50)
           └── detect_evaluation_scope (持株会社判定)
```

## 5. 用語と DB スキーマの対応

ドキュメント内の用語と、実装で使われる名前の対応表です。

| 概念 | 実装 | 説明 |
| --- | --- | --- |
| 書類 | `DocumentRecord` / `financial_reports` テーブル | 1 件の有価証券報告書 |
| 処理状態 | `financial_reports.status` | `pending` / `processing` / `processed` / `skipped` / `failed` の 5 値 |
| 指標 | `financial_metrics`, `human_metrics` (`ParsedDocument` 内) | 売上高・営業利益・女性管理職比率など |
| 人的資本指標の次元 | `HumanMetricRecord(scope, worker_type, ...)` / `human_capital_metrics` テーブル | `(scope, worker_type)` の組合せで複数行 |
| 抽出経路 | `metric_evidence.matched_by` | `element_id_match` / `item_name_match` / `text_fallback` / `llm_fallback` |
| 抽出根拠 | `MetricEvidenceRecord` / `metric_evidence` | どの行・どのファイルから値を抜いたかの監査証跡 |
| 元 CSV 行 | `RawFactRecord` / `raw_edinet_facts` | 元 CSV の 1 行をそのまま保存（再抽出・監査用） |
| LLM キャッシュ | `llm_extraction_cache` | SHA256(モデル+テキスト) をキーにした LLM 結果の永続化 |
| 分析ビュー | `vw_company_year_metrics` | 企業×年度×次元 に集約した分析向けビュー (1 書類が最大 6 行を返す) |

## 6. ジョブの状態遷移（要点）

```text
        ┌─────────┐
        │ pending │  ← fetch で登録される（CSV あり）
        └────┬────┘
             │ process（claim）
             ▼
        ┌──────────┐
        │processing│
        └────┬─────┘
             │
   ┌─────────┼─────────┐
   │         │         │
   ▼         ▼         ▼
processed   failed   skipped
（成功）  （要再試行） （CSV 無し等）
   │
   │ retry（--retry-failed 時）
   ▼
（failed → pending に戻して再処理）
```

`processing` 状態は通常一瞬しか存在せず、各 `process` 実行内で `processed` /
`failed` / `skipped` のいずれかに遷移します。プロセスが SIGINT で中断された場合は、
`reset_to_pending` で安全に `pending` まで戻されます。

## 7. テストの読み方

`tests/` 配下のテストは、**1 モジュール 1 ファイル**を基本にしています。
リファクタするときは、まず対応するテストを読むと「どこまでが仕様か」が理解できます。

| 対象 | テストファイル |
| --- | --- |
| `client.py` | `test_client.py` |
| `config.py` | `test_config.py` |
| `db.py` | `test_db_unit.py` + `test_cli_integration.py`（要 PostgreSQL） |
| `extractors.py` | `test_extractors.py` |
| `llm_extractor.py` | `test_llm_extractor.py`（mock ベース、Ollama 接続不要） |
| `jobs.py` | `test_jobs.py` + `test_cli_integration.py` |
| `analytics.py` | `test_analytics_export.py` |
| `dashboard/data.py` | `test_dashboard_data.py`（インメモリ DuckDB） |
| `dashboard/__init__.py` | `test_dashboard_cli.py`, `test_dashboard_app.py` |

`@pytest.mark.integration` のついたテストは PostgreSQL が必要です。
通常の `pytest` 実行では skip され、`pytest -m integration` で明示的に実行します。

## 8. 将来の改善候補（まだ実装していないメモ）

ここまでに気づいた改善余地のうち、現時点で「動いているので触らない」と
判断したものを記録しておきます。次に手を入れるならこのあたりが候補です。

- **`extractors.parse_document_zip` のメモリ効率改善**: 現状 `pd.read_csv` で全行を
  読み込み `to_dict('records')` で再変換しており、巨大 CSV では多重保持になります。
  `itertuples` ベースに切り替えれば改善できますが、全テストが回帰することを確認する
  作業量が大きいため見送りました。
- **Parquet 出力のアトミック性強化**: `analytics.export_parquet_snapshot` は
  既存ディレクトリを `rmtree` してから tmp を `replace` するため、
  その瞬間だけ読み手から「ファイルが消えた」状態が見えます。完全なアトミック性が
  必要なら `parquet/` 自体に versioned suffix を付けて切り替える方式が候補です。
- **`reset_to_pending` と SIGINT 経路のテスト追加**: 中断系のテストが現状無いため、
  リファクタ耐性が低いです。`signal` を使った中断シミュレーションテストを足すと安心です。
- **Dashboard ページの共通チャートユーティリティ**: `financial.py` /
  `human_capital.py` / `data_quality.py` で類似の Plotly 設定を繰り返しています。
  ページ数が増えてきたら共通化を検討する価値があります。

## 9. 関連ドキュメント

- [README.md](../README.md) — セットアップと CLI の網羅的リファレンス
- [DATA_FLOW.md](DATA_FLOW.md) — 1 書類が API から可視化まで流れる過程の時系列解説
- [airflow_learning.md](airflow_learning.md) — Airflow 実行に関する学習メモ
