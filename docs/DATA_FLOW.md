# データフロー — 1 書類が EDINET API から可視化されるまでの時系列

このドキュメントは、有価証券報告書 1 件が EDINET API から取得され、最終的に
ダッシュボードに表示されるまでの**処理の流れ**を、コードの該当箇所と対応付けて
解説したものです。コードを読むときに「今どの段階の処理を見ているのか」を
迷わないための地図として使ってください。

## 0. 全体像

```text
EDINET API                                    Ollama (任意)
   │                                              ▲
   │ ① fetch                                      │ Layer 3b: LLM 抽出
   ▼                                              │ (LLM_FALLBACK_ENABLED=true 時)
financial_reports        ← 状態: pending / skipped │
   │                                              │
   │ ② process                                    │
   │   - CSV ZIP DL                               │
   │   - 3層抽出 (要素ID → 項目名 → テキスト)      │
   │   - LLM フォールバック (オプション)──────────┘
   ▼
financial_reports        ← 状態: processed / failed / skipped
human_capital_metrics    ← 1 書類につき最大 6 行 (scope × worker_type)
metric_evidence          ← matched_by + element_id + scope + worker_type
raw_edinet_facts
llm_extraction_cache     ← SHA256(モデル+テキスト) → JSONB
   │
   │ ③ export-analytics (運用 DB → 分析ファイル)
   ▼
artifacts/analytics/parquet/
artifacts/analytics/edinet_analytics.duckdb
   │
   │ ④ dashboard (DuckDB を直接読む)
   ▼
ブラウザ (Streamlit) — サイドバーで scope / worker_type を切替
```

スキーマは Alembic マイグレーション (`0001` → `0002` → `0003`) で管理。
`0003_add_dimension_columns` で `(scope, worker_type)` 次元と `llm_extraction_cache` が追加されている。

下の各セクションで、それぞれの段階を詳細に追います。

## 1. fetch — 書類一覧の取得（jobs.py）

`edinet fetch --date 2024-03-29` を実行すると、`cli.py:main` が
`jobs.fetch_documents_for_date` を呼びます。

```text
jobs.fetch_documents_for_date(settings, date)
  │
  ├─ EdinetClient.fetch_documents(target_date)
  │    └─ GET https://api.edinet-fsa.go.jp/api/v2/documents.json
  │       ?date=YYYY-MM-DD&type=2 (有価証券報告書等)
  │
  ├─ for each document in payload["results"]:
  │    ├─ FilingFilters.matches() で対象書類のみ抽出
  │    │    （ordinanceCode='010', formCode='030000',
  │    │      docDescription が "有価証券報告書－" で始まる）
  │    │
  │    ├─ build_document_record() で API レスポンス → DocumentRecord
  │    │    └─ derive_fiscal_year(): periodEnd 優先、無ければ submitDateTime
  │    │
  │    ├─ repository.upsert_company(edinet_code, filer_name)
  │    └─ repository.upsert_document(record)
  │         ├─ csvFlag='1' → status='pending'
  │         └─ csvFlag='0' → status='skipped' (CSV 非対応)
  │
  └─ connection.commit()
```

このフェーズでは**まだ CSV はダウンロードしません**。書類のメタデータだけを
DB に登録し、`pending` キューに積みます。

## 2. process — キューを順に処理（jobs.py）

`edinet process --limit 20` を実行すると、`jobs.process_documents` が
キューから書類を取り出して処理します。

