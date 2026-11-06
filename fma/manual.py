"""A manual day: the pipeline's own stages with a person or a Claude session as the writer and the layer-2 reviewer
(6 Nov 2026). Used when the free models fail, or when they are switched off; docs/MANUAL_DAY.md is the step-by-step
guide. Every check is the same code as an automatic day: layer 1, layer 2's protocol (evidence quotes confirmed word
for word in the source), the gate, the scratch site build and image check.

    python -m fma.manual collect [--pick "title start" ...]   # the day's stories and numbered sources
    python -m fma.manual check                                # draft.json -> layer 1, review.txt, gate
    python -m fma.manual publish                              # commit the post, queue the Reels, add to the bank

The working files live in .manual/<date>/ (not committed)."""
from __future__ import annotations

import argparse
import copy
import json
import pickle
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from . import config

ROOT = config.ROOT


def _today() -> str:
    from zoneinfo import ZoneInfo
    return datetime.now(ZoneInfo(config.site_config().get("timezone", "Asia/Kolkata"))).date().isoformat()


def work(date: str) -> Path:
    d = ROOT / ".manual" / date
    d.mkdir(parents=True, exist_ok=True)
    return d


# ---------------------------------------------------------------- 1. collect

def collect(date: str, picks: list[str]) -> None:
    from .extract import about_title, extract_item
    from .feeds import Http, fetch_all
    from .pipeline import _yaml, load_json
    from .rank import lineup_caps, pick_lineup, rank
    from .write import number_sources

    w = work(date)
    site, srcs = _yaml(ROOT / "config/site.yaml"), _yaml(ROOT / "config/sources.yaml")
    pipe = site.get("pipeline", {})
    now = datetime.now(timezone.utc)
    http = Http()
    items, _stats = fetch_all(srcs, http, now=now)
    ranked = rank(items, srcs, pipe, load_json(ROOT / "data/history.json", []), now, date)
    (w / "ranked.txt").write_text("\n".join(f"{st.score:5.2f} {st.category:9s} {st.title}  [{', '.join(sorted(st.publishers))}]"
                                            for st in ranked[:40]), encoding="utf-8")
    if picks:
        lineup = []
        for t in picks:
            st = next((s for s in ranked if s.title.startswith(t)), None)
            if st is None:
                sys.exit(f"no story starts with {t!r}: see {w / 'ranked.txt'}")
            lineup.append(st)
    else:
        lineup = pick_lineup(ranked, n=int(pipe.get("stories_per_post", 5)) + 2, **lineup_caps(pipe))
    for st in lineup:
        for it in ([st.lead] + [i for i in st.items if i is not st.lead])[:3]:
            it.text = extract_item(it, http)
    lineup = [st for st in lineup if len(st.lead.text or st.lead.summary) >= 200
              and about_title(st.lead.title, st.lead.text or st.lead.summary)] or lineup
    lineup = lineup[:int(pipe.get("stories_per_post", 5))]
    sources, blocks = number_sources(lineup, per_block=True)
    (w / "sources.json").write_text(json.dumps(sources, ensure_ascii=False, indent=1), encoding="utf-8")
    (w / "blocks.txt").write_text("\n\n=========== STORY BLOCK ===========\n\n".join(blocks), encoding="utf-8")
    with open(w / "lineup.pkl", "wb") as f:
        pickle.dump(lineup, f)
    print(f"{len(lineup)} stories, {len(sources)} sources -> {w / 'blocks.txt'}")
    for st in lineup:
        print(f"  - {st.title}  [{', '.join(sorted(st.publishers))}]")


# ---------------------------------------------------------------- 2. check

RATE = {"spark": 5.0, "doubt": 4.8, "rex": 4.6}       # syllables a second, as fma/voice.py CHARACTERS


def _syllables(text: str) -> int:
    n = 0
    for w in re.findall(r"[a-z']+", text.lower()):
        k = len(re.findall(r"[aeiouy]+", w))
        if w.endswith("e") and not w.endswith(("le", "ee")) and k > 1:
            k -= 1
        n += max(1, k)
    return n


def duo_seconds(card: dict) -> float:
    """The duo Reel's length, estimated without the voice engine: syllables over each character's speaking rate, the
    pauses duo_reel adds, and a 1.5 s correction. Calibrated on the four 6 Nov 2026 renders: within 0.6 s of all of
    them (estimated 41.4 / 35.9 / 46.1 / 39.0 s, actual 41.9 / 35.3 / 46.5 / 38.6 s)."""
    from .duo_desk import script
    from .social import plain
    from .voice import OUTRO, spoken
    _guest, lines = script(card, OUTRO)
    t = 0.12 * len(lines) + 1.4 + 1.5
    for who, text, *tags in lines:
        t += _syllables(spoken(plain(text))) / RATE.get(who, 4.8) + (0.16 if who == "spark" else 0.1)
        t += 0.45 if "beat" in tags else 0.0
    return t


