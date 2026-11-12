"""Overnight prompt tuning for the local model (6 Nov 2026). Pavan: "train the 7B model and bring it to its best
ability". Its weights are not changed (a 7B needs more than the laptop's 4 GB of VRAM, and our content was written
by models whose terms forbid training other models on it); instead DSPy (stanfordnlp/dspy, MIT) searches for the
instructions and worked examples that make the 7B do best at our two writing steps, scored by our own code checks:

- facts: the story as 4 Spark lines. Score: lines the code fact-checker confirms (fma/judge.py), plus citations,
  length, plain words, limits kept ("at least") and numbers kept with what they count.
- jokes: one guest reaction to one Spark line. Score: the code ranker (fma.duo_desk.rank_reaction): rules kept,
  reacts to its own line, not a copy. Funny is judged by Pavan from the shadow Reels, not by code.

The winners are written to data/tuned/local.json as plain text (instructions + examples). The daily code never runs
DSPy: fma/duo_desk.py reads that file only when the writer is the local model, and the cloud models keep their prompts.
Before saving, three prompts are scored on the same stories the tuner did not practise on: the untuned default,
the one kept from an earlier night, and tonight's candidate. A challenger replaces the holder only when its gain
is at least MARGIN and more than twice the standard error of the paired differences (13 Nov 2026: a gain of 0.0025
on 10 stories was "kept", and the prompt kept on 6 Nov was never re-tested against the default on newer stories).

    python -m fma.tune [--auto light|medium] [--model qwen2.5:7b]     # needs Ollama and `pip install "dspy[optuna]"`"""
from __future__ import annotations

import argparse
import json
import random
import re
from datetime import datetime, timezone

from . import config

OUT = config.ROOT / "data" / "tuned" / "local.json"


def stories() -> list[dict]:
    """Every published section with its citations: the practice material."""
    out = []
    for p in sorted((config.ROOT / "content/posts").glob("*.json")):
        for sec in json.loads(p.read_text(encoding="utf-8")).get("sections", []):
            text = "\n".join(sec.get("paragraphs", []))
            if len(text.split()) >= 80:
                out.append({"title": sec.get("title", ""), "text": text})
    return out


def spark_lines() -> list[str]:
    """Spark-style fact lines to react to: published duo lines and Reel card points."""
    from .bank import _read
    lines = [r["spark"] for r in _read("duo_pairs.jsonl")]
    for c in _read("cards.jsonl"):
        lines += [c["hook"], *c.get("points", [])]
    return [x for x in dict.fromkeys(lines) if x and len(x.split()) >= 6]


# ---------------------------------------------------------------- scores (code only)

def facts_score(lines: list[str], story_text: str) -> float:
    from .duo_desk import HARD_WORDS, binding_problems, ceiling_problems, plain
    from .judge import judge
    lines = [str(x) for x in (lines or []) if str(x).strip()][:4]
    if len(lines) < 3:
        return 0.0
    total = 0.0
    for t in lines:
        ok = 0.0
        ok += 0.25 if re.search(r"\[S\d+\]", t) else 0
        ok += 0.15 if 6 <= len(plain(t).split()) <= 20 else 0
        ok += 0.1 if not {w for w in re.findall(r"[a-z]+", plain(t).lower()) if w in HARD_WORDS} else 0
        verdict = judge(t, story_text)[0]
        ok += {"supported": 0.5, "unsure": 0.15, "unsupported": 0.0}[verdict]
        total += ok
    s = total / len(lines)
    if binding_problems(lines, story_text) or ceiling_problems([{"who": "spark", "text": t} for t in lines], story_text):
        s *= 0.5
    return round(s * (len(lines) / 4), 4)


def jokes_score(reactions: list[str], line: str, guest: str) -> float:
    from .duo_desk import rank_reaction
    best = 0.0
    for r in [str(x) for x in (reactions or [])][:3]:
        sc, why = rank_reaction(r, line, [], [], guest)
        if not why:
            best = max(best, 0.4 + min(sc, 6.0) / 10)       # a valid reaction is worth 0.4; relevance adds up to 0.6
    return round(best, 4)


# ---------------------------------------------------------------- DSPy programs