```text
jobs.process_documents(settings, limit, retry_failed, ...)
  │
  ├─ DatabasePool でコネクションプールを生成
  │    （書類ごとに connect/close するとコストが累積するため）
  │
  ├─ repository.claim_documents_for_processing(limit, retry_failed)
  │    └─ SELECT FOR UPDATE SKIP LOCKED で排他取得
  │       UPDATE financial_reports SET status = 'processing'
  │       （並行ワーカーが同じ書類を取らないようロックベース制御）
  │
  ├─ for each claimed document:
  │    │
  │    ├─ EdinetClient.download_document_csv(doc_id)
  │    │    ├─ GET .../documents/{doc_id}?type=5
  │    │    ├─ レスポンスが ZIP かを判定
  │    │    └─ 404 相当 → CsvUnavailableError
  │    │       不正レスポンス → EdinetApiError
  │    │
  │    ├─ extractors.parse_document_zip(zip_bytes)
  │    │    │  ★ 3層抽出戦略 (v0.3〜)
  │    │    │
  │    │    ├─ ZIP を展開し jpcrp/jpaud/xbrl_to_csv の CSV を列挙
  │    │    ├─ pd.read_csv (encoding='utf-16le', sep='\t')
  │    │    │
  │    │    ├─ for each row in CSV:
  │    │    │    ├─ RawFactRecord として 11 列をそのまま保持
  │    │    │    │
  │    │    │    ├─ Layer 1: 要素ID完全一致 (最優先)
  │    │    │    │    classify_element_id() で
  │    │    │    │      jpcrp_cor:RatioOfFemaleEmployees... 等から
  │    │    │    │      (metric, scope, worker_type) を判定
  │    │    │    │    + unit='pure' の値は ×100 で % 換算
  │    │    │    │    + MetricEvidenceRecord (matched_by='element_id_match')
  │    │    │    │
  │    │    │    ├─ Layer 2: 項目名部分一致 (旧タクソノミー救済)
  │    │    │    │    EXPLICIT_PATTERNS の項目名にマッチ
  │    │    │    │    + 相対年度が「当期」相当
  │    │    │    │    + MetricEvidenceRecord (matched_by='item_name_match')
  │    │    │    │
  │    │    │    └─ Layer 3a: テキストフォールバック (regex)
  │    │    │         "管理職に占める女性労働者の割合" を含む
  │    │    │         自由記述テキストから後方 800 文字を切出
  │    │    │         + 走査窓を「他ラベル直前」で打ち切り (F=M同値バグ対策)
  │    │    │         + MetricEvidenceRecord (matched_by='text_fallback')
  │    │    │
  │    │    └─ ParsedDocument (human_metrics は (scope, worker_type) ごとに複数行)
  │    │
  │    ├─ Layer 3b: LLM フォールバック  ※ LLM_FALLBACK_ENABLED=true 時のみ
  │    │    Layer 1/2 で提出会社の指標が1つも取れていない場合のみ実行
  │    │    └─ llm_extractor.extract_via_llm()
  │    │         ├─ "従業員の状況 [テキストブロック]" を Ollama (qwen3.5:9b) に送信
  │    │         ├─ JSON モードで構造化レスポンスを取得
  │    │         ├─ SHA256(text+model) で llm_extraction_cache に永続化
  │    │         └─ merge_llm_records() で空欄のみ埋める (first-wins)
  │    │         + MetricEvidenceRecord (matched_by='llm_fallback')
  │    │
  │    └─ DB に書き込み（1 書類で 1 トランザクション）
  │         ├─ replace_raw_facts(doc_id, raw_facts)
  │         ├─ mark_processed(doc_id, parsed)  (status + financial_metrics)
  │         ├─ delete_human_metrics_for_doc(...)  (旧次元レコード掃除)
  │         ├─ upsert_human_metrics(...)
  │         │    └─ ON CONFLICT (edinet_code, fiscal_year, scope, worker_type, source_name)
  │         ├─ replace_metric_evidence(doc_id, evidence)
  │         └─ connection.commit()
  │
  └─ pool.closeall()
```

### エラーハンドリングの分岐

`process_documents` のループ内では、書類ごとに次の例外を区別します：

| 例外 | 遷移先 | 想定ケース |
| --- | --- | --- |
| `CsvUnavailableError` | `skipped` | EDINET 側が CSV を提供していない |
| `EdinetApiError` | `failed` | API タイムアウト、5xx エラー |
| その他の `Exception` | `failed` | パース失敗など |
| `BaseException` (SIGINT 等) | `pending` に戻して再 raise | ユーザー中断の安全処理 |

これにより**処理途中で停止しても、同じコマンドを再実行すれば残りを続行**できます。

## 3. export-analytics — 分析用ファイルへの変換（analytics.py）

`edinet export-analytics --format both` を実行すると、PostgreSQL の現在の状態を
スナップショットとして Parquet と DuckDB に出力します。

```text
analytics.export_analytics(settings, output_format='both')
  │
  ├─ load_analytics_frames(settings)
  │    │
  │    ├─ build_company_year_metrics_frame()
  │    │    └─ SELECT ... FROM vw_company_year_metrics ORDER BY ...
  │    │       （企業×年度ビュー）
  │    │
  │    └─ build_metric_evidence_frame()
  │         └─ SELECT ... FROM metric_evidence
  │            JOIN financial_reports
  │            JOIN companies ORDER BY ...
  │
  ├─ export_parquet_snapshot(settings, frames)
  │    │
  │    ├─ 一時ディレクトリ .tmp-{ms}/parquet/ に書き出し
  │    │    └─ pq.write_to_dataset(partition_cols=['fiscal_year'])
  │    │       fiscal_year ごとにパーティション分割
  │    │
  │    └─ 完了したら本番ディレクトリへ rmtree → replace で入れ替え
  │       （途中失敗時は tmp を捨てるだけで本番は無傷）
  │
  └─ export_duckdb_snapshot(settings, frames)
       │
       ├─ {target}.tmp に DuckDB ファイルを作成
       │    └─ CREATE OR REPLACE TABLE analytics.{dataset} AS SELECT * FROM ...
       │
       └─ 完了したら tmp を本番パスへ rename
```

