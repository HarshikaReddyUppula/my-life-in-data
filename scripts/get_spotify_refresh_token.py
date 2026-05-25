"""One-shot Spotify OAuth helper.

Reads SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET from .env, opens your
browser to authorize the app on Spotify, catches the callback on
http://localhost:8888/callback, exchanges the auth code for a refresh
token, and writes SPOTIFY_REFRESH_TOKEN back to .env.

Run once:
    python scripts/get_spotify_refresh_token.py
"""

from __future__ import annotations

import http.server
import os
import threading
import urllib.parse
import webbrowser
from pathlib import Path

import requests
from dotenv import load_dotenv, set_key

load_dotenv()

CLIENT_ID = os.environ["SPOTIFY_CLIENT_ID"]
CLIENT_SECRET = os.environ["SPOTIFY_CLIENT_SECRET"]
REDIRECT_URI = "http://localhost:8888/callback"
SCOPES = "user-read-recently-played"

AUTH_URL = "https://accounts.spotify.com/authorize"
TOKEN_URL = "https://accounts.spotify.com/api/token"

_captured: dict[str, str] = {}


class _Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        params = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        if "code" in params:
            _captured["code"] = params["code"][0]
            body = b"<h2>Spotify authorization complete.</h2><p>You can close this tab.</p>"
            self.send_response(200)
        elif "error" in params:
            _captured["error"] = params["error"][0]
            body = f"<h2>Authorization failed: {params['error'][0]}</h2>".encode()
            self.send_response(400)
        else:
            body = b"Missing 'code' parameter."
            self.send_response(400)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_args, **_kwargs) -> None:
        pass  # silence access log


def main() -> None:
    server = http.server.HTTPServer(("localhost", 8888), _Handler)
    thread = threading.Thread(target=server.handle_request, daemon=True)
    thread.start()

    auth_url = f"{AUTH_URL}?" + urllib.parse.urlencode({
        "client_id": CLIENT_ID,
        "response_type": "code",
        "redirect_uri": REDIRECT_URI,
        "scope": SCOPES,
        "show_dialog": "true",
    })
    print(f"Opening browser to authorize Spotify access...\n  {auth_url}\n")
    webbrowser.open(auth_url)

    thread.join(timeout=180)
    if "error" in _captured:
        raise SystemExit(f"Spotify returned an error: {_captured['error']}")
    if "code" not in _captured:
        raise SystemExit("Timed out waiting for Spotify authorization (3 min).")

    print("Exchanging authorization code for refresh token...")
    resp = requests.post(
        TOKEN_URL,
        data={
            "grant_type": "authorization_code",
            "code": _captured["code"],
            "redirect_uri": REDIRECT_URI,
        },
        auth=(CLIENT_ID, CLIENT_SECRET),
        timeout=10,
    )
    resp.raise_for_status()
    refresh_token = resp.json()["refresh_token"]

    env_path = Path(__file__).resolve().parent.parent / ".env"
    set_key(str(env_path), "SPOTIFY_REFRESH_TOKEN", refresh_token)
    print(f"✓ Saved SPOTIFY_REFRESH_TOKEN to {env_path}")
    print("\nNext: python -m ingestion.spotify")


if __name__ == "__main__":
    main()
