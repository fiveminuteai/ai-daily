"""The learning loop: what our own Instagram numbers say, turned into small, guarded changes.

    python -m fma.learn update [--lessons]     rebuild data/learning/reels.json and data/learned.json

Pavan, 3 Nov 2026: the system should improve on its own, "but not hallucinate, overfit or underfit". So:

- Evidence only from Instagram's API (data/stats), joined to what we decided (data/social, content/posts). A Reel is
  counted once its numbers are MATURE_HOURS old; earlier numbers are still growing.
- One outcome per Reel, fixed in code: 0.6 x watch time (z-score) + 0.4 x log reach (z-score). Watch time is what
  Instagram rewards with reach, and reach is what grows the page.
- Each feature's effect is shrunk towards zero (empirical Bayes, SHRINK pseudo-Reels of average results) and counts
  only with MIN_N Reels on each side and an effect over twice its standard error. Few Reels means no change: that is
  how it avoids overfitting. A lean towards one category is bounded (MAX_BONUS) and moves at most STEP a week.
- Lessons for the producer are written by a model from the computed table only, each with its numbers; code checks
  every number against the table and drops a lesson that cites anything else (no hallucinated lessons). Lessons
  expire after LESSON_DAYS unless the data still supports them.
- Fixed and never learned: the fact-check, the posting rules, the quality bar's floor, the no-clickbait rules.
"""
from __future__ import annotations

import argparse
import json
import logging
import math
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from statistics import mean, pstdev

from . import config
from .rank import player_of

log = logging.getLogger(__name__)

MATURE_HOURS = 48
SHRINK = 10           # pseudo-Reels of average outcome added to every group
MIN_N = 8             # Reels needed on each side before a feature can count
MAX_BONUS = 1.0       # a category's learned bonus, in Reel-desk points (the bar is 6 of 10)
STEP = 0.25           # largest change to a bonus in one week
LESSONS_MAX, LESSON_DAYS = 5, 28


def _yaml(path: Path) -> dict | None:
    try:
        import yaml
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, ImportError):
        return None


