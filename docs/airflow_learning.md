# Airflow ハンズオン学習ガイド — EDINET Data Pipeline

このガイドでは、既存の EDINET パイプラインの DAG を教材に、Airflow の基礎から実践的な拡張までをハンズオンで学びます。

---

## 前提準備

```bash
# 1. Airflow コンテナを起動
docker compose --profile airflow up -d

# 2. ブラウザで Airflow UI を開く
open http://localhost:8080
# ログイン: admin / (ターミナルに出力されるパスワード)
```

> `airflow standalone` は初回起動時にパスワードをログ出力します。
> `docker compose logs airflow | grep password` で確認できます。

---

## Part 1: 基礎概念の理解

### 1.1 DAG (有向非巡回グラフ) とは

`airflow/dags/edinet_pipeline.py` を開いてください。

```python
with DAG(
    dag_id="edinet_pipeline",        # DAG の一意な名前
    start_date=pendulum.datetime(2024, 1, 1, tz="Asia/Tokyo"),  # スケジュールの起点
    schedule="@daily",               # 実行間隔
    catchup=False,                   # 過去分を遡って実行しない
    tags=["edinet"],                 # UI でのフィルタ用タグ
) as dag:
```

**DAG** = ワークフロー全体の定義。「どのタスクを、どの順番で、いつ実行するか」を宣言するもの。

| パラメータ | 意味 | 今の設定 |
|-----------|------|---------|
| `dag_id` | DAG の識別名 (UI に表示) | `edinet_pipeline` |
| `start_date` | このDAGが有効になる起点日 | 2024-01-01 JST |
| `schedule` | 実行頻度 | `@daily` (毎日0時) |
| `catchup` | start_date〜現在の未実行分を自動実行するか | `False` (しない) |
| `tags` | UI でのグループ分け | `["edinet"]` |

**ハンズオン 1-1**: Airflow UI で `edinet_pipeline` DAG を見つけ、Graph ビューでタスクの依存関係を確認してください。

---

### 1.2 Task と Operator

```python
fetch_daily = BashOperator(
    task_id="fetch_daily",
    bash_command="edinet fetch --date {{ ds }}",
)
```

- **Task** = DAG 内の個々の処理単位。上の例では `fetch_daily` が1つのタスク
- **Operator** = タスクの「種類」を決めるクラス。`BashOperator` はシェルコマンドを実行する

**主な Operator の種類**:

| Operator | 用途 | 例 |
|----------|------|---|
| `BashOperator` | シェルコマンド実行 | 今のDAGで使用中 |
| `PythonOperator` | Python 関数を直接実行 | DB操作、データ加工 |
| `EmailOperator` | メール送信 | エラー通知 |
| `DummyOperator` | 何もしない (分岐点に使う) | DAG構造の整理 |

---

### 1.3 Jinja テンプレートとマクロ

```python
bash_command="edinet fetch --date {{ ds }}",
```

`{{ ds }}` は Airflow のテンプレートマクロ。実行時に日付文字列に置き換わります。

| マクロ | 値の例 | 説明 |
|--------|-------|------|
| `{{ ds }}` | `2024-03-26` | 論理実行日 (YYYY-MM-DD) |
| `{{ ds_nodash }}` | `20240326` | ハイフンなし |
| `{{ ts }}` | `2024-03-26T00:00:00+00:00` | ISO タイムスタンプ |
| `{{ execution_date }}` | datetime オブジェクト | Python で扱う場合 |
| `{{ prev_ds }}` | `2024-03-25` | 前回実行日 |
| `{{ next_ds }}` | `2024-03-27` | 次回実行日 |

**ハンズオン 1-2**: Airflow UI から DAG を手動トリガーし、`fetch_daily` タスクのログを開いて `{{ ds }}` が実際の日付に展開されていることを確認してください。

---

### 1.4 タスクの依存関係

```python
fetch_daily >> process_queue >> optional_backfill
```

`>>` 演算子で実行順を定義。これは以下と同じ意味:
```python
fetch_daily.set_downstream(process_queue)
process_queue.set_downstream(optional_backfill)
```

```
fetch_daily → process_queue → optional_backfill
```

**依存パターン**:
```python
# 直列 (今のDAG)
a >> b >> c

# 並列 → 合流
a >> [b, c] >> d     # b と c は並列実行、両方終わったら d

# ファンアウト
a >> [b, c, d]       # a の後に b, c, d が並列

# ファンイン
[a, b, c] >> d       # a, b, c 全部終わったら d
```

**ハンズオン 1-3**: Graph ビューで矢印の方向と実行順を確認してください。

---

### 1.5 重要な概念: 実行日 (execution_date) vs 実際の実行時刻

Airflow で最も混乱しやすい概念です。

