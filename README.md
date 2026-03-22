# EDINET Data Pipeline - 人的資本×財務データ 分析基盤

このプロジェクトは、**EDINET API（V2）** を活用して、日本国内の上場企業の「有価証券報告書」から財務指標および**人的資本に関する指標（女性管理職比率、男性育休取得率など）** を自動抽出・蓄積し、将来的な統計分析やダッシュボード構築の土台となるデータパイプラインです。

## 💡 プロジェクトの目的・背景
近年、投資家やステークホルダーからの関心が高まっている**「エンゲージメント（人的資本）と業績・企業価値の相関」**というテーマに対して、データドリブンなアプローチでアセスメントするための基盤（Data Warehouse）として設計しました。

手作業での情報収集を手放し、EDINET APIからXBRL/CSV形式の生データを自動取得・解析するプログラムを実装することで、データエンジニアリングの基礎である**ETL（Extract, Transform, Load）**のフローを構築しています。

## 🛠 技術スタック
- **言語・ライブラリ**: Python 3.10, pandas (データ解析・クレンジング), requests
- **データベース**: PostgreSQL 15, psycopg2
- **インフラ・環境**: Docker, Docker Compose
- **外部API**: EDINET API V2 (CSV取得対応)

## 📊 システムアーキテクチャ

```mermaid
flowchart LR
    A["EDINET API V2"]
    B["Docker: Python App"]
    C[("Docker: PostgreSQL")]

    A -->|"1. fetch_edinet.py<br/>(書類一覧取得)"| B
    A -->|"2. extract_metrics.py<br/>(ZIP/CSV抽出・解析)"| B
    B -->|"3. Data Load<br/>(ON CONFLICT DO NOTHING)"| C

    subgraph PG["PostgreSQL Database"]
        C1["companies<br/>企業マスタ"]
        C2["financial_reports<br/>売上・利益・従業員数"]
        C3["human_capital_metrics<br/>人的資本・多様性指標"]
        C1 --- C2
        C1 --- C3
    end

    C -.-> C1
```

## 🗂 ディレクトリ構成
```text
edinet_data_pipeline/
├── docker-compose.yml   # データベースとアプリケーションコンテナの統合管理
├── Dockerfile           # Pythonコンテナの環境構築
├── init.sql             # 正規化された3テーブルのDDL定義（初回起動時自動実行）
├── requirements.txt     # Python依存パッケージ
├── README.md            
└── src/
    ├── fetch_edinet.py    # 指定日の提出書類一覧をAPIから取得し、DB(企業マスタ)へ登録
    └── extract_metrics.py # 対象書類のZIPをダウンロードし、CSVから財務・人的資本データを抽出
```

## 🌟 注目ポイント（ポートフォリオとしてのアピール要素）
1. **API v2のモダンな機能の活用**
   - 2024年に拡充されたEDINET APIのCSVダウンロード（`type=5`）機能をいち早く組み込み、泥臭いXBRLパース開発の工数を抑えつつ、いち早くビジネス価値（データ抽出）に直結させています。
2. **オンメモリでのZIP解凍・解析処理**
   - ダウンロードした大量のZIPファイルをローカルディスクに保存し続けるのではなく、`io.BytesIO` と `zipfile` モジュールを使ってすべてオンメモリで展開・パースしています。コンテナのストレージ圧迫やI/Oボトルネックを防ぐ堅牢な実装を意識しました。
3. **拡張性を見据えたRDB設計**
   - BIツールでの分析を前提とし、「企業マスタ」「期間ごとの財務データ」「人的資本指標」を論理的に分離・正規化しました。SQLによる柔軟なJOIN・Group By集計ができるように `init.sql` でスキーマを定めています。
4. **べき等性の担保**
   - パイプラインが途中で失敗しても何度でも安全に再実行できるように、PostgreSQLの `ON CONFLICT DO NOTHING` （または UPDATE）を設計に盛り込み、データの重複登録（Duplicate Key）を防いでいます。

## 🚀 セットアップと実行手順

### 1. EDINET APIキーの設定
`/src/fetch_edinet.py` および `/src/extract_metrics.py` の `API_KEY` 変数に、[EDINET 開発者向けサイト](https://api.edinet-fsa.go.jp/api/auth/index.aspx) から取得したキーを設定します。

### 2. コンテナのビルドとDB初期化
```bash
docker compose up -d --build
```

### 3. パイプラインの実行
**(1) 書類一覧の取得（Extractの起点）**
指定した日付の書類リストを取得し、`companies`テーブルへのマスタ登録、および`financial_reports`への空枠（対象書類ID）登録を行います。
```bash
docker compose exec app python src/fetch_edinet.py
```

**(2) 実データのダウンロードとDBへの抽出・ロード（Transform & Load）**
XBRLに紐づくCSVデータをAPIからZIPとして要求し、売上・利益・従業員数・人的資本指標などの数値を安全にパースして挿入します。
```bash
docker compose exec app python src/extract_metrics.py
```

## 📈 今後の展望
- Tableau等のBIツールを直接PostgreSQLに接続し、「人的資本の充実度と利益率の相関」を可視化するダッシュボードを構築。
- Apache Airflow（またはMage.ai）への移行による、バッチ処理（Cronジョブやタスクごとの依存関係整理）の完全自動化。
