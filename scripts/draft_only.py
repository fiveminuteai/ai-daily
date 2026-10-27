"""Diagnostics: build today's lineup, ask the model for a draft, run layer-1 verification, save everything to
logs/draft-<date>.json. Publishes nothing.   python scripts/draft_only.py [provider]"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fma import config  # noqa: E402
from fma.extract import extract_item  # noqa: E402
from fma.feeds import Http, fetch_all  # noqa: E402
from fma.llm import Chain, providers_from_config  # noqa: E402
from fma.pipeline import load_json, today_in  # noqa: E402
from fma.rank import pick_lineup, rank  # noqa: E402
from fma.verify import verify_draft  # noqa: E402
from fma.write import build_prompt, normalise_draft, SYSTEM  # noqa: E402

site, srcs = config.site_config(), config.sources_config()
now, http = datetime.now(timezone.utc), Http()
date = today_in(site["timezone"], now)
items, _ = fetch_all(srcs, http, now=now)
ranked = rank(items, srcs, site["pipeline"], load_json(config.DATA_DIR / "history.json", []), now, date)
lineup = pick_lineup(ranked, n=5)
for st in lineup:
    for it in ([st.lead] + [i for i in st.items if i is not st.lead])[:3]:
        it.text = extract_item(it, http)
sources, prompt = build_prompt(lineup, datetime.fromisoformat(date).strftime("%A %d %B %Y"))
chain = Chain(providers_from_config(site, only=sys.argv[1] if len(sys.argv) > 1 else None))
t0 = datetime.now()
raw_obj = chain.ask_json(SYSTEM, prompt)
draft = normalise_draft(raw_obj)
post, report = verify_draft(draft, sources)
out = Path("logs") / f"draft-{date}.json"
out.parent.mkdir(exist_ok=True)
out.write_text(json.dumps({"seconds": (datetime.now() - t0).seconds, "prompt_chars": len(prompt), "raw": chain.last_raw,
                           "draft": draft, "verified": post, "report": report, "sources": sources},
                          ensure_ascii=False, indent=2, default=str), encoding="utf-8")
print(out, "words in draft sections:", sum(len(" ".join(s["paragraphs"]).split()) for s in draft["sections"]),
      "dropped:", report["dropped"], "ok:", report["ok"])
