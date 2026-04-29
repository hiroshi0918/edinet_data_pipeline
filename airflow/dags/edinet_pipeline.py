"""EDINET 日次パイプライン Airflow DAG.

実行する 3 タスクを fetch → process → optional_backfill の順で連結する。

タスク構成:
  fetch_daily       : 実行日 (Airflow の {{ ds }}) に提出された書類一覧を EDINET API から取得し、
                      対象書類を `financial_reports` に登録 / 更新する。
  process_queue     : `pending` キューから書類を取り出し、
                      CSV ZIP をダウンロードして指標を抽出・DB へ書き込む。
  optional_backfill : 環境変数 EDINET_BACKFILL_START が設定されている場合のみ、
                      その開始日 〜 当日まで `fetch -> process` をまとめて再実行する。
                      未設定時はメッセージを残してスキップする。

利用する環境変数:
  EDINET_PROCESS_LIMIT  : process / backfill の 1 バッチで処理する書類数 (既定: 20)
  EDINET_BACKFILL_START : optional_backfill を有効化する開始日 (YYYY-MM-DD)。未設定なら無効

注意:
  - schedule は `@daily` 固定。Asia/Tokyo の 0:00 起点で 1 日 1 回実行する。
  - catchup=False のため過去日へさかのぼっての自動再実行はしない (必要なら backfill を使う)。
  - v1 では analytics エクスポート (Parquet / DuckDB) はこの DAG では実行しない。必要な場合は
    別途 `edinet export-analytics` を手動 / 別 DAG で起動する。
"""

from __future__ import annotations

import pendulum

from airflow import DAG
from airflow.operators.bash import BashOperator

with DAG(
    dag_id="edinet_pipeline",
    start_date=pendulum.datetime(2024, 1, 1, tz="Asia/Tokyo"),
    schedule="@daily",
    catchup=False,
    tags=["edinet"],
) as dag:
    # 1) 当日分の書類一覧を取得 (テンプレート変数 {{ ds }} = 実行日 YYYY-MM-DD)
    fetch_daily = BashOperator(
        task_id="fetch_daily",
        bash_command="edinet fetch --date {{ ds }}",
    )

    # 2) 取得済みキューの処理 (限度数は EDINET_PROCESS_LIMIT、未設定時 20)
    process_queue = BashOperator(
        task_id="process_queue",
        bash_command="edinet process --limit ${EDINET_PROCESS_LIMIT:-20}",
    )

    # 3) 任意のバックフィル (EDINET_BACKFILL_START 指定時のみ実行)
    #    過去日へまとめて fetch + process を行うことで、停止期間の空白を埋める。
    optional_backfill = BashOperator(
        task_id="optional_backfill",
        bash_command="""
        if [ -n "${EDINET_BACKFILL_START:-}" ]; then
          edinet backfill \
            --from "${EDINET_BACKFILL_START}" \
            --to "{{ ds }}" \
            --process-limit ${EDINET_PROCESS_LIMIT:-20}
        else
          echo "Skipping optional backfill; set EDINET_BACKFILL_START to enable."
        fi
        """,
    )

    fetch_daily >> process_queue >> optional_backfill
