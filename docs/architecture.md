# Architecture

## Design principles

1. **Medallion (Bronze → Silver → Gold)** — keep raw immutable for replay, clean once in Silver, model business logic in Gold only.
2. **Schema-on-read in Bronze, schema-on-write in Silver** — vendor APIs change; isolate that volatility from the warehouse.
3. **Idempotent ingestion** — every run writes to a deterministic `s3://bucket/source=spotify/date=YYYY-MM-DD/` partition; safe to backfill.
4. **One source per Glue job** — failures are isolated; a GitHub API outage doesn't block Spotify ingest.
5. **Reverse-ETL ready** — Gold marts are denormalized fact + dim tables that any BI tool can consume.

## Data flow

### 1. Ingestion (`ingestion/`)

- One Python module per source.
- Each module exposes a `fetch(start_date, end_date) -> Path` function that returns the local path to the raw JSON file it wrote.
- Auth: OAuth refresh tokens stored in `.env`, never long-lived access tokens.
- Failure mode: API errors raise; Airflow handles retry + backoff.

### 2. Bronze (`s3://my-life-in-data-bronze/`)

- Layout: `source={spotify|github|google_calendar}/date=YYYY-MM-DD/data.json`
- Format: Raw JSON (no transformation).
- Retention: forever — this is the source of truth for replay.

### 3. Silver (`s3://my-life-in-data-silver/`)

- Layout: `source=spotify/year=2026/month=05/day=25/part-*.parquet`
- Format: Parquet with explicit schema.
- Transforms: type casting, deduplication, surrogate keys, late-arriving-data handling.
- Job runner: AWS Glue (PySpark).

### 4. Gold (Snowflake `MY_LIFE.MARTS`)

- Loaded via Snowpipe auto-ingest from Silver, or COPY INTO on schedule.
- Modeled with dbt:
  - `staging/` — 1:1 with Silver, light renaming and casting.
  - `intermediate/` — joins and enrichments not yet at the grain of a mart.
  - `marts/` — facts + dims at well-defined grains, documented + tested.

### 5. Serving

- Tableau Cloud or Power BI connects directly to Snowflake `MARTS` schema.
- Notebooks (`notebooks/`) for ad-hoc exploration and the annual year-in-review.

## Orchestration

A single Airflow DAG (`daily_ingest.py`) runs daily at 06:00 local:

```
[spotify_ingest] ──┐
[github_ingest]  ──┼──→ [trigger_glue_jobs] ──→ [snowpipe_refresh] ──→ [dbt_run] ──→ [dbt_test]
[calendar_ingest]──┘
```

Each ingest task is independent (TaskGroup) so a single-source failure doesn't kill the run.

## Quality

- **In-flight** — Glue jobs validate row counts and reject runs where rows drop >20% vs. 7-day rolling avg.
- **Post-load** — `dbt test` runs on every model: not_null, unique, accepted_values, custom singular tests.
- **Freshness** — `dbt source freshness` alerts if any Silver partition is >36h stale.

## Cost guardrails

- Snowflake warehouse auto-suspends after 60s of idle.
- Glue uses 2 DPUs per job (the minimum).
- S3 lifecycle: Bronze → Glacier after 90 days, Silver → Standard-IA after 30.

## What I'd do differently at 100x scale

- Replace daily batch with Kinesis/EventBridge → Iceberg for sub-hour freshness.
- Move Glue → EMR Serverless for cheaper Spark.
- Add a feature store (Feast) for ML-ready aggregates.
