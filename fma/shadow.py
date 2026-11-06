"""The shadow test (6 Nov 2026): the local model does a published day's Reel work in the background, and is scored
against the same checks a published Reel must pass, so the day it is good enough to rely on is measured, not guessed.

For each of the day's duo stories, the local model writes the duo script with the same small steps as the cloud
models (fma/duo_desk.py: facts, then jokes from the knowledge bank's punchlines, then assembly in code). Scored:
- rules: the duo desk's checks (plain words, the guest states no facts, length budget);
- facts: every Spark line through the code fact-checker (fma/judge.py) against the day's saved sources;
- length: the estimated Reel length (fma/manual.duo_seconds), 44 s at most.
A story "passes" when all three pass. Results: data/shadow/<date>.json, beside the published scripts.

    python -m fma.shadow [date] [--model qwen2.5:7b]       # needs Ollama running on this machine"""
from __future__ import annotations

import argparse
import json
import time

from . import config
from .verify import cites, plain


def copied(joke: str, examples: list[str]) -> str | None:
    """A punchline that is mostly an example's words is recycled, not written: the example it copies, if any."""
    from .judge import words
    jw = words(joke)
    for ex in examples:
        ew = words(ex)
        if jw and len(jw & ew) / len(jw) >= 0.6:
            return ex
    return None


def local_chain(model: str):
    from .llm import Chain, Provider
    return Chain([Provider(name="ollama", base_url="http://localhost:11434", model=model, key_env=None, local=True,
                           timeout=1800)])


def run(date: str, model: str = "qwen2.5:7b") -> dict:
    from .duo_desk import assemble, ceiling_problems, facts_step, jokes_step, pick_guest, problems
    from .judge import judge
    from .manual import duo_seconds

    post = json.loads((config.ROOT / "content/posts" / f"{date}.json").read_text(encoding="utf-8"))
    src = {s["id"]: s for s in json.loads((config.ROOT / "data/sources" / f"{date}.json").read_text(encoding="utf-8"))}
    chain = local_chain(model)
    stories = []
    for sec in post["sections"]:
        card = sec.get("card") or {}
        if not card.get("duo"):
            continue
        t0 = time.monotonic()
        row = {"story": sec["title"], "published": card["duo"], "guest": pick_guest(sec)}
        lines = facts_step(chain, sec)
        jokes = jokes_step(chain, row["guest"], lines) if lines else None
        if not (lines and jokes):
            row.update(passed=False, why="the local model did not finish the script within the retries")
        else:
            duo = assemble(row["guest"], lines, jokes)
            rules = problems(duo) + ceiling_problems(duo["lines"], " ".join(sec.get("paragraphs", [])))
            facts = []
            for ln in duo["lines"]:
                if ln["who"] == "spark":
                    text = " ".join(f"{src[i].get('title', '')}. {src[i].get('text', '')}" for i in cites(ln["text"]) if i in src)
                    verdict, _ev, why = judge(ln["text"], text) if text else ("unsupported", "", "cites no saved source")
                    facts.append({"line": plain(ln["text"]), "verdict": verdict, "why": why})
            from .bank import joke_pairs
            from .duo_desk import JOKE_PAIRS
            examples = [j for _, j in JOKE_PAIRS[row["guest"]] + joke_pairs(row["guest"], 50)]
            rules += [f"recycled punchline: \"{ln['text']}\" copies \"{ex}\"" for ln in duo["lines"]
                      if ln["who"] == "guest" and (ex := copied(ln["text"], examples))]
            secs = duo_seconds({**card, "duo": duo})
            row.update(script=duo, rules=rules, facts=facts, seconds=round(secs, 1),
                       passed=not rules and all(f["verdict"] != "unsupported" for f in facts) and secs <= 44)
        row["minutes"] = round((time.monotonic() - t0) / 60, 1)
        stories.append(row)
    out = {"date": date, "model": model, "stories": stories,
           "score": f"{sum(r['passed'] for r in stories)}/{len(stories)} Reel scripts pass every check"}
    path = config.ROOT / "data/shadow" / f"{date}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    return out


def main() -> None:
    from .manual import _today
    ap = argparse.ArgumentParser(prog="python -m fma.shadow")
    ap.add_argument("date", nargs="?")
    ap.add_argument("--model", default="qwen2.5:7b")
    a = ap.parse_args()
    out = run(a.date or _today(), a.model)
    print(out["score"])
    for r in out["stories"]:
        print(f"\n== {r['story']} ({r['guest']}, {r.get('seconds')} s, {r['minutes']} min) -> {'PASS' if r['passed'] else 'FAIL'}")
        for ln in (r.get("script") or {}).get("lines", []):
            print(f"  {ln['who']:5s} {plain(ln['text'])}")
        for p in r.get("rules", []):
            print(f"  rule: {p}")
        for f in r.get("facts", []):
            if f["verdict"] != "supported":
                print(f"  fact {f['verdict']}: {f['line'][:80]} ({f['why']})")
        if r.get("why"):
            print("  " + r["why"])


if __name__ == "__main__":
    main()
