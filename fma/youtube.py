"""YouTube Shorts: every Reel is also uploaded as a Short (8 Nov 2026, growth plan).

A Short is any vertical video up to three minutes, so our Reels qualify as they are. YouTube shows Shorts to people
who don't subscribe, the same way Instagram shows Reels, so each Reel gets a second, separate audience for free.

API facts, checked on Google's pages on 8 Nov 2026:
- videos.insert costs 1 unit from its own "Video Uploads" quota bucket, 100 calls a day
  (developers.google.com/youtube/v3/docs/videos/insert).
- Since 2 Nov 2026, uploads from unverified API projects are no longer locked to private
  (developers.google.com/youtube/v3/revision_history), so a personal project can post public Shorts.

Secrets (GitHub > Settings > Secrets > Actions), made once with `python -m fma.youtube_auth`:
  YOUTUBE_CLIENT_ID, YOUTUBE_CLIENT_SECRET, YOUTUBE_REFRESH_TOKEN
Until all three exist, nothing here runs. Tokens never appear in logs or error messages."""
from __future__ import annotations

import json
import os
import re
import uuid

TOKEN_URL = "https://oauth2.googleapis.com/token"
UPLOAD_URL = "https://www.googleapis.com/upload/youtube/v3/videos?uploadType=multipart&part=snippet,status"
SECRETS = ("YOUTUBE_CLIENT_ID", "YOUTUBE_CLIENT_SECRET", "YOUTUBE_REFRESH_TOKEN")
TITLE_MAX = 100
DESC_MAX = 5000
CATEGORY_SCIENCE_TECH = "28"
TAGS = ["AI", "AI news", "artificial intelligence", "tech news", "Five Minute AI"]
UPLOAD_TIMEOUT = 300


class YouTubeError(Exception):
    """An upload failed. The message never holds a token."""


def configured(env: dict | None = None) -> bool:
    env = os.environ if env is None else env
    return all(env.get(k) for k in SECRETS)


def _plain(s: str) -> str:
    return re.sub(r"\[S\d+\]", "", s or "").strip()


def title_for(hook: str) -> str:
    """The Reel's short cover line as a plain searchable phrase, at most 100 characters, no angle brackets.
    22 Nov 2026: " #Shorts" is no longer added. A vertical video under three minutes is a Short anyway, and Shorts got
    their own search filter on 8 Jan 2026, so the title's room goes to the words people search for."""
    t = re.sub(r"[<>]", "", _plain(hook)).strip().rstrip(".")
    return t if len(t) <= TITLE_MAX else t[:TITLE_MAX - 1].rsplit(" ", 1)[0] + "…"


def description_for(caption: str, site: dict, date: str) -> str:
    """A short YouTube description made from the Reel's caption (22 Nov 2026): the story's lines, where it is checked,
    and its topic hashtags. Instagram-only lines ("link in bio", "Send this to a friend") are left out: the pasted
    caption read as a cross-post. Links in Shorts descriptions aren't clickable, so the site is named, not linked."""
    domain = re.sub(r"^https?://|/$", "", site["base_url"])
    keep, tags = [], []
    for ln in (caption or "").splitlines():
        t = ln.strip()
        if not t:
            continue
        if t.startswith("#"):
            tags += [w for w in t.split() if w.startswith("#")]
        elif re.search(r"link in bio|send this|every claim sourced|tag a friend|follow", t, re.I):
            continue
        else:
            keep.append(_plain(t.lstrip("•")))
    tags = list(dict.fromkeys([*tags, "#ainews", "#shorts"]))[:5]
    text = "\n".join(keep[:3]) + f"\n\nEvery claim checked against its source: {domain}\n\n" + " ".join(tags)
    return text[:DESC_MAX]


def wanted(iid: str, growth: dict) -> bool:
    """Which of the day's Reels go to YouTube (22 Nov 2026). YouTube's rules name templated, mass-produced readings
    of news feeds as inauthentic, and four look-alike Shorts a day reached almost no one (most had no views at all).
    So only the Reel numbers in growth.youtube_slots go, the day's best stories first (default: 1 and 2)."""
    n = iid.rsplit("-", 1)[-1]
    slots = growth.get("youtube_slots") or [1, 2]
    return n.isdigit() and int(n) in slots


