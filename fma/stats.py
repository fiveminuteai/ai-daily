"""Daily audience numbers across platforms, for the control dashboard's Stats tab.

    python -m fma.stats collect [--date YYYY-MM-DD]     write data/stats/<date>.json

One snapshot per India-time day:
  website    GoatCounter API (free). GOATCOUNTER_TOKEN, site code from `goatcounter:` in config/site.yaml
  instagram  Instagram API (free). INSTAGRAM_TOKEN from the Meta app. With `instagram_id:` in config/site.yaml it is
             the never-expiring system-user token from "API setup with Unified login" (Five Minute AI portfolio),
             read through graph.facebook.com; without it, an Instagram Login token through graph.instagram.com.
             Account insights need the insights permission; without it the profile and post numbers still count
  x, linkedin  no free API for reading stats (X is paid; LinkedIn page stats need Community Management approval),
             so their numbers are typed into the dashboard and kept in data/stats/manual.json

A platform without its token is "off"; one that fails is "error" with the error type and HTTP status only. Request
URLs are never recorded or logged: Instagram's token travels in the query string. API facts checked against
goatcounter.com/help/api and Meta's Instagram Platform reference on 31 Oct 2026.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from datetime import date as Date, datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlencode

from . import config

log = logging.getLogger(__name__)

IG_API = "https://graph.instagram.com/v26.0"
FB_API = "https://graph.facebook.com/v26.0"   # system-user tokens (Unified login)
IG_MEDIA_METRICS = "reach,views,saved,shares,total_interactions"   # "impressions" is deprecated for new media
IG_ACCOUNT_METRICS = "reach,views,accounts_engaged,total_interactions"
REEL_METRICS = "ig_reels_avg_watch_time,ig_reels_video_view_total_time"   # ms; Reels only, asked for separately
IG_POSTS = 12
DAYS = 28


class StatsError(Exception):
    """A platform's request failed. The message never contains a URL or a token."""


def _get_json(http, url: str, headers: dict | None = None) -> dict:
    try:
        r = http.get(url, headers=headers or {})
    except Exception as exc:  # noqa: BLE001 - a network error's message can include the URL (and a token)
        raise StatsError(type(exc).__name__) from None
    if r.status_code >= 400:
        try:                       # Meta's error code says why (190 bad token, 10/200 missing permission); never its text
            code = (r.json().get("error") or {}).get("code")
        except Exception:  # noqa: BLE001
            code = None
        raise StatsError(f"HTTP {r.status_code}" + (f" (Meta error {code})" if isinstance(code, int) else ""))
    try:
        return r.json()
    except ValueError:
        raise StatsError("not JSON") from None


# ---------------------------------------------------------------- website (GoatCounter)

def website(http, site_code: str, token: str, day: str) -> dict:
    end = Date.fromisoformat(day) + timedelta(days=1)
    start = end - timedelta(days=DAYS)
    week = end - timedelta(days=7)
    base = f"https://{site_code}.goatcounter.com/api/v0/stats"
    auth = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    def rng(a: Date) -> str:
        return urlencode({"start": f"{a.isoformat()}T00:00:00Z", "end": f"{end.isoformat()}T00:00:00Z"})

    total = _get_json(http, f"{base}/total?{rng(start)}", auth)
    hits = _get_json(http, f"{base}/hits?{rng(week)}&limit=10", auth)
    refs = _get_json(http, f"{base}/toprefs?{rng(week)}&limit=8", auth)
    daily = [{"day": s.get("day"), "visitors": int(s.get("daily") or 0)} for s in total.get("stats") or [] if s.get("day")]
    return {
        "status": "ok",
        "visitors_28d": int(total.get("total") or 0),
        "visitors_day": next((d["visitors"] for d in daily if d["day"] == day), None),
        "daily": daily,
        "top_paths": [{"path": h.get("path"), "title": h.get("title") or "", "visitors": int(h.get("count") or 0)}
                      for h in (hits.get("hits") or []) if not h.get("event")][:10],
        "top_refs": [{"name": s.get("name") or "(direct)", "visitors": int(s.get("count") or 0)}
                     for s in (refs.get("stats") or [])][:8],
    }


# ---------------------------------------------------------------- Instagram

def _ig(http, path: str, token: str, api: str = IG_API, **params) -> dict:
    return _get_json(http, f"{api}/{path}?{urlencode({**params, 'access_token': token})}")


