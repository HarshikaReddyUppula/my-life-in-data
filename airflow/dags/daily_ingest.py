"""Daily ingest DAG.

Pulls each source independently (TaskGroup), kicks off Glue Bronze→Silver,
then runs dbt against Snowflake.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.operators.python import PythonOperator
from airflow.utils.task_group import TaskGroup

default_args = {
    "owner": "harshika",
    "retries": 2,
    "retry_delay": timedelta(minutes=10),
    "email_on_failure": False,
}


def _ingest_spotify(**_):
    from ingestion.spotify import fetch, write_to_bronze
    write_to_bronze(fetch())


def _ingest_github(**_):
    from ingestion.github import fetch, write_to_bronze
    write_to_bronze(fetch(pages=1))


def _ingest_calendar(**_):
    from ingestion.google_calendar import fetch, write_to_bronze
    write_to_bronze(fetch(days_back=1))


with DAG(
    dag_id="daily_ingest",
    description="Pull daily personal data and refresh the warehouse.",
    schedule="0 6 * * *",
    start_date=datetime(2026, 1, 1),
    catchup=False,
    default_args=default_args,
    tags=["personal", "elt"],
) as dag:

    with TaskGroup(group_id="ingest") as ingest:
        PythonOperator(task_id="spotify", python_callable=_ingest_spotify)
        PythonOperator(task_id="github", python_callable=_ingest_github)
        PythonOperator(task_id="google_calendar", python_callable=_ingest_calendar)

    # TODO: replace with GlueJobOperator once Glue jobs are deployed.
    bronze_to_silver = BashOperator(
        task_id="bronze_to_silver",
        bash_command='echo "TODO: trigger Glue jobs via boto3.client(\'glue\').start_job_run(...)"',
    )

    dbt_run = BashOperator(
        task_id="dbt_run",
        bash_command="cd /opt/airflow/dbt && dbt run --profiles-dir .",
    )

    dbt_test = BashOperator(
        task_id="dbt_test",
        bash_command="cd /opt/airflow/dbt && dbt test --profiles-dir .",
    )

    ingest >> bronze_to_silver >> dbt_run >> dbt_test
