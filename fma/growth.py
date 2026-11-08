"""The growth scoreboard (8 Nov 2026, docs/growth-strategy.md).

Instagram decides how many non-followers see a Reel mostly from three things: how long people watch, how many send
it to someone, and how many like it, each per account reached (Adam Mosseri, Jan 2025). So the scoreboard follows
one Reel's path through those gates and says which gate is losing us the most people this week:

  reach -> stay past 3 s (1 - skip rate) -> watch time -> send / save / like / comment -> follow

Built every evening from data/stats/<date>.json (fma/stats.py) and the Reel queues (data/social). Writes
data/growth/scoreboard.json and data/growth/scoreboard.md. Code only, no model: the numbers are the numbers.

Targets are ours, not Instagram's (no official benchmarks exist for accounts under 1,000 followers). They step up
each phase of the plan; see TARGETS."""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

from . import config

# The plan's gates. Phase 1 (to 6 Dec 2026): get people to stay. The numbers on 8 Nov 2026: skip rate unknown,
# average watch 5.5-11 s of ~40 s, 0 sends, 0 saves, 0 comments, 2 followers.
TARGETS = {
    "skip_rate": ("at most", 45.0, "% leave in the first 3 s"),
    "avg_watch_s": ("at least", 15.0, "s watched on average"),
    "sends_per_1k": ("at least", 5.0, "sends per 1,000 reached"),
    "likes_per_1k": ("at least", 30.0, "likes per 1,000 reached"),
    "follows_per_week": ("at least", 15.0, "new followers a week"),
}
WINDOW_DAYS = 7