出力ディレクトリの最終形：

```text
artifacts/analytics/
├── parquet/
│   ├── company_year_metrics/
│   │   ├── fiscal_year=2023/...parquet
│   │   └── fiscal_year=2024/...parquet
│   └── metric_evidence/
│       └── fiscal_year=2024/...parquet
└── edinet_analytics.duckdb     ← analytics.company_year_metrics
                                  analytics.metric_evidence の 2 テーブル
```

## 4. dashboard — DuckDB を直接読む（dashboard/）

`edinet dashboard` を実行すると、Streamlit が起動して上記 DuckDB を直接読みます。

```text
dashboard/__init__.py.launch_dashboard(host, port, duckdb_path)
  │
  └─ subprocess で `streamlit run app.py -- --duckdb-path ...` を起動
       │
       └─ dashboard/app.py
            │
            ├─ dashboard/components/filters.py の共通フィルタを描画
            │   ├─ render_fiscal_year_filter (年度範囲スライダー)
            │   ├─ render_dimension_filter   (scope / worker_type セレクタ)
            │   └─ render_company_filter     (企業マルチセレクト)
            │
            └─ st.navigation でページを切り替え
                 ├─ pages/overview.py        (KPI / ステータス分布)
                 ├─ pages/financial.py       (推移・ランキング・統計)
                 ├─ pages/human_capital.py   (分布・散布図・推移、scope/worker_type 対応)
                 └─ pages/data_quality.py    (カバレッジ・充足率)
                      │
                      └─ dashboard/data.py.query_* で
                         DuckDB に SELECT を発行（read-only）
                         ※ 全クエリが scope/worker_type を WHERE 句で絞る前提。
                           デフォルトは reporting_company × all。
```

`dashboard/data.py` の各関数は `@st.cache_data(ttl=300)` で 5 分間結果を
キャッシュしているため、同じフィルタ条件での再レンダリングは高速です。

## 5. backfill — 日付範囲の一括実行（jobs.py）

`edinet backfill --from 2024-03-01 --to 2024-03-31 --process-limit 20` は、
内部で fetch + process を日付ごとに繰り返すだけです。

```text
backfill_documents(settings, start_date, end_date, process_limit, ...)
  │
  └─ for current_date in [start_date .. end_date]:
       ├─ fetch_documents_for_date(settings, current_date)
       └─ while True:
            processed = process_documents(
                settings, limit=process_limit,
                submitted_date=current_date, ...
            )
            if processed == 0:
                break
```

その日のキューが空になるまで `process_documents` を繰り返し呼ぶことで、
1 日 100 件以上ある日でも `--process-limit 20` で順次処理できます。

## 6. 状態遷移を理解するためのヒント

「ある書類が今どこにいるのか」は `financial_reports.status` と
`processed_at` を見れば一目でわかります。

```sql
-- 取り込み状況のサマリ
SELECT status, COUNT(*) AS reports
FROM financial_reports
GROUP BY status
ORDER BY status;
```

**status の意味と次にどうすればよいか**：

| status | 意味 | アクション |
| --- | --- | --- |
| `pending` | 取得済み・未処理 | `edinet process` を実行 |
| `processing` | 処理中 | 通常一瞬。残り続けたら手動で `pending` に戻す |
| `processed` | 抽出完了 | 何もしなくて良い |
| `skipped` | CSV 非対応の書類 | 何もしなくて良い |
| `failed` | エラーで失敗 | `edinet process --retry-failed` で再試行 |

## 7. このドキュメントと一緒に読むと良いもの

- [CODE_MAP.md](CODE_MAP.md) — 各モジュールの責務と「読む順序」
- [README.md](../README.md) — セットアップ・CLI リファレンス・SQL クエリ集
- 実装の詳細を追いたいときは、`src/edinet_pipeline/` 直下の Python ファイルに
  日本語の docstring が付いているので、合わせて読むとスムーズです。