def _insight_values(data: dict) -> dict:
    """Insights responses: {"data": [{"name": ..., "values": [{"value": n}]} or {"total_value": {"value": n}}]}.
    A metric with no data is left out (the API returns an empty set instead of 0)."""
    out = {}
    for m in data.get("data") or []:
        if "total_value" in m:
            out[m["name"]] = m["total_value"].get("value")
        elif m.get("values"):
            out[m["name"]] = m["values"][-1].get("value")
    return out


def instagram(http, token: str, day: str, ig_id: str | None = None) -> dict:
    api, node = (FB_API, ig_id) if ig_id else (IG_API, "me")
    me = _ig(http, node, token, api, fields="username,followers_count,media_count")
    start = datetime.fromisoformat(f"{day}T00:00:00+05:30")
    acct = {}
    try:
        acct = _insight_values(_ig(http, f"{node}/insights", token, api, metric=IG_ACCOUNT_METRICS, period="day",
                                   metric_type="total_value", since=int(start.timestamp()),
                                   until=int((start + timedelta(days=1)).timestamp())))
    except StatsError as exc:          # account insights need the insights scope; the profile numbers still count
        acct = {"error": str(exc)}
    media = _ig(http, f"{node}/media", token, api, fields="id,caption,timestamp,permalink,like_count,comments_count,media_type",
                limit=IG_POSTS).get("data") or []
    posts = []
    for m in media[:IG_POSTS]:
        try:
            ins = _insight_values(_ig(http, f"{m['id']}/insights", token, api, metric=IG_MEDIA_METRICS))
        except StatsError:
            ins = {}
        if m.get("media_type") == "VIDEO":       # how long people watch: the Reels number that matters most
            try:
                ins.update(_insight_values(_ig(http, f"{m['id']}/insights", token, api, metric=REEL_METRICS)))
            except StatsError:
                pass
        posts.append({"id": m["id"], "timestamp": m.get("timestamp"), "permalink": m.get("permalink"),
                      "type": m.get("media_type"), "caption": (m.get("caption") or "").split("\n")[0][:90],
                      "likes": m.get("like_count"), "comments": m.get("comments_count"),
                      **{k: ins.get(k) for k in ("reach", "views", "saved", "shares", "total_interactions")},
                      "avg_watch_s": round(ins["ig_reels_avg_watch_time"] / 1000, 1)
                      if isinstance(ins.get("ig_reels_avg_watch_time"), (int, float)) else None})
    return {"status": "ok", "username": me.get("username"), "followers": me.get("followers_count"),
            "media_count": me.get("media_count"),
            **({"day": {k: acct.get(k) for k in IG_ACCOUNT_METRICS.split(",")}} if "error" not in acct
               else {"day_error": acct["error"]}),
            "posts": posts}


# ---------------------------------------------------------------- snapshot

def _safely(name: str, fn, *args) -> dict:
    try:
        return fn(*args)
    except StatsError as exc:
        log.warning("%s stats failed: %s", name, exc)
        return {"status": "error", "error": str(exc)}


def collect(http, day: str, site: dict, env: dict | None = None) -> dict:
    env = os.environ if env is None else env
    gc, gc_token, ig_token = site.get("goatcounter"), env.get("GOATCOUNTER_TOKEN"), env.get("INSTAGRAM_TOKEN")
    return {
        "date": day,
        "collected_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "website": _safely("website", website, http, gc, gc_token, day) if gc and gc_token
        else {"status": "off", "note": "set GOATCOUNTER_TOKEN" if gc else "no goatcounter site in config/site.yaml"},
        "instagram": _safely("instagram", instagram, http, ig_token, day, site.get("instagram_id")) if ig_token
        else {"status": "off", "note": "set INSTAGRAM_TOKEN"},
    }


def write_snapshot(root: Path, snap: dict) -> Path:
    path = root / "data" / "stats" / f"{snap['date']}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(snap, ensure_ascii=False, indent=1), encoding="utf-8")
    return path


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="fma.stats")
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("collect")
    c.add_argument("--date")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    from .feeds import Http
    from .pipeline import today_in
    site = config.site_config()
    day = args.date or today_in(site["timezone"])
    snap = collect(Http(), day, site)
    path = write_snapshot(config.ROOT, snap)
    print(f"wrote {path}: " + ", ".join(f"{k} {snap[k]['status']}" for k in ("website", "instagram")))
    return 0       # a platform that failed is recorded in the file, not a failed run


if __name__ == "__main__":
    sys.exit(main())
