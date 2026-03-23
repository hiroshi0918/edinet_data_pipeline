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
    fetch_daily = BashOperator(
        task_id="fetch_daily",
        bash_command="edinet fetch --date {{ ds }}",
    )

    process_queue = BashOperator(
        task_id="process_queue",
        bash_command="edinet process --limit ${EDINET_PROCESS_LIMIT:-20}",
    )

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