def check(date: str) -> bool:
    from .duo_desk import ceiling_problems, problems
    from .feeds import Http
    from .gate import SHORT_EDITION, calm_post, rescue_headline, run_gate, soft_only
    from .pipeline import _yaml, assemble, recent_posts
    from .review import ReviewChain
    from .verify import llm_check, verify_draft
    from .write import normalise_draft

    w = work(date)
    site = _yaml(ROOT / "config/site.yaml")
    pipe = site.get("pipeline", {})
    sources = json.loads((w / "sources.json").read_text(encoding="utf-8"))
    raw = json.loads((w / "draft.json").read_text(encoding="utf-8"))
    raw.setdefault("what_happened", [s.get("bullet", "") for s in raw["sections"]])
    draft = normalise_draft(copy.deepcopy(raw))
    ok = True
    for sec, orig in zip(draft["sections"], raw["sections"]):     # the Reel desk's cards, attached as produce() does
        sec["card"] = copy.deepcopy(orig.get("card"))
        duo = (sec["card"] or {}).get("duo")
        if duo:
            bad = problems(duo) + ceiling_problems(duo["lines"], " ".join(sec.get("paragraphs", [])))
            secs = duo_seconds(sec["card"])
            print(f"duo {sec['title'][:50]!r}: {duo['guest']}, about {secs:.0f} s, {bad or 'rules ok'}")
            if bad or secs > 44:
                ok = False
                print("  FIX: " + "; ".join(bad + ([f"about {secs:.0f} s: cut one exchange (cap 45 s)"] if secs > 44 else [])))
    verified, report = verify_draft(draft, sources, max_quotes=int(pipe.get("max_quotes", 1)))
    l1 = [e for e in report["entries"] if e["status"] == "dropped"]
    print(f"layer 1: {len(l1)} dropped")
    for e in l1:
        print(f"  - {e['where']}: {e['text'][:100]} ({'; '.join(e['problems'])[:140]})")
    reject = json.loads((w / "reject.json").read_text(encoding="utf-8")) if (w / "reject.json").exists() else {}
    verified, report = llm_check(ReviewChain(w / "review.txt", reject), verified, sources, report)
    l2 = [e for e in report["entries"] if e["status"] == "dropped" and e not in l1]
    print(f"layer 2: {len(l2)} dropped; read every claim in {w / 'review.txt'} and list any unsupported ones in reject.json")
    for e in l2:
        print(f"  - {e.get('where')}: {e['text'][:100]} ({'; '.join(e['problems'])[:160]})")
    post = assemble(date, verified, sources, site, "manual day: written and reviewed in a Claude session", report)
    post = rescue_headline(calm_post(post), report)
    fails = run_gate(post, report, pipe, recent_posts(ROOT / "content/posts"), http=Http())
    if fails and soft_only(fails) and not run_gate(post, report, {**pipe, **SHORT_EDITION}, recent_posts(ROOT / "content/posts"),
                                                   http=Http()):
        print(f"gate: short edition ({'; '.join(fails)})")
        post, fails = {**post, "edition": "short"}, []
    print("gate:", "; ".join(fails) if fails else f"PASS, {post['word_count']} words, headline {post['headline']!r}")
    with open(w / "checked.pkl", "wb") as f:
        pickle.dump({"post": post, "report": report, "fails": fails}, f)
    return ok and not fails


# ---------------------------------------------------------------- 3. publish

def reslot(queue: dict, date: str, site: dict, now: datetime) -> list[str]:
    """Reels whose slot has passed (or is under 20 minutes away) move to the next free slot today, else to the
    next morning's first slot, so two Reels never go out together (6 Nov 2026, done by hand)."""
    from .social_queue import reel_slots, slot_utc
    slots = [slot_utc(date, s) for s in reel_slots(site)]
    nxt = (datetime.fromisoformat(date) + timedelta(days=1)).date().isoformat()
    spare = [s for s in slots if datetime.fromisoformat(s) > now + timedelta(minutes=20)]
    spare += [slot_utc(nxt, s) for s in reel_slots(site)]
    reels = [it for it in queue["items"] if it.get("kind") == "reel" and it.get("status") != "posted"]
    taken = set()
    moved = []
    for it in reels:
        free = [s for s in spare if s not in taken]
        if datetime.fromisoformat(it["scheduled_at"]) <= now + timedelta(minutes=20) or it["scheduled_at"] in taken:
            if free:
                it["scheduled_at"] = free[0]
                moved.append(f"{it['id']} -> {free[0]}")
        taken.add(it["scheduled_at"])
    return moved


def publish(date: str) -> None:
    import subprocess

    from .bank import add as bank_add
    from .pipeline import _commit, _yaml, load_json
    from .site import build

    w = work(date)
    checked = pickle.load(open(w / "checked.pkl", "rb"))
    if checked["fails"]:
        sys.exit(f"not published: the gate failed ({checked['fails']}). Run check again after fixing draft.json")
    lineup = pickle.load(open(w / "lineup.pkl", "rb"))
    r = _commit(checked["post"], checked["report"], lineup, load_json(ROOT / "data/history.json", []),
                ROOT / "content/posts", ROOT / "content/reports", ROOT / "data", ROOT, lambda **kw: build(**kw))
    if r.status != "published":
        sys.exit(f"not published: {r.reason}")
    print("published", r.slug)
    subprocess.run([sys.executable, "-m", "fma.social_queue", "build"], check=True, cwd=ROOT)
    q = ROOT / "data/social" / f"{date}.json"
    queue = json.loads(q.read_text(encoding="utf-8"))
    for m in reslot(queue, date, _yaml(ROOT / "config/site.yaml"), datetime.now(timezone.utc)):
        print("moved", m)
    q.write_text(json.dumps(queue, ensure_ascii=False, indent=1), encoding="utf-8")
    print("bank:", bank_add(date))
    print("now: git add content data && git commit && git push")


def main() -> None:
    ap = argparse.ArgumentParser(prog="python -m fma.manual")
    ap.add_argument("step", choices=["collect", "check", "publish"])
    ap.add_argument("--date", default=None)
    ap.add_argument("--pick", action="append", default=[], help="start of a story title from ranked.txt, in order")
    a = ap.parse_args()
    date = a.date or _today()
    if a.step == "collect":
        collect(date, a.pick)
    elif a.step == "check":
        sys.exit(0 if check(date) else 1)
    else:
        publish(date)


if __name__ == "__main__":
    main()
