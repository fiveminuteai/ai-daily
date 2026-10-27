"""Trial run: the full daily pipeline in a scratch folder, so nothing touches content/ or data/.
Shows which provider wrote each part and whether the post passed the gate. Keys come from the environment only.

    python scripts/trial_run.py <name> <provider> [<provider> ...]      e.g.  trial_run.py gemini-only gemini
"""
import json
import logging
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from fma.feeds import Http  # noqa: E402
from fma.llm import Chain, providers_from_config  # noqa: E402
from fma.pipeline import _yaml, run_day, today_in  # noqa: E402
from fma.site import build  # noqa: E402

name, wanted = sys.argv[1], sys.argv[2:]
trial = ROOT / "logs" / "trials" / name
shutil.rmtree(trial, ignore_errors=True)
for d in ("config", "content/posts", "content/reports", "data"):
    (trial / d).mkdir(parents=True, exist_ok=True)
shutil.copy(ROOT / "config/site.yaml", trial / "config/site.yaml")
shutil.copy(ROOT / "config/sources.yaml", trial / "config/sources.yaml")
(trial / "data/history.json").write_text("[]", encoding="utf-8")

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
site = _yaml(trial / "config/site.yaml")
providers = [p for w in wanted for p in providers_from_config(site, only=w)]
chain = Chain(providers)
print("providers available, in order:", [p.name for p in chain.providers])

calls = []
orig = chain.ask_json


def tracked(*a, **kw):
    out = orig(*a, **kw)
    calls.append(chain.used)
    return out


chain.ask_json = tracked
date = today_in(site["timezone"])
res = run_day(date, Http(), chain, root=trial, build_fn=lambda **kw: build(**kw))
print("result:", res.status, res.reason or res.slug)
print("model calls by provider:", {c: calls.count(c) for c in dict.fromkeys(calls)})
if res.post:
    print("words:", res.post["word_count"], "| sections:", len(res.post["sections"]),
          "| verification:", json.dumps(res.post["verification"]))
    print("headline:", res.post["headline"])
