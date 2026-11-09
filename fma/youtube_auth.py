"""One-time YouTube sign-in for the Shorts uploader (fma/youtube.py). Run it on your own computer:

    python -m fma.youtube_auth --client-file "C:\\Users\\you\\Downloads\\client_secret_....json"

It opens Google's consent page in your browser; you pick the Five Minute AI channel and allow "Manage your YouTube
videos" (only the upload permission is asked: scope youtube.upload). Then it saves the three GitHub secrets
(YOUTUBE_CLIENT_ID, YOUTUBE_CLIENT_SECRET, YOUTUBE_REFRESH_TOKEN) itself through `gh secret set`, feeding each value
on stdin: nothing is printed, written to disk, or put on a command line. Afterwards, delete the downloaded file.
`--print` prints the refresh token instead of saving it (for another repository or Chakra's Credential Manager).

Before running it, in Google Cloud Console (console.cloud.google.com), free:
1. Create a project, enable "YouTube Data API v3".
2. Google Auth Platform / OAuth consent screen: External, app name "Five Minute AI uploader", your Google account
   as a test user, then Publishing status "In production". In "Testing", Google expires refresh tokens after 7
   days. Unverified is fine for your own channel (you'll see an "unverified app" warning once; continue).
3. Clients > Create client > Desktop app > Download JSON."""
from __future__ import annotations

import argparse
import http.server
import json
import secrets
import shutil
import socket
import subprocess
import sys
import threading
import urllib.parse
import webbrowser
from pathlib import Path

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
SCOPE = "https://www.googleapis.com/auth/youtube.upload"
REPO = "fiveminuteai/ai-daily"


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def client_from_file(path: Path) -> tuple[str, str]:
    """The client id and secret from Google's downloaded client JSON ({"installed": {...}} for a Desktop app)."""
    d = json.loads(path.read_text(encoding="utf-8"))
    c = d.get("installed") or d.get("web") or {}
    if not c.get("client_id") or not c.get("client_secret"):
        raise ValueError("that file has no client_id/client_secret: download the JSON of a Desktop app client")
    return c["client_id"], c["client_secret"]


def save_secret(name: str, value: str, repo: str = REPO, run=subprocess.run) -> None:
    """gh secret set, with the value on stdin so it never appears in a command line or a log."""
    r = run(["gh", "secret", "set", name, "--repo", repo], input=value, text=True, capture_output=True)
    if r.returncode != 0:
        raise RuntimeError(f"gh secret set {name} failed: {(r.stderr or '').strip()[:200]}")


def sign_in(client_id: str, client_secret: str) -> str:
    """Google's consent page on a loopback redirect; returns the refresh token."""
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
        "client_id": client_id, "redirect_uri": redirect, "response_type": "code", "scope": SCOPE,
        "access_type": "offline", "prompt": "consent", "state": state})
    print("Opening Google's consent page. If it doesn't open, paste this into your browser:\n" + url + "\n")
    webbrowser.open(url)
    for _ in range(600):
        if got:
            break
        threading.Event().wait(0.5)
    server.server_close()
    if "code" not in got:
        raise RuntimeError(f"no sign-in came back ({got.get('error', 'cancelled or timed out')})")
    import requests
    r = requests.post(TOKEN_URL, data={"code": got["code"], "client_id": client_id, "client_secret": client_secret,
                                       "redirect_uri": redirect, "grant_type": "authorization_code"}, timeout=30)
    if r.status_code != 200 or "refresh_token" not in r.json():
        raise RuntimeError(f"Google refused the token exchange: HTTP {r.status_code}")
    return r.json()["refresh_token"]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="fma.youtube_auth")
    ap.add_argument("--client-file", type=Path, help="the client JSON downloaded from Google Cloud")
    ap.add_argument("--client-id")
    ap.add_argument("--client-secret")
    ap.add_argument("--repo", default=REPO)
    ap.add_argument("--print", action="store_true", help="print the refresh token instead of saving GitHub secrets")
    args = ap.parse_args(argv)
    try:
        if args.client_file:
            cid, csec = client_from_file(args.client_file)
        elif args.client_id and args.client_secret:
            cid, csec = args.client_id, args.client_secret
        else:
            ap.error("give --client-file (or --client-id and --client-secret)")
        if not args.print and not shutil.which("gh"):
            raise RuntimeError("GitHub CLI (gh) not found; install it or use --print")
        refresh = sign_in(cid, csec)
        if args.print:
            print("Refresh token (keep it secret):\n" + refresh)
            return 0
        for name, value in (("YOUTUBE_CLIENT_ID", cid), ("YOUTUBE_CLIENT_SECRET", csec),
                            ("YOUTUBE_REFRESH_TOKEN", refresh)):
            save_secret(name, value, args.repo)
            print(f"saved {name} to {args.repo}")
        print("\nDone. The next Reel that posts will also go to YouTube Shorts. You can delete the downloaded file now.")
        return 0
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"Stopped: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