def _programs():
    import dspy
    from .duo_desk import FACTS_TASK, JOKE_TASK, PERSONA

    class Facts(dspy.Signature):
        story: str = dspy.InputField(desc="the story text, with citations like [S1]")
        lines: list[str] = dspy.OutputField(desc="exactly 4 short plain lines for Spark, each ending with its citation")

    class Joke(dspy.Signature):
        guest: str = dspy.InputField(desc="who is reacting, and what they are like")
        spark_line: str = dspy.InputField(desc="what Spark just said")
        reactions: list[str] = dspy.OutputField(desc="exactly 3 different short reactions")

    Facts.__doc__ = FACTS_TASK.split("EXAMPLE")[0].strip()
    Joke.__doc__ = JOKE_TASK.split("EXAMPLES OF")[0].replace("{k}", "3").replace("{name}", "the guest").replace(
        "{name_up}", "THE GUEST").replace("{persona}", "given below").strip()
    return dspy.Predict(Facts), dspy.Predict(Joke), PERSONA


MARGIN = 0.02            # the smallest gain worth switching prompts for
TRAIN_STORIES, TRAIN_JOKES = 24, 28


def beats(challenger: list[float], holder: list[float]) -> tuple[bool, float, float]:
    """(wins, mean gain, standard error of the paired differences). Both lists are scores on the same held-out
    examples in the same order. A win needs a gain of MARGIN or more that is over twice its standard error, and
    at least 20 examples: fewer can't tell a real gain from luck."""
    n = min(len(challenger), len(holder))
    if n < 2:
        return False, 0.0, 0.0
    d = [challenger[k] - holder[k] for k in range(n)]
    gain = sum(d) / n
    var = sum((x - gain) ** 2 for x in d) / (n - 1)
    se = (var / n) ** 0.5
    return n >= 20 and gain >= MARGIN and gain > 2 * se, round(gain, 4), round(se, 4)


def decide(default: list[float], kept: list[float] | None, new: list[float] | None) -> dict:
    """Which prompt to use from tonight on: "default", "kept" or "new", with the numbers behind it. The earlier
    night's prompt is re-tested first: if the default now clearly beats it, it is dropped. Then tonight's candidate
    must clearly beat whichever of the two holds."""
    mean = lambda xs: round(sum(xs) / max(1, len(xs)), 4)          # noqa: E731
    out = {"n": len(default), "default": mean(default), "kept": mean(kept) if kept else None,
           "new": mean(new) if new else None}
    holder, name = default, "default"
    if kept:
        dropped, gain, se = beats(default, kept)
        out["kept_vs_default"] = {"gain_of_default": gain, "se": se, "kept_dropped": dropped}
        if not dropped:
            holder, name = kept, "kept"
    wins, gain, se = beats(new, holder) if new else (False, 0.0, 0.0)      # no candidate: only the re-test
    out["new_vs_holder"] = {"holder": name, "gain": gain, "se": se, "wins": wins}
    out["use"] = "new" if wins else name
    return out


def with_prompt(program, saved: dict | None):
    """A copy of the program carrying a saved prompt (instructions + worked examples), or None without one."""
    import dspy
    if not saved or not saved.get("instructions"):
        return None
    prog = program.deepcopy()
    prog.signature = prog.signature.with_instructions(saved["instructions"])
    prog.demos = [dspy.Example(**d) for d in saved.get("demos") or []]
    return prog


