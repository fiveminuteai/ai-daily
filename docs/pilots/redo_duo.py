"""Write a duo for one story of a published post, through the same checks as the daily run (19 Nov 2026, Pavan:
"update the 4th reel": the 16:00 Gemini 4 Neon Reel went out Spark alone).

    python docs/pilots/redo_duo.py <repo with the post> <date> <section index> [tries] [cloud] [question]

Spark's lines come from the facts step and pass the code fact-check first (as reel_desk does), the whole script
passes the final check, then the model check (layer 2) reads Spark's lines against the sources. Only a duo that
survives all of it is written into content/posts/<date>.json. The local model writes and checks (35B first).
"""
import json
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from fma.duo_desk import write  # noqa: E402
from fma.llm import Chain  # noqa: E402
from fma.verify import Verifier, cites, llm_check  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


def main() -> int:
    repo, date, n = Path(sys.argv[1]), sys.argv[2], int(sys.argv[3])
    tries = int(sys.argv[4]) if len(sys.argv) > 4 else 3
    post_path = repo / "content" / "posts" / f"{date}.json"
    post = json.loads(post_path.read_text(encoding="utf-8"))
    sources = json.loads((repo / "data" / "sources" / f"{date}.json").read_text(encoding="utf-8"))
    sec = post["sections"][n]
    card = sec["card"]
    if card.get("duo"):
        print("this card already has a duo; nothing to do")
        return 0
    if len(sys.argv) > 6 and not card.get("ask"):
        # the writer's own question, from the day's report, kept only if it passes the rebuilt-card rule
        from fma.reel_desk import carried_ask
        ask = carried_ask({"ask": sys.argv[6]}, [card.get("hook") or "", *(card.get("points") or [])])
        if not ask:
            print("the question fails the rebuilt-card rule:", sys.argv[6])
            return 1
        card["ask"] = ask
    if len(sys.argv) > 5 and sys.argv[5] == "cloud":
        # 19 Nov 2026: the 35B's one slot was busy with other jobs for 2 hours; the daily run's own cloud writers
        # (Groq, then Gemini) are used instead, after the day's post, with FMA_ALLOW_PROD_KEYS=1 set on purpose
        from fma.config import site_config
        from fma.llm import providers_from_config
        chain = Chain([p for p in providers_from_config(site_config()) if not p.local])
    else:
        from fma.llm import local_providers      # the 35B switch (831224a); not on main before it
        chain = Chain(local_providers())
    print("writer:", [p.model for p in chain.providers])
    ids = list(dict.fromkeys(i for p in sec.get("paragraphs", []) for i in cites(p)))
    for t in range(1, tries + 1):
        checker = Verifier(sources)
        duo = write(chain, sec, card, check=lambda s: checker.sentence(s, "duo pre-check", ids))
        if not duo:
            print(f"try {t}: no duo")
            continue
        v = Verifier(sources)
        kept = v.duo(duo, ids, n)
        if not kept:
            print(f"try {t}: the code fact-check rejected the duo:", [e for e in v.log if e["status"] == "dropped"])
            continue
        (ROOT.parent / f"fma-redo-duo-try{t}.json").write_text(json.dumps(kept, ensure_ascii=False, indent=2),
                                                               encoding="utf-8")
        report = {"entries": list(v.log), "checked": len(v.log), "ok": 0, "repaired": 0, "dropped": 0}
        mini = {"headline": "", "dek": "", "what_happened": [], "why_it_matters": [], "quote": None,
                "sections": [{**sec, "paragraphs": [], "card": {**card, "duo": kept}}]}
        mini, report = llm_check(chain, mini, sources, report, min_words=0)   # a one-card mini-post has no story
        s = (mini.get("sections") or [{}])[0]
        final = (s.get("card") or {}).get("duo") or s.get("kept_duo")
        if card.get("ask") and (s.get("card") or {}).get("ask") != card["ask"]:
            print(f"try {t}: the model check dropped the question; it goes, the duo may stay")
            card["ask"] = None
        # 19 Nov 2026: comparing whole line dicts threw away an 8/10 duo the check had not touched (it rewrites
        # fields such as citations); what matters is that every line is still there and none was dropped
        dropped = [(e.get("where"), e.get("problems")) for e in report["entries"]
                   if e.get("status") == "dropped" and "duo" in str(e.get("where"))]
        if not final or len(final["lines"]) != len(kept["lines"]) or dropped:
            print(f"try {t}: the model check dropped the duo or a line:", dropped,
                  "| lines before/after:", len(kept["lines"]), len((final or {}).get("lines") or []))
            continue
        for a, b in zip(kept["lines"], final["lines"]):
            if a.get("text") != b.get("text"):
                print(f"  check rewrote: {a.get('text')!r} -> {b.get('text')!r}")
        card["duo"] = final
        card["duo_added"] = f"{date}: written after publishing (docs/pilots/redo_duo.py), both checks passed"
        post_path.write_text(json.dumps(post, ensure_ascii=False, indent=2), encoding="utf-8")
        print("duo written:")
        for ln in final["lines"]:
            print(f"  {ln['who']}: {ln['text']}")
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
