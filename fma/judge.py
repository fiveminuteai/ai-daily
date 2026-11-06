"""A fact-checker made of code (6 Nov 2026), so a small local model never has to be the judge. It is cautious by
design: it answers "supported" only with hard evidence, "unsupported" only when it is sure, and "unsure" otherwise;
the unsure claims (a few a day) go to a model or a person.

For one claim and the text of the sources it cites:
1. the evidence is the best-matching source sentence (fma/review.py);
2. every number in the claim must match the evidence, with its unit and per cent;
3. a limit in the evidence ("at least", "up to"...) must not be dropped (verify.ceiling_dropped);
4. a "not" / "can't" must not appear or vanish between evidence and claim;
5. enough of the claim's words must be in the evidence.

Measured by `python -m fma.judge eval <date>`: the published claims of that day (all checked by hand) must come out
supported or unsure, never unsupported; deliberately broken copies of them (a changed number, a dropped limit, a
flipped negative) must never come out supported."""
from __future__ import annotations

import json
import random
import re
import sys

from .review import best_evidence, toks
from .verify import ceiling_dropped, cites, norm, number_ok, numbers_in, plain

NEG = re.compile(r"\b(not|no|never|can't|cannot|won't|isn't|aren't|doesn't|didn't|wasn't|without)\b|n't\b", re.I)
SAYS = set("says said say saying according reports reported reporting notes noted told announced also its their "
           "the company firm".split())
PLAN = re.compile(r"\b(will|plans? to|planning to|expects? to|aims? to|intends? to|to acquire|would|could|may|might)\b", re.I)
DONE = re.compile(r"\b(has|have|had)\s+\w+(ed|en)?\b|\b(acquired|bought|launched|released|completed|closed)\b", re.I)
NUMWORD = "one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|fifteen|twenty|thirty|fifty|hundred"
LIMIT = re.compile(r"\b(at least|up to|more than|as many as|nearly|about|around|almost|over|fewer than|less than)\s+"
                   r"(\$?\d[\d,.]*|" + NUMWORD + r")\b", re.I)


def _stem(w: str) -> str:
    w = w.replace("centre", "center").replace("colour", "color").replace("ise", "ize")
    for suf in ("ings", "ing", "ies", "ed", "es", "s"):
        if w.endswith(suf) and len(w) - len(suf) >= 3:
            return w[: -len(suf)] + ("y" if suf == "ies" else "")
    return w


def words(s: str) -> set[str]:
    return {_stem(t) for t in toks(norm(s)) if t not in SAYS}


def window(claim: str, source_text: str, k: int = 3) -> str:
    """The k source sentences that best match the claim, joined: a claim often draws on two sentences."""
    sents = [x.strip() for x in re.split(r"(?<=[.!?”\"])\s+|\n+", source_text) if len(x.split()) >= 4]
    cw = words(claim)
    ranked = sorted(sents, key=lambda x: -len(cw & words(x)) / (1 + 0.02 * len(x.split())))
    return " ".join(ranked[:k])


def judge(claim: str, source_text: str) -> tuple[str, str, str]:
    """(verdict, evidence, reason) for one claim against its sources' text."""
    c = plain(claim)
    ev = best_evidence(c, source_text)                 # the one quote layer 2 shows
    win = window(c, source_text)                       # what the checks read
    win_n, src_n, c_n = norm(win), norm(source_text), norm(c)
    for num, pct, mult in numbers_in(c):
        if not number_ok(num, pct, mult, win_n):
            if not number_ok(num, pct, mult, src_n):
                return "unsupported", ev, f"the number {num}{pct or ''} is not in the sources"
            return "unsure", ev, f"the number {num}{pct or ''} is in the sources but not near the claim's words"
    capped = ceiling_dropped(c, ev)                    # limits are read against the closest sentence only
    for m in LIMIT.finditer(win_n):                    # "up to three seconds" must not become "three seconds"
        val = m.group(2).lower()
        for cm in re.finditer(r"(?<![\w$.\-])\$?" + re.escape(val) + r"(?![\w]|\.\d)", c_n.lower()):
            before = c_n.lower()[:cm.start()].rstrip()
            if re.search(r"\bfrom\s+\$?[\w.,]+\s+to$", before):      # a range ("from 3 to 15") states its own limits
                continue
            if not re.search(r"(at least|up to|more than|as many as|nearly|about|around|almost|over|fewer than|less than)$", before):
                capped = capped or f"the source says \"{m.group(0)}\"; the claim drops the limit"
    if capped:
        return "unsupported", ev, capped
    if PLAN.search(win_n) and not PLAN.search(c_n) and DONE.search(c_n):
        return "unsure", ev, "the source states a plan or possibility; the claim may state it as done"
    cw = words(c)
    cover = len(cw & words(win)) / max(1, len(cw))
    if NEG.search(c_n) and not NEG.search(win_n):
        return "unsure", ev, "the claim has a negative ('not', 'can't'...) the evidence lacks"
    soft = re.search(r"\b(less|fewer|lower|reduc\w*|avoid\w*|stop\w*|refus\w*)\b", c_n)   # "less likely to hack" ~ "not hacking"
    if NEG.search(win_n) and not NEG.search(c_n) and not soft:
        for m in NEG.finditer(win_n):                  # a negative right before one of the claim's words
            after = words(" ".join(win_n[m.end():].split()[:3]))
            if after & cw:
                return "unsure", ev, f"the source says '{m.group(0)} {' '.join(win_n[m.end():].split()[:2])}'; the claim has no negative"
    if cover >= 0.55:
        return "supported", ev, f"{cover:.0%} of the claim's words are in the evidence"
    return "unsure", ev, f"{cover:.0%} word overlap: needs a reader"


