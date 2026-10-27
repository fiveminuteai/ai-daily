"""Turn the day's stories into a structured draft with the model, citing a source on every sentence."""
from __future__ import annotations

import json

from .models import Story

HYPE_WORDS = ["revolutionary", "revolutionize", "revolutionizes", "game-changer", "game-changing", "groundbreaking",
              "unprecedented", "mind-blowing", "jaw-dropping", "stunning", "insane", "delve", "delves", "unleash",
              "unleashes", "supercharge", "supercharges", "skyrocket", "explosive", "seismic", "paradigm shift",
              "cutting-edge", "next-level", "breathtaking", "earth-shattering", "landmark", "tapestry", "embark",
              "in today's fast-paced", "buckle up", "the future is here", "it's not just", "a testament to"]

SYSTEM = """You write "Five Minute AI", a daily briefing on AI for smart colleagues who are not AI specialists.
Accuracy is the whole brand. You only state what the numbered sources say, in your own words.
You reply with one JSON object and nothing else."""

RULES = """Rules, all mandatory:
1. Every sentence ends with one or more citations like [S2] or [S1][S4], pointing to the sources that support it.
2. Use only facts found in the source text below. Copy every number, date, product name, model name, company
   name and person's name exactly as the source writes it. If you are not sure, leave it out.
3. Summarise in your own words. At most ONE direct quotation in the whole post, under 15 words, copied exactly,
   and put it in the "quote" field, not in the body.
4. Plain, calm, human voice. Short sentences (aim for under 22 words). Explain any jargon in a few words.
   No hype, no clickbait, no exclamation marks, no rhetorical questions. Never use these words: {hype}.
5. Facts go in the sections. Opinions or predictions go only in "why_it_matters" items marked "speculative": true.
6. Length: each section body 170 to 230 words (2 or 3 paragraphs). "what_happened" is exactly 3 bullets,
   each under 30 words. "why_it_matters" is 2 or 3 items of 30 to 60 words. The whole post must land between
   950 and 1100 words. Count carefully: too short is a failure.
7. Headline: specific and plain, under 80 characters, no colon-bait, no question.
8. "chart": include only if one source gives two or more directly comparable numbers (benchmark scores, prices,
   sizes). Each bar's value must be a number printed in that source. Otherwise null.
9. "diagram": optional. Up to 5 short steps (under 6 words each) that show how something in one story works,
   taken from that story's source. Otherwise null."""

SCHEMA = """{
  "headline": "string",
  "dek": "one sentence summary of the day, with citations",
  "tags": ["2 to 5 lowercase topic tags, e.g. openai, open-source, regulation"],
  "what_happened": ["bullet with citation [S1]", "...", "..."],
  "sections": [
    {"story": 1, "title": "short plain section title", "category": "models|research|products|tools|policy|impact",
     "paragraphs": ["paragraph text, every sentence cited [S1]", "..."]}
  ],
  "why_it_matters": [{"text": "sentence(s) with citations", "speculative": false}],
  "quote": {"text": "exact words", "speaker": "who said it, as named in the source", "source": "S3"} or null,
  "chart": {"title": "string", "unit": "e.g. % or $ per million tokens", "source": "S2",
            "bars": [{"label": "string", "value": 0.0}]} or null,
  "diagram": {"title": "string", "source": "S5", "steps": ["...", "..."]} or null
}"""


def number_sources(stories: list[Story], lead_chars: int = 2600, other_chars: int = 1100, per_story: int = 3):
    """Assign S1..Sn ids. Returns (sources list, prompt block)."""
    sources, blocks, sid = [], [], 0
    for n, st in enumerate(stories, 1):
        ordered = [st.lead] + [i for i in st.items if i is not st.lead]
        seen_urls = set()
        lines = [f"=== STORY {n} (suggested section: {st.category}) ==="]
        for it in ordered:
            if it.url in seen_urls or len([s for s in sources if s["story"] == n]) >= per_story:
                continue
            seen_urls.add(it.url)
            body = (it.text or it.summary or "").strip()
            if not body:
                continue
            sid += 1
            limit = lead_chars if it is st.lead else other_chars
            src = {"id": f"S{sid}", "story": n, "title": it.title, "url": it.url, "publisher": it.source_name,
                   "published": it.published.isoformat() if it.published else None, "text": body}
            sources.append(src)
            date = it.published.strftime("%d %B %Y") if it.published else "unknown date"
            lines.append(f"[{src['id']}] {it.source_name} — \"{it.title}\" ({date})\n{body[:limit]}")
        blocks.append("\n\n".join(lines))
    return sources, "\n\n".join(blocks)


def build_prompt(stories: list[Story], date_label: str, feedback: str = "") -> tuple[list[dict], str]:
    sources, block = number_sources(stories)
    prompt = (f"Today is {date_label}. Write today's post from the {len(stories)} stories below, one section per story, "
              f"most important first.\n\n{RULES.format(hype=', '.join(HYPE_WORDS))}\n\n"
              f"Reply with JSON in exactly this shape:\n{SCHEMA}\n\n")
    if feedback:
        prompt += f"Your previous attempt was rejected for these reasons; fix them:\n{feedback}\n\n"
    prompt += f"SOURCES\n\n{block}"
    return sources, prompt


def draft_post(chain, stories: list[Story], date_label: str, feedback: str = "") -> tuple[dict, list[dict]]:
    sources, prompt = build_prompt(stories, date_label, feedback)
    draft = chain.ask_json(SYSTEM, prompt, temperature=0.3)
    return normalise_draft(draft), sources


def normalise_draft(d: dict) -> dict:
    """Coerce the model's reply into the expected shape so later steps never trip on a missing key."""
    def as_list(x):
        return x if isinstance(x, list) else ([] if x in (None, "") else [x])

    out = {
        "headline": str(d.get("headline") or "").strip(),
        "dek": str(d.get("dek") or "").strip(),
        "tags": [str(t).strip().lower().replace(" ", "-") for t in as_list(d.get("tags")) if str(t).strip()][:5],
        "what_happened": [str(b).strip() for b in as_list(d.get("what_happened")) if str(b).strip()],
        "sections": [],
        "why_it_matters": [],
        "quote": d.get("quote") if isinstance(d.get("quote"), dict) and d["quote"].get("text") else None,
        "chart": d.get("chart") if isinstance(d.get("chart"), dict) and d["chart"].get("bars") else None,
        "diagram": d.get("diagram") if isinstance(d.get("diagram"), dict) and d["diagram"].get("steps") else None,
    }
    for s in as_list(d.get("sections")):
        if not isinstance(s, dict):
            continue
        paras = [str(p).strip() for p in as_list(s.get("paragraphs") or s.get("body")) if str(p).strip()]
        out["sections"].append({"story": s.get("story"), "title": str(s.get("title") or "").strip(),
                                "category": str(s.get("category") or "products").strip().lower(), "paragraphs": paras})
    for w in as_list(d.get("why_it_matters")):
        if isinstance(w, dict):
            out["why_it_matters"].append({"text": str(w.get("text") or "").strip(), "speculative": bool(w.get("speculative"))})
        elif str(w).strip():
            out["why_it_matters"].append({"text": str(w).strip(), "speculative": False})
    return out


def dumps(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=2)
