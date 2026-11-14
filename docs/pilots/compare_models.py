"""7B vs 35B on Five Minute AI's real duo work (14 Nov 2026, requested by Pavan via the aicli session).
Local against local only. Same stories, same prompts, same checks as fma/shadow.py; N samples per story per model.

    python docs/pilots/compare_models.py run 7b|35b OUT_DIR       (resumable: skips samples already on disk)
    python docs/pilots/compare_models.py table OUT_DIR

The 7B runs the way production's local path does (Ollama, with the overnight-tuned prompts). The 35B runs through the
generic chat path (llama.cpp, OpenAI-style, thinking off) with the built-in prompts: the tuned prompts are 7B-specific
and a migration would start from the built-in ones.
"""
import json
import os
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
os.environ.setdefault("LLAMA_LOCAL_KEY", "none")
for k in ("GROQ_API_KEY", "GEMINI_API_KEY", "OPENROUTER_API_KEY"):
    os.environ.pop(k, None)                      # local against local: no cloud keys in this process

from fma import config                            # noqa: E402
from fma.verify import cites, plain               # noqa: E402

DATES = ["2026-11-11", "2026-11-12"]
SAMPLES = 3


def chain_for(which: str):
    from fma.llm import Chain, Provider
    if which == "7b":
        return Chain([Provider(name="ollama", base_url="http://localhost:11434", model="qwen2.5:7b", key_env=None,
                               local=True, timeout=1800)])
    return Chain([Provider(name="llama", base_url="http://127.0.0.1:8080/v1/", model="qwen3.6-35b-a3b",
                           key_env="LLAMA_LOCAL_KEY", timeout=900,
                           extra={"chat_template_kwargs": {"enable_thinking": False}, "max_tokens": 1500})])


def stories():
    out = []
    for d in DATES:
        post = json.loads((config.ROOT / "content/posts" / f"{d}.json").read_text(encoding="utf-8"))
        src = {s["id"]: s for s in json.loads((config.ROOT / "data/sources" / f"{d}.json").read_text(encoding="utf-8"))}
        for n, sec in enumerate(post["sections"]):
            if (sec.get("card") or {}).get("duo"):
                out.append((d, n, sec, src))
    return out


def one(chain, sec, src):
    from fma.bank import joke_pairs
    from fma.duo_desk import (JOKE_PAIRS, assemble, ceiling_problems, facts_step, jokes_step, pick_guest, problems)
    from fma.judge import judge
    from fma.manual import duo_seconds
    from fma.shadow import copied
    card = sec["card"]
    guest = pick_guest(sec)
    t0 = time.monotonic()
    row = {"story": sec["title"], "guest": guest}
    try:
        lines = facts_step(chain, sec)
        jokes = jokes_step(chain, guest, lines) if lines else None
    except Exception as exc:  # noqa: BLE001 - a crash is a failed sample, with its reason
        lines, jokes, row["error"] = None, None, f"{type(exc).__name__}: {str(exc)[:160]}"
    if not (lines and jokes):
        row.update(passed=False, confirmed=False, why=row.get("error") or "did not finish the script within the retries")
    else:
        duo = assemble(guest, lines, jokes)
        rules = problems(duo) + ceiling_problems(duo["lines"], " ".join(sec.get("paragraphs", [])))
        facts = []
        for ln in duo["lines"]:
            if ln["who"] == "spark" and ln.get("kind") != "comeback":
                text = " ".join(f"{src[i].get('title', '')}. {src[i].get('text', '')}" for i in cites(ln["text"]) if i in src)
                v, _ev, why = judge(ln["text"], text) if text else ("unsupported", "", "cites no saved source")
                facts.append({"line": plain(ln["text"]), "verdict": v, "why": why})
        examples = [j for _, j in JOKE_PAIRS[guest] + joke_pairs(guest, 50)]
        rules += [f"recycled punchline: {ln['text']}" for ln in duo["lines"]
                  if ln["who"] == "guest" and copied(ln["text"], examples)]
        secs = duo_seconds({**card, "duo": duo})
        row.update(script=duo, rules=rules, facts=facts, seconds=round(secs, 1),
                   passed=not rules and all(f["verdict"] != "unsupported" for f in facts) and secs <= 44,
                   confirmed=all(f["verdict"] == "supported" for f in facts))
    row["task_seconds"] = round(time.monotonic() - t0, 1)
    return row


def run(which: str, out: Path):
    out.mkdir(parents=True, exist_ok=True)
    chain = chain_for(which)
    for d, n, sec, src in stories():
        for k in range(SAMPLES):
            f = out / f"{which}-{d}-{n}-{k}.json"
            if f.exists():
                continue
            row = one(chain, sec, src)
            row.update(model=which, date=d, idx=n, sample=k)
            f.write_text(json.dumps(row, ensure_ascii=False, indent=1), encoding="utf-8")
            print(which, d, n, k, "PASS" if row["passed"] else "FAIL", "strict" if row.get("confirmed") and row["passed"] else "",
                  row["task_seconds"], "s", flush=True)


def table(out: Path):
    rows = [json.loads(f.read_text(encoding="utf-8")) for f in sorted(out.glob("*.json"))]
    for which in ("7b", "35b"):
        r = [x for x in rows if x["model"] == which]
        if not r:
            continue
        reasons = {}
        for x in r:
            for p in x.get("rules", []) + ([x["why"]] if x.get("why") else []) + \
                    [f"fact {f['verdict']}" for f in x.get("facts", []) if f["verdict"] != "supported"]:
                key = p.split(":")[0][:60] if p.startswith(("line ", "recycled")) is False else p[:60]
                reasons[key] = reasons.get(key, 0) + 1
        top = sorted(reasons.items(), key=lambda kv: -kv[1])[:4]
        print(f"{which}: {len(r)} samples | pass {sum(x['passed'] for x in r)} | passed and every fact confirmed "
              f"{sum(x['passed'] and x.get('confirmed', False) for x in r)} | median {statistics.median(x['task_seconds'] for x in r):.0f} s "
              f"| unfinished {sum(1 for x in r if 'script' not in x)} | top failures {top}")


if __name__ == "__main__":
    if sys.argv[1] == "run":
        run(sys.argv[2], Path(sys.argv[3]))
    else:
        table(Path(sys.argv[2]))