def _load(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def snapshots(root: Path) -> list[dict]:
    return [s for s in (_load(p) for p in sorted((root / "data" / "stats").glob("20*.json"))) if s]


def reel_index(root: Path) -> dict[str, dict]:
    """media id -> what we know about the Reel from our own queue (date, slot, story, YouTube copy)."""
    out = {}
    for p in sorted((root / "data" / "social").glob("20*.json")):
        q = _load(p) or {}
        for it in q.get("items", []):
            if it.get("platform") == "instagram_reel" and it.get("media_id"):
                out[str(it["media_id"])] = {"id": it["id"], "hook": it.get("hook", ""), "youtube": it.get("youtube_url"),
                                            "scheduled_at": it.get("scheduled_at")}
    return out


def _per_1k(n, reach) -> float | None:
    if not isinstance(n, (int, float)) or not reach:
        return None
    return round(1000 * n / reach, 1)


def rows(root: Path) -> list[dict]:
    snaps = snapshots(root)
    if not snaps:
        return []
    ig = (snaps[-1].get("instagram") or {})
    known = reel_index(root)
    out = []
    for m in ig.get("posts") or []:
        if m.get("type") != "VIDEO":
            continue
        reach = m.get("reach") or 0
        out.append({"id": m["id"], "day": (m.get("timestamp") or "")[:10], "caption": m.get("caption", ""),
                    "reach": reach, "skip_rate": m.get("skip_rate"), "avg_watch_s": m.get("avg_watch_s"),
                    "likes_per_1k": _per_1k(m.get("likes"), reach), "sends_per_1k": _per_1k(m.get("shares"), reach),
                    "saves_per_1k": _per_1k(m.get("saved"), reach), "comments": m.get("comments") or 0,
                    "ours": known.get(str(m["id"]), {}).get("id"), "youtube": known.get(str(m["id"]), {}).get("youtube")})
    return out


def followers(root: Path) -> list[tuple[str, int]]:
    return [(s["date"], s["instagram"]["followers"]) for s in snapshots(root)
            if isinstance((s.get("instagram") or {}).get("followers"), int)]


def _median(xs: list) -> float | None:
    xs = [x for x in xs if isinstance(x, (int, float))]
    return round(statistics.median(xs), 1) if xs else None


def summary(rs: list[dict], fol: list[tuple[str, int]], today: date) -> dict:
    start = (today - timedelta(days=WINDOW_DAYS - 1)).isoformat()
    prev = (today - timedelta(days=2 * WINDOW_DAYS - 1)).isoformat()
    week = [r for r in rs if r["day"] >= start]
    last = [r for r in rs if prev <= r["day"] < start]

    def block(xs):
        return {"reels": len(xs), "reach": _median([r["reach"] for r in xs]),
                **{k: _median([r[k] for r in xs]) for k in ("skip_rate", "avg_watch_s", "likes_per_1k", "sends_per_1k",
                                                            "saves_per_1k")},
                "comments": sum(r["comments"] for r in xs)}
    f_now = fol[-1][1] if fol else None
    f_then = next((n for d, n in reversed(fol) if d <= (today - timedelta(days=WINDOW_DAYS)).isoformat()), None)
    if f_then is None and fol:
        f_then = fol[0][1]
    this = block(week)
    this["follows_per_week"] = (f_now - f_then) if f_now is not None and f_then is not None else None
    return {"date": today.isoformat(), "window": [start, today.isoformat()], "this_week": this,
            "last_week": block(last), "followers": f_now, "gates": gates(this), "best": best(week)}


def gates(this: dict) -> list[dict]:
    """Each target with this week's number and whether it is met; the first unmet one is the bottleneck."""
    out = []
    for key, (how, goal, what) in TARGETS.items():
        v = this.get(key)
        ok = None if v is None else (v <= goal if how == "at most" else v >= goal)
        out.append({"metric": key, "value": v, "target": f"{how} {goal:g}", "what": what, "met": ok})
    return out


def best(week: list[dict]) -> list[dict]:
    """The week's Reels, best first: watch time first (it decides reach), then sends."""
    return sorted(week, key=lambda r: (-(r["avg_watch_s"] or 0), -(r["sends_per_1k"] or 0)))[:3]


ADVICE = {
    "skip_rate": "People scroll past in the first 3 s: test stronger first lines and covers (the hook, not the facts).",
    "avg_watch_s": "People leave mid-Reel: shorter scripts, the punchline earlier, fewer numbers per line.",
    "sends_per_1k": "Nobody sends it on: pick stories people argue about, end on a line worth forwarding.",
    "likes_per_1k": "Watched but not liked: sharper jokes, a clear point of view in the take.",
    "follows_per_week": "Seen but not followed: profile and pinned Reels must say what you get by following.",
}


def markdown(s: dict) -> str:
    t, l = s["this_week"], s["last_week"]

    def f(v, unit=""):
        return "n/a" if v is None else f"{v:g}{unit}"
    lines = [f"# Growth scoreboard, {s['date']}", "",
             f"Followers: **{f(s['followers'])}**. Reels this week: {t['reels']} (last week {l['reels']}).", "",
             "| Gate | This week | Last week | Target | |", "|---|---|---|---|---|"]
    for g in s["gates"]:
        mark = "n/a" if g["met"] is None else ("met" if g["met"] else "**not yet**")
        lines.append(f"| {g['what']} | {f(g['value'])} | {f(l.get(g['metric']))} | {g['target']} | {mark} |")
    lines += ["", f"Median reach per Reel: {f(t['reach'])} (last week {f(l['reach'])}). Comments: {t['comments']}.", ""]
    stuck = next((g for g in s["gates"] if g["met"] is False), None)
    if stuck:
        lines += [f"**Bottleneck: {stuck['what']}.** {ADVICE[stuck['metric']]}", ""]
    if s["best"]:
        lines.append("Best Reels this week (by watch time):")
        lines += [f"- {r['caption'][:70]} ({f(r['avg_watch_s'], ' s')}, reach {r['reach']}, "
                  f"skip {f(r['skip_rate'], '%')})" for r in s["best"]]
    return "\n".join(lines) + "\n"


def write(root: Path, today: date | None = None) -> dict:
    today = today or datetime.now().date()
    s = summary(rows(root), followers(root), today)
    out = root / "data" / "growth"
    out.mkdir(parents=True, exist_ok=True)
    (out / "scoreboard.json").write_text(json.dumps(s, ensure_ascii=False, indent=1), encoding="utf-8")
    (out / "scoreboard.md").write_text(markdown(s), encoding="utf-8")
    return s


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="fma.growth")
    ap.add_argument("--date")
    args = ap.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    s = write(config.ROOT, date.fromisoformat(args.date) if args.date else None)
    print(markdown(s))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
