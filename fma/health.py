"""The daily live health check (11 Nov 2026, Pavan: "expand the test loop to every platform and the dashboard").

Unit tests prove the code; this proves the day. It reads only public pages and the repo's own records, posts
nothing, and checks each layer where a reader would meet it:

  post      today's post exists, has its stories and words, isn't a silent short edition
  site      home, today's post, about, llms.txt, sitemap and feed answer 200; JSON-LD parses
  media     share/<date>/media.json: every Reel rendered, voiced, 25-45 s, duo where the card has a duo, with a cover
  queue     nothing approved is overdue, every posted item has its link, YouTube mirrored or explained, no errors
  instagram (with IG_ACCESS_TOKEN) each posted media id is live on Instagram, and the token isn't about to expire
  dashboard the control dashboard answers

Every finding is FAIL (the day is broken: fix it) or WARN (degraded: look at it). `python -m fma.health` prints the
report, writes data/health/<date>.json for the dashboard, and exits 1 on any FAIL so the workflow goes red and GitHub
emails the owner.

    python -m fma.health [--date YYYY-MM-DD] [--offline] [--at HH:MM]
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from . import config

IST = ZoneInfo("Asia/Kolkata")
GRACE = timedelta(minutes=40)        # a post-scheduled run may start up to ~30 min late on GitHub's cron
REEL_SECONDS = (25.0, 45.5)
MIN_STORIES = 5
MIN_WORDS = 880


class Report:
    def __init__(self, date: str):
        self.date, self.items = date, []

    def add(self, level: str, area: str, msg: str) -> None:
        self.items.append({"level": level, "area": area, "msg": msg})

    def fail(self, area: str, msg: str) -> None:
        self.add("FAIL", area, msg)

    def warn(self, area: str, msg: str) -> None:
        self.add("WARN", area, msg)

    def ok(self, area: str, msg: str) -> None:
        self.add("OK", area, msg)

    @property
    def failed(self) -> bool:
        return any(i["level"] == "FAIL" for i in self.items)

    def as_dict(self) -> dict:
        n = {lv: sum(1 for i in self.items if i["level"] == lv) for lv in ("FAIL", "WARN", "OK")}
        return {"date": self.date, "checked_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "status": "fail" if n["FAIL"] else "warn" if n["WARN"] else "ok", "counts": n, "items": self.items}


# ---------------------------------------------------------------- the checks (pure: data in, findings out)

def check_post(r: Report, post: dict | None, run: dict | None) -> None:
    if not post:
        reason = (run or {}).get("reason") or "no run summary either"
        r.fail("post", f"no post for {r.date} ({reason})")
        return
    n, words = len(post.get("sections", [])), int(post.get("word_count", 0))
    if post.get("edition") == "short" or n < MIN_STORIES or words < MIN_WORDS:
        fails = "; ".join(f for a in (run or {}).get("attempts", []) for f in a.get("fails", []))[:300]
        r.warn("post", f"short day: {n} stories, {words} words" + (f" (gate: {fails})" if fails else ""))
    else:
        r.ok("post", f"{n} stories, {words} words")
    carded = [k for k, s in enumerate(post.get("sections", [])) if (s.get("card") or {}).get("hook")]
    if not carded:
        r.fail("post", "no story has a Reel card: no Reels today")


def check_media(r: Report, media: dict | None, post: dict | None) -> None:
    if media is None:
        r.fail("media", "share/<date>/media.json missing: the deploy didn't render today's media")
        return
    if media.get("slug") and post and media["slug"] != post.get("slug"):
        r.fail("media", f"media.json is for {media['slug']}, not today's post {post.get('slug')}")
    if not media.get("voice"):
        r.fail("media", "Reels rendered without a voice (Kokoro missing in the deploy)")
    if not media.get("slides"):
        r.fail("media", "no carousel slides rendered")
    sections = (post or {}).get("sections", [])
    for k, reel in enumerate(media.get("reels", []), 1):
        name = reel.get("file") or f"Reel {k}"
        if not reel.get("file"):
            r.fail("media", f"Reel {k} failed to render: {reel.get('error', '?')}")
            continue
        sec = sections[reel["story"]] if isinstance(reel.get("story"), int) and reel["story"] < len(sections) else {}
        has_duo = bool((sec.get("card") or {}).get("duo"))
        if reel.get("duo"):
            r.ok("media", f"{name}: duo with {reel['duo']}")
        elif has_duo:
            r.fail("media", f"{name}: the card has a duo but the Reel is plain ({reel.get('plain_because', '?')})")
        else:
            r.warn("media", f"{name}: plain Reel ({reel.get('plain_because', 'card has no duo')})")
        secs = reel.get("seconds")
        if secs is None:
            r.warn("media", f"{name}: length not measured")
        elif not REEL_SECONDS[0] <= secs <= REEL_SECONDS[1]:
            r.fail("media", f"{name}: {secs} s, outside {REEL_SECONDS[0]:.0f}-{REEL_SECONDS[1]:.0f} s")
        if reel.get("audio") is False:
            r.fail("media", f"{name}: no audio stream")
        if not reel.get("cover"):
            r.warn("media", f"{name}: no cover image")


def _when(item: dict) -> datetime | None:
    try:
        return datetime.fromisoformat(item["scheduled_at"]) if item.get("scheduled_at") else None
    except ValueError:
        return None


def check_queue(r: Report, queue: dict | None, now: datetime, media: dict | None = None) -> None:
    if not queue:
        r.fail("queue", "no posting queue for today (data/social/<date>.json)")
        return
    reels_rendered = len((media or {}).get("reels", [])) if media else None
    reels_queued = sum(1 for i in queue.get("items", []) if i.get("kind") == "reel")
    if reels_rendered is not None and reels_queued != reels_rendered:
        r.fail("queue", f"{reels_queued} Reels queued but {reels_rendered} rendered")
    for it in queue.get("items", []):
        iid, st, when = it.get("id", "?"), it.get("status"), _when(it)
        auto = it.get("posting") == "api"
        if st == "posted":
            if not it.get("posted_url"):
                r.fail("queue", f"{iid}: marked posted but has no link")
            else:
                r.ok("queue", f"{iid}: posted {it['posted_url']}")
            if it.get("kind") == "reel" and not it.get("youtube_url"):
                r.warn("queue", f"{iid}: not on YouTube ({it.get('youtube_error') or 'no record'})")
        elif st == "failed":
            r.fail("queue", f"{iid}: failed: {it.get('error') or '?'}")
        elif auto and st == "approved" and when and now > when + GRACE:
            r.fail("queue", f"{iid}: approved for {when.astimezone(IST):%H:%M} IST and still not posted "
                            f"({it.get('error') or 'no error recorded'})")
        elif auto and st == "pending" and when and now > when:
            r.warn("queue", f"{iid}: its time passed but it was never approved")
        if it.get("error") and st != "failed":
            r.warn("queue", f"{iid}: last error: {str(it['error'])[:200]}")


def check_pages(r: Report, http, origin: str, post: dict | None) -> None:
    pages = ["", "about/", "llms.txt", "sitemap.xml", "feed.xml"]
    if post:
        pages.insert(1, post.get("url_path") or f"posts/{post['slug']}/")
    for path in pages:
        url = f"{origin}/{path}"
        try:
            resp = http.get(url, timeout=30)
        except Exception as exc:  # noqa: BLE001
            r.fail("site", f"{url}: {type(exc).__name__}")
            continue
        if resp.status_code != 200:
            (r.warn if path == "feed.xml" and resp.status_code == 404 else r.fail)("site", f"{url}: HTTP {resp.status_code}")
            continue
        if path.endswith("/") and path:
            for blob in re.findall(r'<script type="application/ld\+json">(.*?)</script>', resp.text, re.S):
                try:
                    json.loads(blob)
                except ValueError:
                    r.fail("site", f"{url}: JSON-LD doesn't parse")
        if post and path == (post.get("url_path") or f"posts/{post['slug']}/") and post.get("headline", "")[:30] \
                and post["headline"][:30].split()[0] not in resp.text:
            r.fail("site", f"{url}: live page doesn't show today's headline (old deploy?)")
    r.ok("site", f"{len(pages)} pages checked")


def check_media_files(r: Report, http, origin: str, date: str, media: dict | None) -> None:
    for reel in (media or {}).get("reels", []):
        if not reel.get("file"):
            continue
        url = f"{origin}/share/{date}/{reel['file']}"
        try:
            resp = http.head(url, timeout=30, allow_redirects=True)
            if resp.status_code != 200:
                r.fail("media", f"{url}: HTTP {resp.status_code}")
        except Exception as exc:  # noqa: BLE001
            r.fail("media", f"{url}: {type(exc).__name__}")


def check_instagram(r: Report, http, queue: dict | None, token: str) -> None:
    """Read-only Graph API calls: each posted item's media id still resolves, and the token's expiry."""
    base = "https://graph.facebook.com/v26.0"
    for it in (queue or {}).get("items", []):
        if it.get("status") == "posted" and it.get("media_id") and it.get("platform", "").startswith("instagram"):
            try:
                resp = http.get(f"{base}/{it['media_id']}", params={"fields": "id,permalink", "access_token": token},
                                timeout=30)
                if resp.status_code != 200:
                    r.fail("instagram", f"{it['id']}: media {it['media_id']} not found (HTTP {resp.status_code})")
            except Exception as exc:  # noqa: BLE001
                r.warn("instagram", f"{it['id']}: couldn't check ({type(exc).__name__})")
    try:
        resp = http.get(f"{base}/debug_token", params={"input_token": token, "access_token": token}, timeout=30)
        exp = (resp.json().get("data") or {}).get("expires_at") if resp.status_code == 200 else None
        if exp:
            days = (datetime.fromtimestamp(exp, timezone.utc) - datetime.now(timezone.utc)).days
            (r.fail if days < 7 else r.warn if days < 14 else r.ok)("instagram", f"token expires in {days} days")
    except Exception as exc:  # noqa: BLE001
        r.warn("instagram", f"token expiry unknown ({type(exc).__name__})")


def check_youtube(r: Report, http) -> None:
    """The YouTube sign-in still refreshes (uploads nothing). A revoked or expired token fails here in the
    morning instead of at the first Short."""
    from .youtube import _token, configured
    if not configured():
        return
    try:
        _token(http, os.environ)
        r.ok("youtube", "sign-in refreshes")
    except Exception as exc:  # noqa: BLE001
        r.fail("youtube", f"sign-in no longer works: {str(exc)[:200]}")


def check_dashboard(r: Report, http, url: str | None) -> None:
    if not url:
        return
    try:
        resp = http.get(url, timeout=30, allow_redirects=False)
        # behind Cloudflare Access a healthy app answers with its sign-in redirect; only a server error is down
        (r.ok if resp.status_code < 500 else r.fail)("dashboard", f"{url}: HTTP {resp.status_code}")
    except Exception as exc:  # noqa: BLE001
        r.fail("dashboard", f"{url}: {type(exc).__name__}")


# ---------------------------------------------------------------- running it

def _load(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def run(date: str, now: datetime, root: Path | None = None, http=None, offline: bool = False) -> Report:
    root = root or config.ROOT
    site = config.site_config()
    origin = str(site.get("base_url") or "https://fiveminuteai.net").rstrip("/")
    r = Report(date)
    post = _load(root / "content/posts" / f"{date}.json")
    run_summary = _load(root / "data/runs" / f"{date}.json")
    queue = _load(root / "data/social" / f"{date}.json")
    media = None
    if not offline and http is not None:
        try:
            resp = http.get(f"{origin}/share/{date}/media.json", timeout=30)
            media = resp.json() if resp.status_code == 200 else None
        except Exception:  # noqa: BLE001
            media = None
    check_post(r, post, run_summary)
    if not offline:
        check_media(r, media, post)
    check_queue(r, queue, now, media)
    if not offline and http is not None:
        check_pages(r, http, origin, post)
        check_media_files(r, http, origin, date, media)
        if os.environ.get("IG_ACCESS_TOKEN"):
            check_instagram(r, http, queue, os.environ["IG_ACCESS_TOKEN"])
        check_youtube(r, http)
        check_dashboard(r, http, os.environ.get("FMA_DASHBOARD_URL") or (site.get("dashboard") or {}).get("url"))
    return r


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m fma.health")
    ap.add_argument("--date")
    ap.add_argument("--offline", action="store_true", help="repo records only, no network")
    ap.add_argument("--write", action="store_true", help="save data/health/<date>.json")
    a = ap.parse_args(argv)
    now = datetime.now(timezone.utc)
    date = a.date or now.astimezone(IST).date().isoformat()
    http = None
    if not a.offline:
        import requests
        http = requests.Session()
        http.headers["User-Agent"] = "fiveminuteai-health/1.0"
    rep = run(date, now, http=http, offline=a.offline)
    for i in rep.items:
        if i["level"] != "OK":
            print(f"{i['level']:4} {i['area']:9} {i['msg']}")
    d = rep.as_dict()
    print(f"health {date}: {d['status'].upper()} ({d['counts']['FAIL']} fail, {d['counts']['WARN']} warn, "
          f"{d['counts']['OK']} ok)")
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as f:
            f.write(f"## Health {date}: {d['status'].upper()}\n\n| Level | Area | Finding |\n|---|---|---|\n")
            f.writelines(f"| {i['level']} | {i['area']} | {i['msg'].replace('|', '/')} |\n" for i in rep.items)
    if a.write:
        out = config.ROOT / "data/health" / f"{date}.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    return 1 if rep.failed else 0


if __name__ == "__main__":
    sys.exit(main())
