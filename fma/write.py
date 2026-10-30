"""Turn the day's stories into a structured draft with the model, citing a source on every sentence."""
from __future__ import annotations

import json
import re

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
7. Headline: specific and plain, under 80 characters, sentence case (only names capitalised), no colon-bait,
   no question. Section titles are sentence case too.
   The publisher of a source is not always the maker of the thing: say who made or announced it as the source says.
   The date in each source header is when that page was published, not when the event happened: only state a date
   if the article text itself gives it. Background and context must also come from the sources.
8. "chart": include only if one source gives two or more directly comparable numbers (benchmark scores, prices,
   sizes). Each bar's value must be a number printed in that source. Otherwise null.
9. "diagram": optional. Up to 5 short steps (under 6 words each) that show how something in one story works,
   taken from that story's source. Otherwise null.
10. Architecture stories (how a model is built: attention changes, mixture-of-experts, state-space or hybrid layers,
   long context, reasoning or test-time compute, multimodal design, quantisation, distillation, training recipes):
   use category "architecture". Explain the idea in plain English first, then what is actually new compared with a
   standard transformer. Attribute performance claims to whoever makes them ("the model card says...") and say when
   nobody has checked them independently. If the source describes the design, set "diagram" with
   "kind": "compare", "steps" = 3 to 5 blocks of the new design using the source's own terms, and "baseline" = the
   matching blocks of a standard transformer chosen ONLY from this list: {baseline}."""

SCHEMA = """{
  "headline": "string",
  "dek": "one sentence summary of the day, with citations",
  "tags": ["2 to 5 lowercase topic tags, e.g. openai, open-source, regulation"],
  "what_happened": ["bullet with citation [S1]", "...", "..."],
  "sections": [
    {"story": 1, "title": "short plain section title", "category": "models|architecture|research|products|tools|policy|impact",
     "paragraphs": ["paragraph text, every sentence cited [S1]", "..."]}
  ],
  "why_it_matters": [{"text": "sentence(s) with citations", "speculative": false}],
  "quote": {"text": "exact words", "speaker": "who said it, as named in the source", "source": "S3"} or null,
  "chart": {"title": "string", "unit": "e.g. % or $ per million tokens", "source": "S2",
            "bars": [{"label": "string", "value": 0.0}]} or null,
  "diagram": {"title": "string", "source": "S5", "kind": "flow|compare", "steps": ["...", "..."],
              "baseline": ["only for compare"]} or null
}"""

# The only blocks the "standard transformer" side of a comparison diagram may use. This side isn't checked against
# a source (it's general background), so it's limited to textbook names.
BASELINE_BLOCKS = ["Token embeddings", "Self-attention over all tokens", "Dense feed-forward layer",
                   "Every parameter used per token", "Fixed context window", "Text-only input", "Full-precision weights",
                   "One answer per pass", "Output layer"]


def number_sources(stories: list[Story], lead_chars: int = 2600, other_chars: int = 1100, per_story: int = 3,
                   per_block: bool = False):
    """Assign S1..Sn ids. Returns (sources list, prompt block) or, with per_block, (sources, [block per story])."""
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
    return (sources, blocks) if per_block else (sources, "\n\n".join(blocks))


def build_prompt(stories: list[Story], date_label: str, feedback: str = "") -> tuple[list[dict], str]:
    sources, block = number_sources(stories)
    prompt = (f"Today is {date_label}. Write today's post from the {len(stories)} stories below, one section per story, "
              f"most important first.\n\n{RULES.format(hype=', '.join(HYPE_WORDS), baseline='; '.join(BASELINE_BLOCKS))}\n\n"
              f"Reply with JSON in exactly this shape:\n{SCHEMA}\n\n")
    if feedback:
        prompt += f"Your previous attempt was rejected for these reasons; fix them:\n{feedback}\n\n"
    prompt += f"SOURCES\n\n{block}"
    return sources, prompt


SECTION_SCHEMA = """{
  "title": "short plain section title, sentence case",
  "category": "models|architecture|research|products|tools|policy|impact",
  "what": "paragraph 1, 60 to 80 words: what happened, who did it, when. Every sentence cited [S1]",
  "details": "paragraph 2, 60 to 80 words: the specifics, numbers and names from the sources. Every sentence cited",
  "context": "paragraph 3, 50 to 70 words: background a non-specialist needs, in plain English. Every sentence cited",
  "bullet": "one sentence under 30 words summing up this story for the 30-second version, cited",
  "quote": {"text": "exact words", "speaker": "who said it, as named in the source", "source": "S3"} or null,
  "chart": {"title": "string", "unit": "e.g. %", "source": "S2", "bars": [{"label": "string", "value": 0.0}]} or null,
  "diagram": {"title": "string", "source": "S5", "kind": "flow|compare", "steps": ["..."], "baseline": ["..."]} or null
}"""

FINAL_SCHEMA = """{
  "headline": "string",
  "dek": "one sentence summing up the day, with citations copied from the sections",
  "tags": ["2 to 5 lowercase topic tags, e.g. openai, open-source, regulation"],
  "why_it_matters": [{"text": "30 to 60 words, with citations", "speculative": false}]
}"""


def section_prompt(block: str, n: int, total: int, date_label: str, feedback: str) -> str:
    rules = RULES.format(hype=", ".join(HYPE_WORDS), baseline="; ".join(BASELINE_BLOCKS))
    p = (f"Today is {date_label}. This is story {n} of {total} in today's post. Write ONE section about it.\n\n"
         f"{rules}\n\nFor this section: three paragraphs, 'what', 'details' and 'context', 180 to 230 words in total. "
         f"Each paragraph has at least three full sentences; a short paragraph is a failure. "
         f"The rules about the headline, 'what_happened' and 'why_it_matters' are handled separately; ignore them.\n\n"
         f"Reply with JSON in exactly this shape:\n{SECTION_SCHEMA}\n\n")
    if feedback:
        p += f"An earlier attempt at today's post was rejected for these reasons; avoid them:\n{feedback}\n\n"
    return p + f"SOURCES\n\n{block}"


def final_prompt(sections: list[dict], date_label: str, feedback: str) -> str:
    body = "\n\n".join(f"SECTION {n} ({s.get('category')}): {s.get('title')}\n" + "\n".join(s.get("paragraphs", []))
                       for n, s in enumerate(sections, 1))
    p = (f"Today is {date_label}. Below are today's sections. Write the headline, a one-sentence dek, 2 to 5 tags "
         f"and 2 or 3 'why it matters' items. Use only facts from the sections and keep their [S#] citations on "
         f"every sentence. Headline: under 80 characters, sentence case, about the most important story, no question, "
         f"no hype. 'Why it matters' explains consequences for ordinary people and companies; mark any prediction "
         f"or opinion as \"speculative\": true. Never use these words: {', '.join(HYPE_WORDS)}.\n\n"
         f"Reply with JSON in exactly this shape:\n{FINAL_SCHEMA}\n\n")
    if feedback:
        p += f"An earlier attempt was rejected for these reasons; avoid them:\n{feedback}\n\n"
    return p + f"SECTIONS\n\n{body}"


def draft_post(chain, stories: list[Story], date_label: str, feedback: str = "", mode: str = "sections"):
    """Write the post. "sections" mode asks for one section per call (better length control and attribution,
    especially for small local models), then one short call for headline, dek and 'why it matters'."""
    if mode == "single":
        sources, prompt = build_prompt(stories, date_label, feedback)
        return normalise_draft(chain.ask_json(SYSTEM, prompt, temperature=0.3)), sources
    sources, blocks = number_sources(stories, per_block=True)
    sections, extras, last_error = [], {"quote": None, "chart": None, "diagram": None}, None
    for n, block in enumerate(blocks, 1):
        try:
            sec = chain.ask_json(SYSTEM, section_prompt(block, n, len(blocks), date_label, feedback), temperature=0.3)
        except Exception as exc:  # noqa: BLE001 - one story failing shouldn't sink the others
            last_error = exc
            continue
        if not isinstance(sec, dict):
            continue
        if not sec.get("paragraphs"):
            sec["paragraphs"] = [sec[k] for k in ("what", "details", "context") if isinstance(sec.get(k), str) and sec[k].strip()]
        sec["story"] = n
        sections.append(sec)
        for k in extras:
            v = sec.get(k)
            if isinstance(v, dict) and extras[k] is None:
                extras[k] = v
            elif k == "diagram" and isinstance(v, dict) and str(sec.get("category")).lower() == "architecture":
                extras[k] = v                        # an architecture diagram wins over a generic one
    if not sections and last_error is not None:
        raise last_error                     # every call failed: report the real reason, not "0 sections"
    norm = normalise_draft({"sections": sections})["sections"]
    final = chain.ask_json(SYSTEM, final_prompt(norm, date_label, feedback), temperature=0.3) if norm else {}
    draft = {**(final if isinstance(final, dict) else {}), "sections": sections,
             "what_happened": [s.get("bullet", "") for s in sections], **extras}   # spares: the first 3 that verify are used
    return normalise_draft(draft), sources


def fix_citations(text: str) -> str:
    """Rewrite citation styles models often use ([S1, S2], (S1), [S1 S2], 【S1】) into [S1][S2]."""
    text = re.sub(r"[【\[(]\s*((?:S\d+\s*[,;/&]?\s*(?:and\s+)?)+)\s*[】\])]",
                  lambda m: "".join(f"[{s}]" for s in re.findall(r"S\d+", m.group(1))), str(text))
    return re.sub(r"\s+(?=\[S\d+\])", "", text)


# Short forms models sometimes write as ordinary words ("Aws"). Only these exact words are touched.
ACRONYMS = {w.lower(): w for w in ("AI", "AGI", "AWS", "API", "APIs", "CEO", "CFO", "CPU", "CPUs", "EU", "FTC", "GPU",
                                   "GPUs", "IBM", "IPO", "LLM", "LLMs", "NHS", "SEC", "TPU", "TPUs", "UK", "UN", "US",
                                   "USA", "UAE", "AMD", "TSMC", "SaaS")}


def tidy_heading(text: str) -> str:
    """Sentence-case safety net for headings: capital first letter, known short forms in capitals.
    Anything else the model wrote (brand names like iPhone or OpenAI, a word like "us") is left alone."""
    text = text.strip()
    first = re.match(r"[A-Za-z]+", text)
    if first and first[0].lower() in ACRONYMS:                       # "aws cuts prices" -> "AWS cuts prices"
        text = ACRONYMS[first[0].lower()] + text[first.end():]
    text = re.sub(r"\b[A-Za-z]+\b",
                  lambda m: ACRONYMS[m[0].lower()] if m[0].lower() in ACRONYMS and m[0] != m[0].lower() else m[0],
                  text)
    if text[:1].islower() and not re.match(r"[a-z]+[A-Z]", text):  # leave iPhone, eBay as written
        text = text[0].upper() + text[1:]
    return text


def normalise_draft(d: dict) -> dict:
    """Coerce the model's reply into the expected shape so later steps never trip on a missing key."""
    def as_list(x):
        if isinstance(x, list):
            return [fix_citations(i) if isinstance(i, str) else i for i in x]
        return [] if x in (None, "") else [fix_citations(x) if isinstance(x, str) else x]
    d = {**d, "dek": fix_citations(d.get("dek") or ""), "headline": str(d.get("headline") or "")}
    if isinstance(d.get("sections"), list):
        d["sections"] = [{**s, "paragraphs": as_list(s.get("paragraphs") or s.get("body"))} if isinstance(s, dict) else s
                         for s in d["sections"]]
    if isinstance(d.get("why_it_matters"), list):
        d["why_it_matters"] = [{**w, "text": fix_citations(w.get("text", ""))} if isinstance(w, dict) else w
                               for w in d["why_it_matters"]]

    out = {
        "headline": tidy_heading(str(d.get("headline") or "")),
        "dek": str(d.get("dek") or "").strip(),
        # same rule as the tag page URLs; a tag that slugs to nothing would overwrite the Topics index page
        "tags": list(dict.fromkeys(t for t in (re.sub(r"[^a-z0-9]+", "-", str(t).lower()).strip("-")
                                               for t in as_list(d.get("tags"))) if t))[:5],
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
        out["sections"].append({"story": s.get("story"), "title": tidy_heading(str(s.get("title") or "")),
                                "category": str(s.get("category") or "products").strip().lower(), "paragraphs": paras})
    for w in as_list(d.get("why_it_matters")):
        if isinstance(w, dict):
            out["why_it_matters"].append({"text": str(w.get("text") or "").strip(), "speculative": bool(w.get("speculative"))})
        elif str(w).strip():
            out["why_it_matters"].append({"text": str(w).strip(), "speculative": False})
    return out


def dumps(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=2)
