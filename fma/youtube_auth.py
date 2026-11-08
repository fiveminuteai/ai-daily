"""One-time YouTube sign-in for the Shorts uploader (fma/youtube.py). Run it on your own computer:

    python -m fma.youtube_auth --client-id <ID> --client-secret <SECRET>

It opens Google's consent page in your browser, you pick the YouTube channel and allow "Manage your YouTube videos"
(upload only is asked: scope youtube.upload), and it prints the refresh token. Save the three values as GitHub
secrets with `gh secret set` (the script prints the exact commands, without echoing the secret values into them).

Before running it, in Google Cloud Console (console.cloud.google.com), free:
1. Create a project, enable "YouTube Data API v3".
2. OAuth consent screen: External, app name "Five Minute AI uploader", add your Google account as a test user,
   then set Publishing status to "In production". In "Testing", Google expires refresh tokens after 7 days.
   Unverified is fine for your own channel (you'll see an "unverified app" warning once; continue).
3. Credentials > Create OAuth client ID > Desktop app. Copy the client ID and secret.
Nothing here is stored on disk; the token is printed once."""
from __future__ import annotations

import argparse
import http.server
import secrets
import socket
import sys
import threading
import urllib.parse
import webbrowser

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
SCOPE = "https://www.googleapis.com/auth/youtube.upload"


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="fma.youtube_auth")
    ap.add_argument("--client-id", required=True)
    ap.add_argument("--client-secret", required=True)
    args = ap.parse_args(argv)
    port, state = _free_port(), secrets.token_urlsafe(16)
    redirect = f"http://127.0.0.1:{port}/"
    got: dict = {}

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            q = dict(urllib.parse.parse_qsl(urllib.parse.urlparse(self.path).query))
            if q.get("state") == state:
                got.update(q)
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"Done. You can close this tab and go back to the terminal.")

        def log_message(self, *a):
            pass

    server = http.server.HTTPServer(("127.0.0.1", port), Handler)
    threading.Thread(target=server.handle_request, daemon=True).start()
    url = AUTH_URL + "?" + urllib.parse.urlencode({
        "client_id": args.client_id, "redirect_uri": redirect, "response_type": "code", "scope": SCOPE,
        "access_type": "offline", "prompt": "consent", "state": state})
    print("Opening Google's consent page. If it doesn't open, paste this into your browser:\n" + url + "\n")
    webbrowser.open(url)
    for _ in range(600):
        if got:
            break
        threading.Event().wait(0.5)
    server.server_close()
    if "code" not in got:
        print("No sign-in came back (cancelled or timed out).", file=sys.stderr)
        return 1
    import requests
    r = requests.post(TOKEN_URL, data={"code": got["code"], "client_id": args.client_id,
                                       "client_secret": args.client_secret, "redirect_uri": redirect,
                                       "grant_type": "authorization_code"}, timeout=30)
    if r.status_code != 200 or "refresh_token" not in r.json():
        print(f"Google refused the token exchange: HTTP {r.status_code}", file=sys.stderr)
        return 1
    print("Refresh token (keep it secret):\n" + r.json()["refresh_token"] + "\n")
    print("Save the three secrets (each command asks you to paste the value):")
    for name in ("YOUTUBE_CLIENT_ID", "YOUTUBE_CLIENT_SECRET", "YOUTUBE_REFRESH_TOKEN"):
        print(f"  gh secret set {name} --repo fiveminuteai/ai-daily")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
