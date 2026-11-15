"""The multiplier report (15 Nov 2026): every Reel as a multiple of what is normal for its kind.

From Caleb Ralston's team practice ("How to Build a Personal Brand", 2025): a raw number says little, because a
duo Reel and a card Reel, or this month and last, are not comparable. So each Reel is compared with the MEDIAN of
its own format over the last 90 days and reported as a multiple (1.5x = half again the usual). A Reel is judged
at day 11, because posts often pick up around day 7; before that the multiple is marked early. Four numbers only,
the ones that change what we do: reach, seconds watched, the share that stayed past the first seconds, and sends
plus saves per viewer. (Follows per Reel are not in Instagram's API; the social engine checked, 15 Nov.)

The monthly "top tenth" study lists what ALL the best Reels share and nothing else; it needs 20 judged Reels, and
it never looks at the worst ones. This file only reports. What the system changes on its own stays in fma/learn.py,
with its guards.

    python -m fma.multiplier            rebuild data/learning/multiplier.json and print the table
"""
from __future__ import annotations

import json
import statistics
from datetime import datetime, timedelta, timezone
from pathlib import Path

from . import config

WINDOW_DAYS = 90
JUDGE_HOURS = 11 * 24
TOP_MIN = 20                  # judged Reels needed before the top tenth means anything
TRAITS = ("category", "player", "hook_type", "pain", "pace", "hook_number", "time", "arm")
METRICS = {                   # name -> (how to read it from a row, label)
    "reach": (lambda r: r.get("reach"), "reach"),
    "watch_s": (lambda r: r.get("watch_s"), "seconds watched"),
    "held": (lambda r: None if r.get("skip") is None else 1 - _share(r["skip"]), "stayed past the start"),
    "sent_saved": (lambda r: ((r.get("shares") or 0) + (r.get("saved") or 0)) / r["reach"] if r.get("reach") else None,
                   "sends + saves per viewer"),
}


def _share(x: float) -> float:
    return x / 100 if x > 1 else x          # the API has given the skip rate both as 0-1 and as 0-100


def kind(row: dict) -> str:
    return "plain" if row.get("pace") == "no duo" else "duo"


def build(rows: list[dict], now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    since = (now - timedelta(days=WINDOW_DAYS)).date().isoformat()
    recent = [r for r in rows if r.get("date", "") >= since]
    medians: dict[str, dict] = {}
    for k in sorted({kind(r) for r in recent}):
        group = [r for r in recent if kind(r) == k]
        medians[k] = {"n": len(group)}
        for name, (get, _label) in METRICS.items():
            vals = [v for v in (get(r) for r in group) if v is not None]
            medians[k][name] = round(statistics.median(vals), 4) if vals else None
    out = []
    for r in recent:
        base, mult = medians[kind(r)], {}
        for name, (get, _label) in METRICS.items():
            v, b = get(r), base.get(name)
            mult[name] = round(v / b, 2) if v is not None and b else None
        seen = [m for m in mult.values() if m is not None]
        out.append({"id": r["id"], "date": r["date"], "kind": kind(r), "hook": r.get("hook", "")[:90],
                    "judged": "final" if (r.get("age_h") or 0) >= JUDGE_HOURS else "early",
                    # the geometric mean: a Reel three people saw is not "1.7x" because those three watched long
                    "x": mult, "overall": round(statistics.geometric_mean([max(m, 0.05) for m in seen]), 2) if seen else None,
                    **{t: r.get(t) for t in TRAITS if r.get(t) is not None}})
    out.sort(key=lambda r: (r["overall"] is None, -(r["overall"] or 0)))
    final = [r for r in out if r["judged"] == "final" and r["overall"] is not None]
    study = None
    if len(final) >= TOP_MIN:
        best = final[:max(2, len(final) // 10)]
        shared = {t: best[0][t] for t in TRAITS if t in best[0] and all(b.get(t) == best[0][t] for b in best)}
        # a trait every Reel has is not a finding: it must be rarer among the rest than among the best
        shared = {t: v for t, v in shared.items()
                  if sum(1 for r in final if r.get(t) == v) < len(final) * 0.8}
        study = {"reels": [b["id"] for b in best], "all_share": shared}
    return {"updated": now.isoformat(timespec="seconds"), "window_days": WINDOW_DAYS, "judged_at_days": 11,
            "medians": medians, "reels": out, "judged": len(final), "top_tenth": study,
            "top_tenth_needs": TOP_MIN}


def table(rep: dict, limit: int = 12) -> str:
    lines = [f"{k}: median of {m['n']} Reels: reach {m['reach']}, watched {m['watch_s']} s, stayed {m['held']}, "
             f"sends+saves per viewer {m['sent_saved']}" for k, m in rep["medians"].items()]
    lines.append("")
    for r in rep["reels"][:limit]:
        x = {k: "-" if v is None else f"{v}x" for k, v in r["x"].items()}
        lines.append(f"{r['overall'] if r['overall'] is not None else '  ? '}x  {r['date']} {r['kind']:5} {r['judged']:5} "
                     f"reach {x['reach']} watch {x['watch_s']} stayed {x['held']} share {x['sent_saved']}  {r['hook'][:60]}")
    t = rep["top_tenth"]
    lines.append("")
    lines.append(f"top tenth ({len(t['reels'])} Reels) all share: {t['all_share'] or 'nothing'}" if t else
                 f"top-tenth study: needs {rep['top_tenth_needs']} Reels judged at day 11, has {rep['judged']}")
    return "\n".join(lines)


def update(root: Path | None = None, rows: list[dict] | None = None, now: datetime | None = None) -> dict:
    root = root or config.ROOT
    if rows is None:
        from .learn import dataset
        rows = dataset(root)
    rep = build(rows, now)
    (root / "data/learning").mkdir(parents=True, exist_ok=True)
    (root / "data/learning/multiplier.json").write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")
    return rep


if __name__ == "__main__":
    print(table(update()))
