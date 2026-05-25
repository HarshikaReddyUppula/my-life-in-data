"""Spotify ingestion: recently-played tracks.

API docs: https://developer.spotify.com/documentation/web-api/reference/get-recently-played
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

import boto3
import requests
from dotenv import load_dotenv

load_dotenv()

TOKEN_URL = "https://accounts.spotify.com/api/token"
RECENT_URL = "https://api.spotify.com/v1/me/player/recently-played"


def _refresh_access_token() -> str:
    """Exchange the long-lived refresh token for a short-lived access token."""
    resp = requests.post(
        TOKEN_URL,
        data={
            "grant_type": "refresh_token",
            "refresh_token": os.environ["SPOTIFY_REFRESH_TOKEN"],
        },
        auth=(os.environ["SPOTIFY_CLIENT_ID"], os.environ["SPOTIFY_CLIENT_SECRET"]),
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


def fetch(limit: int = 50) -> dict:
    """Fetch the most recent `limit` (max 50) tracks for the authenticated user."""
    token = _refresh_access_token()
    resp = requests.get(
        RECENT_URL,
        headers={"Authorization": f"Bearer {token}"},
        params={"limit": limit},
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()


def write_to_bronze(payload: dict, run_date: str | None = None) -> str:
    """Write the raw payload to s3://bronze/source=spotify/date=YYYY-MM-DD/data.json."""
    run_date = run_date or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    bucket = os.environ["S3_BRONZE_BUCKET"]
    key = f"source=spotify/date={run_date}/data.json"

    s3 = boto3.client("s3")
    s3.put_object(
        Bucket=bucket,
        Key=key,
        Body=json.dumps(payload).encode("utf-8"),
        ContentType="application/json",
    )
    return f"s3://{bucket}/{key}"


if __name__ == "__main__":
    payload = fetch()
    uri = write_to_bronze(payload)
    print(f"Wrote {len(payload.get('items', []))} tracks to {uri}")
