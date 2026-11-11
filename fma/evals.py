"""The eval suite: known answers, pass bars, and the gate on every self-change (11 Nov 2026, Pavan: "measured, not
claimed"; the loop may only change itself while these pass).

    python -m fma.evals [--write]        prints the table; exit 1 when a bar is missed; --write saves data/evals/

Unit tests prove a function does what its author meant. These measure how well the system's judgement works on real
material, as rates against a bar:

  facts-true     published claims (each checked by hand or by both layers when it ran) still pass the code check
  facts-broken   the same claims with a number changed or a limit dropped are caught
  numbers        rounded figures pass, wrong ones and rounded percentages don't
  dedupe         hand-labelled headline pairs: same event or not
  speech         numbers and names are spelled for the voice as people say them
  decency-bad    indecent or mean lines are refused (and private-life jokes on sensitive stories)
  decency-clean  every guest line already published passes (false alarms)
  gate           known-bad posts (repeats, dangling openers, thin sections) are refused
  learn-noise    on Reels with no real pattern, the learning loop finds nothing (overfitting guard)
  learn-signal   on Reels with a planted real pattern, it finds it (underfitting guard)

No network, no model calls: it runs in seconds on any machine, in CI and before the nightly learning step
(collect-stats.yml). A case is added to evals/golden.json whenever something slips; a bar is never lowered to let
a change through.
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from datetime import datetime, timezone
from pathlib import Path

from . import config

GOLDEN = "evals/golden.json"
# (suite, bar, what the rate means). Bars were set on 11 Nov 2026 from the first measured run, below it by a small
# margin where the measure is noisy, at 1.0 where a single miss is a real incident.
BARS = {
    "facts-true": 0.97, "facts-broken": 0.90, "numbers": 1.0, "dedupe": 0.93, "speech": 1.0,
    "decency-bad": 1.0, "decency-clean": 1.0, "gate": 1.0, "learn-noise": 0.95, "learn-signal": 0.90,
}


def _load(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def facts(root: Path) -> tuple[dict, dict]:
    """Layer 1 (fma/verify.check_sentence) on every published day that kept its sources."""
    import re

    from .judge import broken, claims_of
    from .verify import check_sentence, cites, corpus, plain
    rnd = random.Random(7)
    true = {"n": 0, "ok": 0, "misses": []}
    brk = {"n": 0, "ok": 0, "misses": []}
    for src_file in sorted((root / "data/sources").glob("*.json")):
        post = _load(root / "content/posts" / src_file.name)
        sources = _load(src_file) or []
        if not post or not sources:
            continue
        corpora = {s["id"]: corpus(s) for s in sources}
        vocab = set(re.findall(r"[a-z][a-z'\-]+", " ".join(corpora.values())))
        for claim in claims_of(post):
            ids = [i for i in cites(claim) if i in corpora]
            if not ids:
                continue
            true["n"] += 1
            problems = check_sentence(claim, ids, corpora, vocab)
            if not problems:
                true["ok"] += 1
            elif len(true["misses"]) < 8:
                true["misses"].append(f"{src_file.stem}: {claim[:90]} -> {problems[0]}")
            b = broken(claim, rnd)
            if b and re.search(r"\d", plain(claim)):          # number changes are what layer 1 exists to catch; a dropped
                brk["n"] += 1                          # "at least" or a flipped "not" is layer 2's and the judge's job
                if check_sentence(b, ids, corpora, vocab):
                    brk["ok"] += 1
                elif len(brk["misses"]) < 8:
                    brk["misses"].append(f"{src_file.stem}: passed: {b[:90]}")
    return true, brk


def numbers(gold: dict) -> dict:
    from .verify import norm, number_ok
    out = {"n": 0, "ok": 0, "misses": []}
    for c in gold["numbers"]:
        out["n"] += 1
        got = number_ok(*c["claim"], norm(c["source"]))
        if got == c["ok"]:
            out["ok"] += 1
        else:
            out["misses"].append(f"{c['claim']} vs {c['source']!r}: got {got}")
    return out


def dedupe(gold: dict) -> dict:
    from .rank import second_angle
    out = {"n": 0, "ok": 0, "misses": []}
    for c in gold["dedupe"]:
        out["n"] += 1
        got = second_angle(c["a"], c["b"])
        if got == c["same"]:
            out["ok"] += 1
        else:
            out["misses"].append(f"{'missed' if c['same'] else 'wrongly merged'}: {c['a'][:50]} | {c['b'][:50]}")
    return out


def speech(gold: dict) -> dict:
    from .voice import spoken
    out = {"n": 0, "ok": 0, "misses": []}
    for c in gold["speech"]:
        out["n"] += 1
        if spoken(c["text"]) == c["spoken"]:
            out["ok"] += 1
        else:
            out["misses"].append(f"{c['text']!r} -> {spoken(c['text'])!r}")
    return out


def decency(root: Path, gold: dict) -> tuple[dict, dict]:
    from .duo_desk import joke_problems
    bad = {"n": 0, "ok": 0, "misses": []}
    for line, sens in [(x, False) for x in gold["decency_bad"]] + [(x, True) for x in gold["decency_sensitive_bad"]]:
        bad["n"] += 1
        if joke_problems(line, sens):
            bad["ok"] += 1
        else:
            bad["misses"].append(f"let through: {line}")
    clean = {"n": 0, "ok": 0, "misses": []}
    for f in sorted((root / "content/posts").glob("*.json")):
        for sec in (_load(f) or {}).get("sections", []):
            duo = (sec.get("card") or {}).get("duo") or {}
            for ln in duo.get("lines", []):
                if ln.get("who") != "guest":
                    continue
                clean["n"] += 1
                why = joke_problems(ln["text"], bool(duo.get("sensitive")))
                if not why:
                    clean["ok"] += 1
                elif len(clean["misses"]) < 8:
                    clean["misses"].append(f"{f.stem}: {ln['text'][:70]} -> {why[0]}")
    return bad, clean


def gate(gold: dict) -> dict:
    from .gate import quality_problems
    out = {"n": 0, "ok": 0, "misses": []}
    for c in gold["gate_bad_posts"]:
        out["n"] += 1
        if quality_problems({"sections": [{"title": "T", "paragraphs": c["paragraphs"]}]}):
            out["ok"] += 1
        else:
            out["misses"].append(f"accepted: {c['why']}")
    return out


def _reels(rnd: random.Random, n: int, planted: float = 0.0) -> list[dict]:
    """Synthetic mature Reels with the features the loop reads. `planted` adds that much watch time (in standard
    deviations) to every "tools" Reel: a real pattern for the loop to find. Without it there is nothing to find."""
    from . import learn
    rows = []
    for k in range(n):
        cat = rnd.choice(["tools", "policy", "models", "products"])
        watch = rnd.gauss(6.0, 2.0) + (planted * 2.0 if cat == "tools" else 0.0)
        rows.append({"id": f"r{k}", "date": f"2026-{10 + k // 28:02d}-{1 + k % 28:02d}", "slot": 1 + k % 3,
                     "time": rnd.choice(["09:00", "13:00", "19:00"]), "category": cat,
                     "player": rnd.choice(["giant", "other"]), "hook_number": rnd.random() < 0.5,
                     "hook_words": rnd.randint(7, 13), "desk": rnd.choice([6, 7, 8]),
                     "pain": rnd.choice(["money", "job", "privacy"]), "hook_type": rnd.choice(["number", "question"]),
                     "pace": rnd.choice(["brisk", "slow"]), "hook": f"hook {k}", "reach": max(1, int(rnd.gauss(60, 25))),
                     "watch_s": max(0.5, watch), "shares": 0, "saved": 0, "comments": 0, "age_h": 72})
    learn._score(rows)
    return rows


def learning(trials: int = 200) -> tuple[dict, dict]:
    """Overfitting: across `trials` sets of 40 patternless Reels, how often does the loop change nothing at all?
    Underfitting: with a strong planted pattern in 90 Reels, how often does it mark that group confident?"""
    from . import learn
    rnd = random.Random(11)
    noise = {"n": trials, "ok": 0, "misses": []}
    for t in range(trials):
        table = learn.effects(_reels(rnd, 40))
        hits = [e for e in table if e["confident"]]
        if not hits and not learn.category_bonus(table, {}):
            noise["ok"] += 1
        elif len(noise["misses"]) < 5:
            noise["misses"].append(f"trial {t}: 'found' {hits[0]['feature']} = {hits[0]['value']} (effect {hits[0]['effect']})")
    signal = {"n": trials, "ok": 0, "misses": []}
    for t in range(trials):
        table = learn.effects(_reels(rnd, 90, planted=1.5))
        tools = next((e for e in table if e["feature"] == "category" and e["value"] == "tools"), None)
        if tools and tools["confident"] and tools["effect"] > 0:
            signal["ok"] += 1
        elif len(signal["misses"]) < 5:
            signal["misses"].append(f"trial {t}: missed the planted pattern ({tools})")
    return noise, signal


def run(root: Path | None = None) -> dict:
    root = root or config.ROOT
    gold = _load(root / GOLDEN) or {}
    res: dict[str, dict] = {}
    res["facts-true"], res["facts-broken"] = facts(root)
    res["numbers"] = numbers(gold)
    res["dedupe"] = dedupe(gold)
    res["speech"] = speech(gold)
    res["decency-bad"], res["decency-clean"] = decency(root, gold)
    res["gate"] = gate(gold)
    res["learn-noise"], res["learn-signal"] = learning()
    rows = []
    for name, bar in BARS.items():
        r = res[name]
        rate = r["ok"] / r["n"] if r["n"] else None
        rows.append({"suite": name, "n": r["n"], "passed": r["ok"], "rate": None if rate is None else round(rate, 3),
                     "bar": bar, "ok": rate is not None and rate >= bar, "misses": r["misses"]})
    return {"at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "ok": all(x["ok"] for x in rows),
            "suites": rows}


def passing(root: Path | None = None) -> bool:
    """The gate the learning loop asks before it changes anything. A suite that cannot run counts as failing."""
    try:
        return bool(run(root)["ok"])
    except Exception:  # noqa: BLE001
        return False


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m fma.evals")
    ap.add_argument("--write", action="store_true", help="save data/evals/latest.json and append history.jsonl")
    a = ap.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    out = run()
    print(f"{'suite':15} {'n':>5} {'rate':>7} {'bar':>6}  result")
    for x in out["suites"]:
        rate = "n/a" if x["rate"] is None else f"{x['rate']:.1%}"
        print(f"{x['suite']:15} {x['n']:>5} {rate:>7} {x['bar']:>6.0%}  {'PASS' if x['ok'] else 'FAIL'}")
        for m in x["misses"][:3]:
            print(f"    - {m}")
    print("evals:", "PASS" if out["ok"] else "FAIL")
    if a.write:
        d = config.ROOT / "data/evals"
        d.mkdir(parents=True, exist_ok=True)
        (d / "latest.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
        with (d / "history.jsonl").open("a", encoding="utf-8") as fh:
            fh.write(json.dumps({"at": out["at"], "ok": out["ok"],
                                 "rates": {x["suite"]: x["rate"] for x in out["suites"]}}) + "\n")
    return 0 if out["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
