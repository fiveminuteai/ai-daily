"""Layer 2 without a cloud model (6 Nov 2026). A small local model is too weak to judge claims (it dropped 33 true
sentences on 6 Nov, e.g. "the evidence does not mention 30%" when it did), so the evidence is found by code and the
judgement comes from a reviewer: Claude in a manual-day session (fma/manual.py), later perhaps a local model.

ReviewChain answers llm_check's own prompts, so every safeguard of layer 2 still applies: the evidence it gives is
the best-matching source sentence, and llm_check confirms that quote is word for word in the source. The verdicts
come from a reject list the reviewer writes after reading every claim next to its evidence (review.txt)."""
from __future__ import annotations

import re
from pathlib import Path

TOK = re.compile(r"[a-z0-9$%.]+")
STOP = set("the a an of to and in on for with is are was were it its that this by as at from be has have or".split())


def toks(s: str) -> set[str]:
    return {t.strip(".") for t in TOK.findall(s.lower()) if t.strip(".") not in STOP}


def best_evidence(claim: str, source_text: str) -> str:
    """The source sentence that shares the most words with the claim (lightly favouring short sentences), cut to the
    40 words llm_check allows."""
    sents = [x.strip() for x in re.split(r"(?<=[.!?”\"])\s+|\n+", source_text) if len(x.split()) >= 4]
    ct = toks(claim)
    best = max(sents, key=lambda x: len(ct & toks(x)) / (1 + 0.02 * len(x.split())), default="")
    return " ".join(best.split()[:40])


class ReviewChain:
    """A stand-in for the model chain in llm_check: evidence by code, verdicts from `reject` (claim start -> reason).
    Every claim and its evidence is written to `log` for the reviewer to read."""

    def __init__(self, log: Path, reject: dict[str, str] | None = None):
        self.reject = reject or {}
        self.log = log
        self.used = "review"
        log.write_text("", encoding="utf-8")

    def __bool__(self) -> bool:
        return True

    def ask_json(self, system: str, prompt: str, temperature: float = 0.0, careful: bool = False) -> dict:
        head, src = prompt.split("\n\nSOURCES\n", 1)
        claims = re.findall(r"^(C\d+): (.*)$", head.split("CLAIMS\n", 1)[1], re.M)
        out = []
        with self.log.open("a", encoding="utf-8") as f:
            for cid, text in claims:
                body = re.sub(r"^\[\w+\] ", "", text)
                ev = best_evidence(body, src)
                why = next((r for k, r in self.reject.items() if body.startswith(k)), None)
                out.append({"id": cid, "evidence": ev, "supported": why is None, "reason": why or "supported"})
                f.write(f"{cid} {'REJECT: ' + why if why else 'ok'}\n  CLAIM: {text}\n  EVID : {ev}\n\n")
        return {"checks": out}