```
schedule = @daily の場合:

2024-03-26 のデータを処理する DAG run は
→ execution_date = 2024-03-26
→ 実際に実行されるのは 2024-03-27 の 00:00 以降

つまり「1日分のデータが確定した後」に実行される設計。
```

`{{ ds }}` は **execution_date** を返します。今のDAGでは `edinet fetch --date {{ ds }}` なので、
「前日のデータを翌日の0時に取得」という意味になります。

---

## Part 2: 既存 DAG の拡張 (ハンズオン)

### 2.1 export-analytics タスクの追加

**目標**: `process_queue` の後に DuckDB エクスポートを自動実行する

`airflow/dags/edinet_pipeline.py` に以下を追加してみましょう:

```python
# --- ここから追加 ---
export_analytics = BashOperator(
    task_id="export_analytics",
    bash_command="edinet export-analytics --format duckdb",
)

# 依存関係を修正:
# before: fetch_daily >> process_queue >> optional_backfill
# after:
fetch_daily >> process_queue >> [optional_backfill, export_analytics]
```

**学びのポイント**:
- `process_queue` の後に2つのタスクが並列実行される
- `optional_backfill` と `export_analytics` は互いに依存しない

**ハンズオン 2-1**: 上記を実装し、Airflow UI の Graph ビューで分岐が確認できることを検証してください。

---

### 2.2 PythonOperator への書き換え

BashOperator は手軽ですが、エラーハンドリングや戻り値の扱いが限定的です。
PythonOperator を使うと Python 関数を直接呼べます。

```python
from airflow.operators.python import PythonOperator

def run_fetch(**context):
    """fetch ジョブを Python から直接呼び出す."""
    from edinet_pipeline.config import Settings
    from edinet_pipeline.jobs import fetch_documents_for_date

    settings = Settings.from_env()
    target_date = context["ds"]  # Airflow が渡す execution_date
    result = fetch_documents_for_date(settings, target_date)
    return result  # 戻り値は XCom に自動保存される

fetch_daily = PythonOperator(
    task_id="fetch_daily",
    python_callable=run_fetch,
)
```

**学びのポイント**:
- `**context` で Airflow のコンテキスト情報 (`ds`, `task_instance` 等) を受け取れる
- 関数の `return` 値は **XCom** に自動保存され、下流タスクから参照できる

---

### 2.3 XCom でタスク間のデータ受け渡し

```python
def run_process(**context):
    """process ジョブを実行し、fetch の結果を参照する."""
    from edinet_pipeline.config import Settings
    from edinet_pipeline.jobs import process_documents

    # 上流タスクの戻り値を取得
    ti = context["task_instance"]
    fetch_result = ti.xcom_pull(task_ids="fetch_daily")
    print(f"fetch結果: {fetch_result}")

    settings = Settings.from_env()
    process_documents(settings, limit=20, retry_failed=False)

process_queue = PythonOperator(
    task_id="process_queue",
    python_callable=run_process,
)
```

**XCom** = タスク間で小さなデータを受け渡す仕組み (Cross-Communication)

| メソッド | 用途 |
|---------|------|
| `xcom_push(key, value)` | 明示的にデータを保存 |
| `xcom_pull(task_ids, key)` | 他タスクのデータを取得 |
| `return` | 自動的に `return_value` キーで保存 |

> 注意: XCom はメタデータDB に保存されるため、大きなデータ (DataFrame等) は渡さない。
> ファイルパスや件数など小さな値に限定する。

---

### 2.4 リトライ設定の追加

EDINET API はレートリミットやネットワークエラーで失敗することがあります:

```python
fetch_daily = BashOperator(
    task_id="fetch_daily",
    bash_command="edinet fetch --date {{ ds }}",
    retries=3,                             # 最大3回リトライ
    retry_delay=timedelta(minutes=5),      # 5分間隔
    retry_exponential_backoff=True,        # 指数バックオフ
    max_retry_delay=timedelta(minutes=30), # 最大30分
)
```

```python
from datetime import timedelta  # ファイル先頭に追加
```

**ハンズオン 2-2**: `fetch_daily` と `process_queue` にリトライ設定を追加してください。

---

### 2.5 エラー通知のコールバック

タスクが失敗した時に通知する仕組み:

```python
def notify_on_failure(context):
    """タスク失敗時のコールバック."""
    task_id = context["task_instance"].task_id
    execution_date = context["ds"]
    error = context.get("exception", "Unknown")
    print(f"[ALERT] Task '{task_id}' failed on {execution_date}: {error}")
    # ここに Slack 通知や Email 送信を実装できる

with DAG(
    dag_id="edinet_pipeline",
    start_date=pendulum.datetime(2024, 1, 1, tz="Asia/Tokyo"),
    schedule="@daily",
    catchup=False,
    tags=["edinet"],
    default_args={
        "on_failure_callback": notify_on_failure,  # 全タスクに適用
        "retries": 2,
        "retry_delay": timedelta(minutes=5),
    },
) as dag:
    ...
```