def _load(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def latest_numbers(root: Path) -> dict[str, dict]:
    """Instagram numbers per media id, from the newest stats snapshot that has the post, with its age in hours."""
    out: dict[str, dict] = {}
    for path in sorted((root / "data/stats").glob("20*.json")):
        snap = _load(path) or {}
        ig = snap.get("instagram") or {}
        at = snap.get("collected_at")
        for p in ig.get("posts") or []:
            if not p.get("id") or not p.get("timestamp") or not at:
                continue
            age = (datetime.fromisoformat(at.replace("Z", "+00:00"))
                   - datetime.strptime(p["timestamp"], "%Y-%m-%dT%H:%M:%S%z")).total_seconds() / 3600
            out[str(p["id"])] = {**p, "age_h": round(age, 1)}
    return out


def dataset(root: Path) -> list[dict]:
    """One row per posted Reel with mature numbers: what we decided (features) and what happened (outcome)."""
    numbers = latest_numbers(root)
    rows = []
    players = (_yaml(root / "config/sources.yaml") or {}).get("players", {})
    for qpath in sorted((root / "data/social").glob("20*.json")):
        queue = _load(qpath) or {}
        post = _load(root / "content/posts" / qpath.name) or {}
        for item in queue.get("items", []):
            if item.get("platform") != "instagram_reel" or item.get("status") != "posted":
                continue
            got = numbers.get(str(item.get("media_id")))
            if not got or got["age_h"] < MATURE_HOURS or got.get("reach") is None:
                continue
            secs = post.get("sections") or []
            sec = secs[item["story"]] if isinstance(item.get("story"), int) and item["story"] < len(secs) else {}
            card = sec.get("card") or {}
            hook = re.sub(r"\[S\d+\]", "", item.get("hook") or card.get("hook") or "")
            rows.append({
                "id": item["id"], "date": qpath.stem, "slot": int(item["id"].rsplit("-", 1)[-1]), "time": _ist_hhmm(item.get("scheduled_at")),
                "category": sec.get("category") or "unknown",
                "player": player_of(" ".join([sec.get("title") or "", hook]), players) or "other",
                "hook_number": bool(re.search(r"\d", hook)), "hook_words": len(hook.split()),
                "desk": card.get("reel"), "hook": hook.strip(), "pain": card.get("pain") or "untagged",
                "pace": _pace(card),
                "hook_type": card.get("hook_type") or "untagged",
                "reach": got["reach"], "watch_s": got.get("avg_watch_s"), "shares": got.get("shares") or 0,
                "saved": got.get("saved") or 0, "comments": got.get("comments") or 0, "age_h": got["age_h"]})
    _score(rows)
    return rows


def _pace(card: dict) -> str:
    """9 Nov 2026: "brisk" when every line is 5 s or less and the Reel is 38 s or less (duo Reels only)."""
    if not (card.get("duo") or {}).get("lines"):
        return "no duo"
    from .duo_desk import pacing_problems
    return "brisk" if not pacing_problems(card) else "slow"


def _z(values: list[float]) -> list[float]:
    m, s = mean(values), pstdev(values)
    return [0.0 if s == 0 else (v - m) / s for v in values]


def _score(rows: list[dict]) -> None:
    """The fixed outcome: 0.6 z(watch time) + 0.4 z(log reach); a Reel without watch time counts reach only."""
    if not rows:
        return
    zr = _z([math.log1p(r["reach"]) for r in rows])
    watched = [r for r in rows if r["watch_s"] is not None]
    zw = dict(zip([r["id"] for r in watched], _z([r["watch_s"] for r in watched]))) if watched else {}
    for r, z in zip(rows, zr):
        r["outcome"] = round(0.6 * zw[r["id"]] + 0.4 * z if r["id"] in zw else z, 3)


def _ist_hhmm(iso: str | None) -> str | None:
    try:
        return datetime.fromisoformat(iso).astimezone(timezone(timedelta(hours=5, minutes=30))).strftime("%H:%M")
    except (TypeError, ValueError):
        return None


FEATURES = {
    "category": lambda r: r["category"],
    "player": lambda r: r.get("player", "other"),
    # the time it was scheduled for (schedule.reels can change); older rows fall back to the original slot times
    "slot": lambda r: r.get("time") or {1: "09:00", 2: "13:00", 3: "19:00"}.get(r["slot"], str(r["slot"])),
    "number in hook": lambda r: "yes" if r["hook_number"] else "no",
    "hook length": lambda r: "short (<=10 words)" if r["hook_words"] <= 10 else "long (11+ words)",
    "desk score": lambda r: "none" if r["desk"] is None else ("7+" if r["desk"] >= 7 else "under 7"),
    "pain": lambda r: r.get("pain", "untagged"),            # 9 Nov 2026: the viewer worry the Reel speaks to
    "hook type": lambda r: r.get("hook_type", "untagged"),
    "pace": lambda r: r.get("pace", "no duo"),
}


def effects(rows: list[dict]) -> list[dict]:
    """Per feature value: count, raw mean outcome, shrunk effect against the rest, and whether it is confident."""
    out = []
    for feat, key in FEATURES.items():
        groups: dict[str, list[float]] = {}
        for r in rows:
            groups.setdefault(key(r), []).append(r["outcome"])
        for value, ys in sorted(groups.items()):
            rest = [r["outcome"] for r in rows if key(r) != value]
            if not rest:
                continue
            shrunk = sum(ys) / (len(ys) + SHRINK)            # the overall mean of z-scores is 0
            rest_shrunk = sum(rest) / (len(rest) + SHRINK)
            spread = pstdev([r["outcome"] for r in rows]) or 1.0
            se = spread * math.sqrt(1 / len(ys) + 1 / len(rest))
            effect = shrunk - rest_shrunk
            held = held_out_agrees(rows, key, value, effect)
            out.append({"feature": feat, "value": value, "n": len(ys), "n_rest": len(rest),
                        "mean": round(mean(ys), 2), "effect": round(effect, 2), "se": round(se, 2),
                        "held_out": held,
                        "confident": len(ys) >= MIN_N and len(rest) >= MIN_N and abs(effect) > 2 * se
                                     and held is not False})
    return out


HELD_OUT_MIN = 3      # Reels needed on each side of the newest third before it can confirm or contradict


def held_out_agrees(rows: list[dict], key, value: str, effect: float) -> bool | None:
    """Does the newest third of the Reels, on its own, point the same way as the whole? True, False, or None when
    it has too few Reels on a side to say. A difference that the newest Reels contradict is an old pattern or a
    fluke of a few early posts, so it can't be "confident" (11 Nov 2026: guard against fitting the past)."""
    ordered = sorted(rows, key=lambda r: (str(r.get("date", "")), r.get("slot", 0)))
    recent = ordered[-max(1, len(ordered) // 3):]
    a = [r["outcome"] for r in recent if key(r) == value]
    b = [r["outcome"] for r in recent if key(r) != value]
    if len(a) < HELD_OUT_MIN or len(b) < HELD_OUT_MIN or not effect:
        return None
    return (mean(a) - mean(b)) * effect > 0


def category_bonus(table: list[dict], previous: dict[str, float]) -> dict[str, float]:
    """A bounded lean towards categories that do well, only from confident effects, moving at most STEP a week.
    Without confident evidence a bonus decays towards zero by STEP, so an old lean does not outlive its data."""
    target = {e["value"]: max(-MAX_BONUS, min(MAX_BONUS, e["effect"] * 2))
              for e in table if e["feature"] == "category" and e["confident"]}
    out = {}
    for cat in set(previous) | set(target):
        old, want = previous.get(cat, 0.0), target.get(cat, 0.0)
        new = old + max(-STEP, min(STEP, want - old))
        if abs(new) >= 0.01:
            out[cat] = round(new, 2)
    return out


LESSON_SYSTEM = """You are the analyst of a short-video AI news page. You read a table of our own Reel results and
write lessons for the producer who writes the next Reels. You never state a number that is not in the table, and you
never generalise from a group with few Reels. You reply with one JSON object and nothing else."""


def lesson_prompt(rows: list[dict], table: list[dict]) -> str:
    best = sorted(rows, key=lambda r: -r["outcome"])
    show = lambda r: (f"{r['date']} slot {r['slot']} [{r['category']}] reach {r['reach']}, watch "  # noqa: E731
                      f"{r['watch_s']}s, shares {r['shares']}, saved {r['saved']}: \"{r['hook']}\"")
    lines = "\n".join(f"- {e['feature']} = {e['value']}: n {e['n']}, mean outcome {e['mean']}, effect {e['effect']}"
                      f" (se {e['se']}){' CONFIDENT' if e['confident'] else ''}" for e in table)
    return ("Outcome is 0.6 x watch time + 0.4 x reach, as z-scores (0 = average). Only rows marked CONFIDENT are "
            f"real differences; the rest may be noise.\n\nGROUPS\n{lines}\n\nBEST REELS\n"
            + "\n".join(show(r) for r in best[:5]) + "\n\nWORST REELS\n" + "\n".join(show(r) for r in best[-5:])
            + f"\n\nWrite at most {LESSONS_MAX} lessons for the producer, each one instruction about how to choose or "
            "write a Reel, backed by this table. A lesson may rest ONLY on a group marked CONFIDENT: copy that "
            "group's line (feature = value: n, effect) into evidence. With no CONFIDENT group, reply with an empty "
            'list: that is the right answer, not a failure. '
            'Reply as {"lessons": [{"lesson": "...", "evidence": ["category = tools: n 12, effect 0.6"]}]}.')


def numbers_in(text: str) -> set[str]:
    return set(re.findall(r"-?\d+(?:\.\d+)?", text))


def rests_on_confident(lesson: dict, table: list[dict]) -> bool:
    """True when the lesson's evidence names a group the table marks confident ("feature = value")."""
    ev = " ".join(str(e) for e in lesson.get("evidence") or []).lower()
    return any(f"{e['feature']} = {e['value']}".lower() in ev for e in table if e.get("confident"))


def check_lessons(reply: dict, rows: list[dict], table: list[dict]) -> list[dict]:
    """Keep lessons whose every number appears in the table or the Reel rows shown to the model, and which rest on
    a confident group. 11 Nov 2026: with 0 of 23 groups confident the model still wrote five lessons from noise
    ("target the 13:00 slot", effect 0.03), and the producer was taught them daily. The rule is code now."""
    known = numbers_in(lesson_prompt(rows, table))
    out = []
    for x in (reply.get("lessons") or [])[:LESSONS_MAX] if isinstance(reply, dict) else []:
        if not isinstance(x, dict) or not str(x.get("lesson", "")).strip():
            continue
        text = str(x["lesson"]) + " " + " ".join(str(e) for e in x.get("evidence") or [])
        if not x.get("evidence") or not numbers_in(text) <= known:
            log.warning("lesson dropped, it cites numbers not in our data: %s", x.get("lesson"))
            continue
        if not rests_on_confident(x, table):
            log.warning("lesson dropped, it rests on no confident group: %s", x.get("lesson"))
            continue
        out.append({"lesson": str(x["lesson"]).strip()[:240], "evidence": [str(e)[:120] for e in x["evidence"]][:4]})
    return out


def update(root: Path, chain=None, now: datetime | None = None, lessons: bool = False,
           allow_changes: bool = True) -> dict:
    """Rebuild the dataset and the learned settings. Bonuses move once a week at most; lessons only when asked.
    With allow_changes False (the eval suite is failing, fma/evals.py) the numbers are still rebuilt but no
    setting moves: a system whose checks are broken must not teach itself anything."""
    now = now or datetime.now(timezone.utc)
    rows = dataset(root)
    table = effects(rows) if len(rows) >= 2 else []
    (root / "data/learning").mkdir(parents=True, exist_ok=True)
    (root / "data/learning/reels.json").write_text(
        json.dumps({"updated": now.isoformat(timespec="seconds"), "reels": rows, "effects": table},
                   ensure_ascii=False, indent=1), encoding="utf-8")
    path = root / "data/learned.json"
    old = _load(path) or {}
    learned = {**old, "reels_counted": len(rows), "checked": now.isoformat(timespec="seconds")}
    last = old.get("bonus_changed")
    if allow_changes and (not last or now - datetime.fromisoformat(last) >= timedelta(days=7)):
        bonus = category_bonus(table, old.get("category_bonus", {}))
        if bonus != old.get("category_bonus", {}):
            learned.update(category_bonus=bonus, bonus_changed=now.isoformat(timespec="seconds"))
    # a lesson lives only while it is young AND today's table still marks its group confident: every run re-tests
    # what was learned, so a lesson can't outlive its evidence
    kept = [x for x in old.get("lessons", []) if now - datetime.fromisoformat(x["added"]) < timedelta(days=LESSON_DAYS)
            and rests_on_confident(x, table)]
    if not allow_changes:
        kept = old.get("lessons", [])
        learned["held"] = "eval suite failing: no self-change"
    else:
        learned.pop("held", None)
    if allow_changes and lessons and chain and len(rows) >= 2 * MIN_N:
        try:
            fresh = check_lessons(chain.ask_json(LESSON_SYSTEM, lesson_prompt(rows, table), temperature=0.2),
                                  rows, table)
            kept = [{**x, "added": now.isoformat(timespec="seconds")} for x in fresh]   # the newest data replaces old
        except Exception as exc:  # noqa: BLE001 - lessons are an extra; old ones stay until they expire
            log.warning("lessons failed: %s", exc)
    learned["lessons"] = kept
    record_change(root, old, learned, table, now)
    path.write_text(json.dumps(learned, ensure_ascii=False, indent=1), encoding="utf-8")
    return learned


CHANGES = "data/learning/changes.jsonl"
TRACKED = ("category_bonus", "lessons")       # the settings the loop may change on its own


def _shape(d: dict) -> str:
    return json.dumps({**d, "lessons": [x.get("lesson") for x in d.get("lessons") or []]}, sort_keys=True)


def record_change(root: Path, old: dict, new: dict, table: list[dict], now: datetime) -> None:
    """Every self-change is written down with its reason and the state before it, so it can be read and undone
    (`python -m fma.learn revert`). No change, no line."""
    before = {k: old.get(k) for k in TRACKED}
    after = {k: new.get(k) for k in TRACKED}
    if _shape(before) == _shape(after):
        return
    confident = [f"{e['feature']} = {e['value']}: n {e['n']}, effect {e['effect']} (se {e['se']})"
                 for e in table if e.get("confident")]
    why = ("confident groups: " + "; ".join(confident)) if confident else \
        "no group is confident: leans decay and lessons without support are removed"
    line = {"at": now.isoformat(timespec="seconds"), "reels": new.get("reels_counted"), "why": why,
            "before": before, "after": after}
    f = root / CHANGES
    f.parent.mkdir(parents=True, exist_ok=True)
    with f.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(line, ensure_ascii=False) + chr(10))


def revert(root: Path, now: datetime | None = None) -> dict | None:
    """Undo the newest self-change: put back the settings it replaced, and log the undo. None with nothing to undo."""
    f = root / CHANGES
    try:
        lines = [json.loads(x) for x in f.read_text(encoding="utf-8").splitlines() if x.strip()]
    except OSError:
        return None
    last = next((x for x in reversed(lines) if not x.get("reverted") and not x.get("undo_of")), None)
    if last is None:
        return None
    now = now or datetime.now(timezone.utc)
    path = root / "data/learned.json"
    new = dict(_load(path) or {})
    for k, v in last["before"].items():
        if v is None:
            new.pop(k, None)
        else:
            new[k] = v
    new["bonus_changed"] = now.isoformat(timespec="seconds")       # held for a week before the loop moves it again
    path.write_text(json.dumps(new, ensure_ascii=False, indent=1), encoding="utf-8")
    last["reverted"] = now.isoformat(timespec="seconds")
    lines.append({"at": now.isoformat(timespec="seconds"), "undo_of": last["at"], "why": "reverted by hand",
                  "before": last["after"], "after": last["before"]})
    f.write_text("".join(json.dumps(x, ensure_ascii=False) + chr(10) for x in lines), encoding="utf-8")
    return last


def learned_settings(root: Path | None = None) -> dict:
    return _load((root or config.ROOT) / "data/learned.json") or {}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="fma.learn")
    sub = ap.add_subparsers(dest="cmd", required=True)
    u = sub.add_parser("update")
    u.add_argument("--lessons", action="store_true", help="also ask the model for this week's lessons")
    sub.add_parser("revert", help="undo the newest self-change (data/learning/changes.jsonl)")
    args = ap.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if args.cmd == "revert":
        done = revert(config.ROOT)
        print(f"reverted the change of {done['at']}: {done['why']}" if done else "nothing to revert")
        return 0
    chain = None
    if args.lessons:
        from .llm import Chain, providers_from_config
        chain = Chain(providers_from_config(config.site_config()))
    from .evals import passing
    ok = passing(config.ROOT)
    if not ok:
        print("::warning::eval suite failing (python -m fma.evals): the learning loop changes nothing today")
    out = update(config.ROOT, chain, lessons=args.lessons, allow_changes=ok)
    print(f"{out['reels_counted']} mature Reels; category bonus {out.get('category_bonus', {})}; "
          f"{len(out.get('lessons', []))} lessons")
    return 0


if __name__ == "__main__":
    sys.exit(main())
