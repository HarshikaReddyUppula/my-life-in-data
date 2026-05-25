"""Google Calendar ingestion: events from the primary calendar.

API docs: https://developers.google.com/calendar/api/v3/reference/events/list

TODO: complete the OAuth dance; this skeleton uses a pre-issued refresh token loaded from .env.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone

import boto3
from dotenv import load_dotenv
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

load_dotenv()

SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]


def _build_service():
    creds = Credentials(
        token=None,
        refresh_token=os.environ["GOOGLE_REFRESH_TOKEN"],
        client_id=os.environ["GOOGLE_CLIENT_ID"],
        client_secret=os.environ["GOOGLE_CLIENT_SECRET"],
        token_uri="https://oauth2.googleapis.com/token",
        scopes=SCOPES,
    )
    creds.refresh(Request())
    return build("calendar", "v3", credentials=creds, cache_discovery=False)


def fetch(days_back: int = 7) -> list[dict]:
    service = _build_service()
    time_min = (datetime.now(timezone.utc) - timedelta(days=days_back)).isoformat()
    time_max = datetime.now(timezone.utc).isoformat()

    events: list[dict] = []
    page_token: str | None = None
    while True:
        resp = (
            service.events()
            .list(
                calendarId="primary",
                timeMin=time_min,
                timeMax=time_max,
                singleEvents=True,
                orderBy="startTime",
                pageToken=page_token,
                maxResults=250,
            )
            .execute()
        )
        events.extend(resp.get("items", []))
        page_token = resp.get("nextPageToken")
        if not page_token:
            break
    return events


def write_to_bronze(payload: list[dict], run_date: str | None = None) -> str:
    run_date = run_date or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    bucket = os.environ["S3_BRONZE_BUCKET"]
    key = f"source=google_calendar/date={run_date}/data.json"

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
