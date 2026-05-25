"""GitHub ingestion: user public events.

API docs: https://docs.github.com/en/rest/activity/events
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone

import boto3
import requests
from dotenv import load_dotenv

load_dotenv()


def fetch(per_page: int = 100, pages: int = 3) -> list[dict]:
    """Fetch up to `per_page * pages` events for the configured user."""
    username = os.environ["GITHUB_USERNAME"]
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "Authorization": f"Bearer {os.environ['GITHUB_TOKEN']}",
    }

    events: list[dict] = []
    for page in range(1, pages + 1):
        resp = requests.get(
            f"https://api.github.com/users/{username}/events",
            headers=headers,
            params={"per_page": per_page, "page": page},
            timeout=10,
        )
        resp.raise_for_status()
        batch = resp.json()
        if not batch:
            break
        events.extend(batch)
    return events


def write_to_bronze(payload: list[dict], run_date: str | None = None) -> str:
    run_date = run_date or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    bucket = os.environ["S3_BRONZE_BUCKET"]
    key = f"source=github/date={run_date}/data.json"

    s3 = boto3.client("s3")
    s3.put_object(
        Bucket=bucket,
        Key=key,
        Body=json.dumps(payload).encode("utf-8"),
        ContentType="application/json",
    )
    return f"s3://{bucket}/{key}"


if __name__ == "__main__":
    events = fetch()
    uri = write_to_bronze(events)
    print(f"Wrote {len(events)} events to {uri}")
