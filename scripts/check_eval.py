"""Re-run the model fact-check (layer 2) on a published post against freshly fetched sources, and report what it
flags. Used to measure the checker on posts with known errors. Publishes nothing.
    python scripts/check_eval.py content/posts/2026-10-28.json [provider]"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from fma import config  # noqa: E402
from fma.extract import extract_item  # noqa: E402
from fma.feeds import Http  # noqa: E402
from fma.llm import Chain, providers_from_config  # noqa: E402
from fma.models import Item  # noqa: E402
from fma.verify import cites, llm_check, plain  # noqa: E402

post = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
http = Http()
story_of = {}
for n, s in enumerate(post["sections"], 1):
    for p in s["paragraphs"]:
        for i in cites(p):
            story_of.setdefault(i, n)
sources = []
for s in post["sources"]:
    text = extract_item(Item("x", s["publisher"], s["title"], s["url"], None), http)
    sources.append({**s, "story": story_of.get(s["id"], 0), "text": text})
verified = {k: post[k] for k in ("dek", "what_happened", "sections", "why_it_matters")}
chain = Chain(providers_from_config(config.site_config(), only=sys.argv[2] if len(sys.argv) > 2 else None))
report = {"entries": [], "dropped": 0}
_, report = llm_check(chain, verified, sources, report)
for e in report["entries"]:
    print("FLAG |", e["text"][:110], "|", e["problems"][0][:330])
print("flagged:", report["layer2_flagged"])