**学びのポイント**:
- `default_args` で全タスク共通の設定をまとめられる
- `on_failure_callback` でタスク失敗時のカスタム処理を定義
- `on_success_callback` も同様に使える

---

## Part 3: 運用・監視

### 3.1 Airflow UI の主要画面

| 画面 | 用途 | 見るべきポイント |
|------|------|---------------|
| **DAGs** | DAG 一覧 | ON/OFF切替、直近の実行状態 |
| **Graph** | タスク依存関係 | 分岐・合流の構造確認 |
| **Grid** | 実行履歴のマトリクス | 日付×タスクの成功/失敗パターン |
| **Calendar** | カレンダー表示 | 長期間の実行傾向 |
| **Task Instance** | 個別タスク詳細 | ログ、実行時間、リトライ回数 |

**ハンズオン 3-1**: Airflow UI で以下を確認してください:
1. DAGs 画面で `edinet_pipeline` の ON/OFF を切り替える
2. Graph ビューで各タスクをクリックし、Log を確認する
3. Grid ビューで過去の実行履歴を確認する

---

### 3.2 Connection と Variable

Airflow UI の **Admin > Connections** と **Admin > Variables** で外部接続や設定値を管理できます。

```python
# Variable の使用例
from airflow.models import Variable

process_limit = Variable.get("edinet_process_limit", default_var=20)
```

現在の DAG では環境変数 (`${EDINET_PROCESS_LIMIT}`) を使っていますが、
Airflow Variable を使うと UI から動的に変更できるメリットがあります。

**ハンズオン 3-2**: Airflow UI の Admin > Variables に `edinet_process_limit` を値 `10` で追加してみてください。

---

### 3.3 手動トリガーとバックフィル

```bash
# UI からの手動トリガー
# → DAGs 画面で ▶ ボタンをクリック

# CLI からの手動トリガー (コンテナ内)
docker compose exec airflow airflow dags trigger edinet_pipeline

# 特定日付で実行
docker compose exec airflow airflow dags trigger edinet_pipeline \
  --exec-date 2024-03-15

# バックフィル (過去の日付範囲を一括実行)
docker compose exec airflow airflow dags backfill edinet_pipeline \
  --start-date 2024-03-01 \
  --end-date 2024-03-31
```

**ハンズオン 3-3**: UI から手動トリガーを実行し、実行ログを確認してください。

---

### 3.4 本番運用のベストプラクティス

| 項目 | 推奨 | 現在のDAG |
|------|------|----------|
| **冪等性** | 同じ日付で何度実行しても同じ結果 | ✅ status管理で冪等 |
| **catchup** | 本番では慎重に (データ量次第) | ✅ False |
| **リトライ** | 外部API呼び出しには必須 | ❌ 未設定 → 拡張で追加 |
| **タイムアウト** | 無限実行を防ぐ | ❌ 未設定 → 追加推奨 |
| **アラート** | 失敗時の通知 | ❌ 未設定 → 拡張で追加 |
| **テスト** | DAG の構文チェック | ❌ 未実装 → 下記参照 |

---

### 3.5 DAG のテスト

DAG がインポート可能かをテストするシンプルなテスト:

```python
# tests/test_dag_validation.py
def test_dag_import():
    """DAG ファイルが構文エラーなくインポートできることを確認."""
    from airflow.models import DagBag

    dag_bag = DagBag(dag_folder="airflow/dags", include_examples=False)
    assert len(dag_bag.import_errors) == 0, f"DAG import errors: {dag_bag.import_errors}"

def test_dag_task_count():
    """期待するタスク数があることを確認."""
    from airflow.models import DagBag

    dag_bag = DagBag(dag_folder="airflow/dags", include_examples=False)
    dag = dag_bag.get_dag("edinet_pipeline")
    assert dag is not None
    assert len(dag.tasks) >= 3
```

---

## 学習ロードマップ

```
Week 1: Part 1 (基礎概念)
  ├── DAG/Task/Operator を理解
  ├── テンプレートマクロを理解
  └── Airflow UI の基本操作

Week 2: Part 2 (DAG拡張)
  ├── export-analytics タスク追加
  ├── PythonOperator 書き換え
  ├── リトライ + エラー通知
  └── XCom でタスク間通信

Week 3: Part 3 (運用)
  ├── UI での監視・デバッグ
  ├── Connection / Variable 管理
  ├── バックフィル運用
  └── DAG テストの追加
```

---

## 参考リンク

- [Apache Airflow 公式ドキュメント](https://airflow.apache.org/docs/)
- [Airflow チュートリアル](https://airflow.apache.org/docs/apache-airflow/stable/tutorial/index.html)
- [Astronomer 学習ガイド](https://www.astronomer.io/docs/learn)