# ---------------------------------------------------------------- evaluation on a published day

def claims_of(post: dict) -> list[str]:
    """Every factual line the reader sees, with its citations: paragraphs' sentences, card hooks and points, and
    Spark's duo lines."""
    from .verify import split_sentences
    out = []
    for sec in post.get("sections", []):
        for p in sec.get("paragraphs", []):
            out += [s for s in split_sentences(p) if cites(s)]
        c = sec.get("card") or {}
        out += [x for x in [c.get("hook"), *c.get("points", [])] if x and cites(x)]
        out += [ln["text"] for ln in (c.get("duo") or {}).get("lines", []) if ln.get("who") == "spark" and cites(ln["text"])]
    return out


def broken(claim: str, rnd: random.Random) -> str | None:
    """A deliberately wrong copy of a claim: a number changed, a limit dropped, or a negative flipped."""
    c = plain(claim)
    nums = list(re.finditer(r"(?<![\d.])(\d+(?:\.\d+)?)", c))
    if nums:
        m = rnd.choice(nums)
        v = m.group(1)
        new = str(int(float(v)) + 3) if "." not in v else f"{float(v) * 2:g}"
        return c[:m.start()] + new + c[m.end():]
    for a, b in ((" at least ", " "), (" up to ", " "), ("can't", "can"), ("cannot", "can"), ("not ", ""), ("will ", "has ")):
        if a in c:
            return c.replace(a, b, 1)
    return None


def evaluate(date: str) -> dict:
    from .pipeline import load_json
    from . import config
    post = load_json(config.ROOT / "content/posts" / f"{date}.json", None)
    sources = {s["id"]: s for s in load_json(config.ROOT / "data/sources" / f"{date}.json", [])}
    rnd = random.Random(7)
    res = {"true": {"supported": 0, "unsure": 0, "unsupported": 0}, "broken": {"supported": 0, "unsure": 0, "unsupported": 0}}
    slips = []
    for claim in claims_of(post):
        text = " ".join(f"{sources[i].get('title', '')}. {sources[i].get('text', '')}" for i in cites(claim) if i in sources)
        v, ev, why = judge(claim, text)
        res["true"][v] += 1
        if v == "unsupported":
            slips.append({"kind": "true claim rejected", "claim": plain(claim), "why": why, "evidence": ev})
        b = broken(claim, rnd)
        if b:
            vb, evb, whyb = judge(b, text)
            res["broken"][vb] += 1
            if vb == "supported":
                slips.append({"kind": "broken claim passed", "claim": b, "why": whyb, "evidence": evb})
    return {"date": date, **res, "slips": slips}


def main() -> None:
    if sys.argv[1:2] == ["eval"]:
        out = evaluate(sys.argv[2])
        print(json.dumps({k: v for k, v in out.items() if k != "slips"}, indent=1))
        for s in out["slips"]:
            print(f"- {s['kind']}: {s['claim'][:110]}\n    {s['why']}\n    evidence: {s['evidence'][:120]}")


if __name__ == "__main__":
    main()