def _token(http, env: dict) -> str:
    try:
        r = http.post(TOKEN_URL, data={"client_id": env["YOUTUBE_CLIENT_ID"], "client_secret": env["YOUTUBE_CLIENT_SECRET"],
                                       "refresh_token": env["YOUTUBE_REFRESH_TOKEN"], "grant_type": "refresh_token"})
    except Exception as exc:  # noqa: BLE001
        raise YouTubeError(f"token: {type(exc).__name__}") from None
    if r.status_code != 200:
        err = ""
        try:
            err = r.json().get("error", "")
        except ValueError:
            pass
        raise YouTubeError(f"token: HTTP {r.status_code} {err}".strip())
    return r.json()["access_token"]


def _body(meta: dict, video: bytes, boundary: str) -> bytes:
    return (f"--{boundary}\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n".encode()
            + json.dumps(meta).encode() + f"\r\n--{boundary}\r\nContent-Type: video/mp4\r\n\r\n".encode()
            + video + f"\r\n--{boundary}--\r\n".encode())


def upload_short(http, video_url: str, caption: str, hook: str, site: dict, date: str, env: dict | None = None,
                 uploader=None) -> str:
    """Download the Reel from our site and upload it to YouTube as a public Short. Returns the Short's URL."""
    env = os.environ if env is None else env
    if not configured(env):
        raise YouTubeError("YouTube secrets are not set")
    try:
        got = http.get(video_url)
    except Exception as exc:  # noqa: BLE001
        raise YouTubeError(f"video download: {type(exc).__name__}") from None
    if got.status_code != 200 or not got.content:
        raise YouTubeError(f"video download: HTTP {got.status_code}")
    access = _token(http, env)
    meta = {"snippet": {"title": title_for(hook), "description": description_for(caption, site, date),
                        "tags": TAGS, "categoryId": CATEGORY_SCIENCE_TECH, "defaultLanguage": "en"},
            # the voices are AI: say so, as on Instagram (YouTube's altered-or-synthetic disclosure)
            "status": {"privacyStatus": "public", "selfDeclaredMadeForKids": False, "containsSyntheticMedia": True}}
    if uploader is None:
        import requests
        uploader = requests.post
    for attempt in (meta, {**meta, "status": {k: v for k, v in meta["status"].items() if k != "containsSyntheticMedia"}}):
        boundary = uuid.uuid4().hex
        try:
            r = uploader(UPLOAD_URL, data=_body(attempt, got.content, boundary), timeout=UPLOAD_TIMEOUT,
                         headers={"Authorization": f"Bearer {access}",
                                  "Content-Type": f"multipart/related; boundary={boundary}"})
        except Exception as exc:  # noqa: BLE001
            # 11 Nov 2026 audit: a connection lost after the file was sent may still have made a Short; the token
            # can't list videos (upload scope only), so this is never retried on its own: a missing Short can be
            # uploaded by hand, a duplicate has to be deleted (9 Nov)
            raise YouTubeError(f"upload outcome unknown ({type(exc).__name__}): check the channel before retrying") from None
        if r.status_code in (200, 201):
            return f"https://www.youtube.com/shorts/{r.json()['id']}"
        reason = ""
        try:
            errs = r.json().get("error", {})
            reason = ",".join(e.get("reason", "") for e in errs.get("errors", [])) or str(errs.get("message", ""))[:120]
        except ValueError:
            pass
        if r.status_code == 400 and attempt is meta:
            continue                    # an older API refusing the disclosure field: upload without it
        raise YouTubeError(f"upload: HTTP {r.status_code} {reason}".strip())
    raise YouTubeError("upload: refused")


def main(argv=None) -> int:
    """`python -m fma.youtube --check`: the sign-in works (a token refresh, nothing uploaded). Prints no secrets."""
    import sys
    from .feeds import Http
    if not configured():
        print("YouTube secrets are not set")
        return 1
    try:
        _token(Http(), os.environ)
    except YouTubeError as exc:
        print(f"YouTube sign-in FAILED: {exc}")
        return 1
    print("YouTube sign-in works: the next Reel will also go to YouTube Shorts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
