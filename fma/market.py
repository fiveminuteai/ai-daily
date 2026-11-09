"""The market scout (9 Nov 2026, growth engine): which AI Shorts people watched this week, in the US and India.

Once a week, the most-viewed short AI videos of the last 7 days on YouTube, from the official YouTube Data API v3
(search.list 100 units a call, videos.list 1; the free daily quota is 10,000, this spends about 1,000 a week).
The titles show which worries and hook shapes are pulling viewers right now; the Reel desk sees the top ones as
ideas only (fma/reel_desk.py market_note): other people's words and claims are never facts for us.

Needs the secret YOUTUBE_API_KEY (Google Cloud > APIs & Services > Credentials > Create API key, restricted to the
YouTube Data API v3). Without it nothing runs. Writes data/growth/market.json."""
from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from . import config

API = "https://www.googleapis.com/youtube/v3"
QUERIES = ["AI news", "ChatGPT", "OpenAI", "Google Gemini AI", "AI tools"]
REGIONS = ["US", "IN"]               # US first: the audience that pays most; India: our home audience
SHORT_MAX_S = 180
TOP_N = 20


def _secs(iso: str) -> float:
    m = re.match(r"^PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?$", iso or "")
    if not m:
        return 1e9
    h, mi, s = (int(x or 0) for x in m.groups())
    return h * 3600 + mi * 60 + s


def scout(http, key: str, now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    since = (now - timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%SZ")
    found: dict[str, str] = {}
    for region in REGIONS:
        for q in QUERIES:
            r = http.get(f"{API}/search", params={"part": "id", "type": "video", "videoDuration": "short", "q": q,
                                                   "order": "viewCount", "publishedAfter": since, "regionCode": region,
                                                   "relevanceLanguage": "en", "maxResults": 25, "key": key})
            if r.status_code != 200:
                raise RuntimeError(f"YouTube search: HTTP {r.status_code}")
            for it in r.json().get("items", []):
                vid = (it.get("id") or {}).get("videoId")
                if vid and vid not in found:
                    found[vid] = region
    rows = []
    ids = list(found)
    for i in range(0, len(ids), 50):
        r = http.get(f"{API}/videos", params={"part": "snippet,statistics,contentDetails",
                                              "id": ",".join(ids[i:i + 50]), "key": key})
        if r.status_code != 200:
            raise RuntimeError(f"YouTube videos: HTTP {r.status_code}")
        for v in r.json().get("items", []):
            if _secs((v.get("contentDetails") or {}).get("duration", "")) > SHORT_MAX_S:
                continue
            rows.append({"id": v["id"], "title": (v.get("snippet") or {}).get("title", "")[:150],
                         "channel": (v.get("snippet") or {}).get("channelTitle", "")[:80],
                         "views": int((v.get("statistics") or {}).get("viewCount", 0) or 0), "region": found[v["id"]]})
    rows.sort(key=lambda r: -r["views"])
    return {"week": f"{(now - timedelta(days=7)):%d %b} to {now:%d %b %Y}", "collected_at": now.isoformat(timespec="seconds"),
            "top": rows[:TOP_N]}


def main(argv=None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    key = os.environ.get("YOUTUBE_API_KEY")
    if not key:
        print("YOUTUBE_API_KEY not set: market scout off")
        return 0
    from .feeds import Http
    try:
        m = scout(Http(), key)
    except Exception as exc:  # noqa: BLE001 - a failed scout never blocks the stats; the URL holds the key, so no details
        print(f"market scout failed: {type(exc).__name__}: {str(exc)[:80]}")
        return 0
    out = config.ROOT / "data" / "growth" / "market.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(m, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"market: {len(m['top'])} Shorts; top: {m['top'][0]['title'] if m['top'] else '-'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