def tune(auto: str = "light", model: str = "qwen2.5:7b", seed: int = 7, search: bool = True) -> dict:
    """search False (--judge-only): no new candidate is searched for; the kept prompt is only re-tested against
    the default on the held-out examples, and dropped if the default clearly beats it."""
    import dspy
    lm = dspy.LM(f"ollama_chat/{model}", api_base="http://localhost:11434", api_key="", temperature=0.4, max_tokens=900)
    dspy.configure(lm=lm, adapter=dspy.JSONAdapter())   # 6 Nov 2026: the default text format confused the 7B
    facts, joke, persona = _programs()
    rnd = random.Random(seed)

    st = stories()
    rnd.shuffle(st)
    f_train = [dspy.Example(story=s["text"], _text=s["text"]).with_inputs("story") for s in st[:TRAIN_STORIES]]
    f_held = [dspy.Example(story=s["text"], _text=s["text"]).with_inputs("story") for s in st[TRAIN_STORIES:]]   # all the rest
    lines = spark_lines()
    rnd.shuffle(lines)
    guests = ["doubt", "rex"]
    j_all = [dspy.Example(guest=f"{g}: {persona[g]}", spark_line=ln, _g=g).with_inputs("guest", "spark_line")
             for k, ln in enumerate(lines[:TRAIN_JOKES + 60]) for g in [guests[k % 2]]]
    j_train, j_held = j_all[:TRAIN_JOKES], j_all[TRAIN_JOKES:]

    def f_metric(ex, pred, trace=None):
        return facts_score(getattr(pred, "lines", None), ex._text)

    def j_metric(ex, pred, trace=None):
        return jokes_score(getattr(pred, "reactions", None), ex.spark_line, ex._g)

    def held_scores(program, data, metric) -> list[float]:
        scores = []
        for ex in data:
            try:
                scores.append(float(metric(ex, program(**ex.inputs()))))
            except Exception:  # noqa: BLE001 - a failed answer scores 0
                scores.append(0.0)
        return scores

    result = {"date": datetime.now(timezone.utc).isoformat(timespec="seconds"), "model": model, "auto": auto}
    prev = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {}
    keep: dict = {}
    for name, prog, train, held, metric in (("facts", facts, f_train, f_held, f_metric),
                                            ("jokes", joke, j_train, j_held, j_metric)):
        prev_saved = prev.get(name)
        old = with_prompt(prog, prev_saved)
        default_scores = held_scores(prog, held, metric)
        kept_scores = held_scores(old, held, metric) if old else None
        tuned = None
        if search:
            opt = dspy.MIPROv2(metric=metric, auto=auto, num_threads=1, seed=seed, verbose=False)
            tuned = opt.compile(prog, trainset=train, requires_permission_to_run=False)
        verdict = decide(default_scores, kept_scores, held_scores(tuned, held, metric) if tuned else None)
        demos = [{k: v for k, v in d.toDict().items() if not k.startswith("_") and k != "augmented"}
                 for d in tuned.demos] if tuned else []
        result[name] = {"score_before": verdict[verdict["new_vs_holder"]["holder"]], "score_after": verdict["new"],
                        "kept": verdict["use"] == "new", "verdict": verdict,
                        "instructions": tuned.signature.instructions if tuned else "", "demos": demos}
        # what the daily code will read: tonight's prompt, the earlier one, or nothing (the built-in default)
        keep[name] = result[name] if verdict["use"] == "new" else prev_saved if verdict["use"] == "kept" else None
    OUT.parent.mkdir(parents=True, exist_ok=True)
    meta = {k: v for k, v in result.items() if k not in ("facts", "jokes")}
    OUT.write_text(json.dumps({**meta, **{k: v for k, v in keep.items() if v}}, ensure_ascii=False, indent=1),
                   encoding="utf-8")
    hist = config.ROOT / "data" / "tuned" / "history.jsonl"
    with hist.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"date": result["date"], "model": model, "auto": auto,
                            **{k: result[k]["verdict"] for k in ("facts", "jokes")}}) + "\n")
    return result


def main() -> None:
    ap = argparse.ArgumentParser(prog="python -m fma.tune")
    ap.add_argument("--auto", default="light", choices=["light", "medium", "heavy"])
    ap.add_argument("--model", default="qwen2.5:7b")
    ap.add_argument("--judge-only", action="store_true", help="re-test the kept prompts against the default; no search")
    a = ap.parse_args()
    r = tune(a.auto, a.model, search=not a.judge_only)
    for k in ("facts", "jokes"):
        v = r[k]["verdict"]
        print(f"{k}: on {v['n']} held-out examples: default {v['default']}, kept {v['kept']}, new {v['new']} "
              f"-> using {v['use']} ({json.dumps({x: v[x] for x in ('kept_vs_default', 'new_vs_holder') if x in v})})")


if __name__ == "__main__":
    main()
