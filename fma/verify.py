"""The verification pass. Nothing is published that this module could not trace to the fetched source text.

Layer 1 (always, deterministic): every sentence must cite a source; every number and every proper name in
it must appear in the text of the source(s) it cites. Quotes must be verbatim. Chart values must be printed
in the chart's source. Anything that fails is dropped, and the drop is recorded in the report.

Layer 2 (optional): the model re-reads each surviving sentence next to its sources and flags anything
the sources don't actually support. Flagged sentences are dropped too.
"""
from __future__ import annotations

import re
import unicodedata
from datetime import datetime

from .write import HYPE_WORDS

CITE_RE = re.compile(r"\[(S\d+)\]")
ABBREV = ["U.S.", "U.K.", "U.N.", "e.g.", "i.e.", "Dr.", "Mr.", "Ms.", "Mrs.", "Inc.", "Corp.", "Ltd.", "vs.", "No.",
          "St.", "Jr.", "Co.", "approx.", "etc.", "Fig.", "Jan.", "Feb.", "Aug.", "Sept.", "Oct.", "Nov.", "Dec."]
MONTHS = "january february march april may june july august september october november december".split()
DAYS = "monday tuesday wednesday thursday friday saturday sunday".split()
# Capitalised words that are fine without being in the source: generic acronyms and calendar words.
ALWAYS_OK = set(MONTHS + DAYS + """i ai a.i. us u.s. uk u.k. eu un ceo cto cfo api apis gpu gpus cpu cpus llm llms
phd ipo faq pdf html ui ux id ok tv pc pcs ios r&d hr it s&p q1 q2 q3 q4 ml nlp asr""".split())
# Ordinary words that often start a sentence; a capital letter here doesn't make them a name.
COMMON_STARTERS = set("""the a an this that these those it its they their them he she his her we our you your i in on at
for with by from as but and or so yet also still then now today tonight yesterday meanwhile however instead separately
elsewhere both each all some many most few several one two three four five six seven eight nine ten there here what when
where why how which who whose while after before since because if unless although though even only not no more less
such other another under over about according last next first second third earlier later overall together critics
experts analysts users people researchers companies developers engineers officials regulators workers customers
the investors employees governments lawmakers until within without during between among across against despite into
through toward towards per unlike like rather whether either neither nor just much any every none nothing something
someone everyone nobody this that thanks taken put asked based given by beyond behind below above near far long""".split())
MULTIPLIERS = {"trillion": ["trillion", "tn", "t"], "billion": ["billion", "bn", "b"],
               "million": ["million", "mn", "m"], "thousand": ["thousand", "k"]}
NUM_RE = re.compile(r"(?<![\w.])[$€£₹]?(\d+(?:[.,]\d+)*)(\s?%)?(?:\s?(trillion|billion|million|thousand)\b)?", re.I)
QUOTE_RE = re.compile(r"[\"“”]([^\"“”]{3,}?)[\"“”]")
WORD_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9.\-+&'’]*[A-Za-z0-9+]|[A-Za-z0-9]")


# ---------------------------------------------------------------- normalisation

def norm(s: str) -> str:
    s = unicodedata.normalize("NFKC", s or "")
    s = s.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    s = re.sub(r"[‐‑‒–—―]", "-", s)
    s = s.lower()
    s = re.sub(r"(\d),(?=\d{3}\b)", r"\1", s)            # 1,000 -> 1000
    s = re.sub(r"(\d)\s*(?:per ?cent|percent)\b", r"\1%", s)
    s = re.sub(r"(\d)\s+%", r"\1%", s)
    return re.sub(r"\s+", " ", s)


def date_words(iso: str | None) -> str:
    """Spell a source's publication date several ways so 'on October 26' can be checked against metadata."""
    if not iso:
        return ""
    try:
        d = datetime.fromisoformat(iso)
    except ValueError:
        return ""
    m = d.strftime("%B")
    return f" {d.day} {m} {m} {d.day} {d.year} {d.strftime('%A')} {m[:3]}. {d.day} {d.strftime('%Y-%m-%d')} "


def corpus(src: dict) -> str:
    return norm(f"{src.get('title', '')} {src.get('publisher', '')} {src.get('text', '')} {date_words(src.get('published'))}")


# ---------------------------------------------------------------- sentences and citations

def split_sentences(text: str) -> list[str]:
    protected = text
    for a in ABBREV:
        protected = protected.replace(a, a.replace(".", "․"))
    parts = re.split(r"(?<=[.!?])\s+(?=[\[\"“(A-Z0-9])", protected.strip())
    out: list[str] = []
    for p in parts:
        p = p.replace("․", ".").strip()
        lead = re.match(r"^((?:\[S\d+\]\s*)+)(.*)$", p)
        if lead and out:          # citations written after the full stop belong to the previous sentence
            out[-1] = out[-1] + " " + lead.group(1).strip()
            p = lead.group(2).strip()
        if p:
            out.append(p)
    return out


def cites(sentence: str) -> list[str]:
    return list(dict.fromkeys(CITE_RE.findall(sentence)))


def plain(sentence: str) -> str:
    return re.sub(r"\s+([.,;:!?])", r"\1", CITE_RE.sub("", sentence)).strip()


def tidy(sentence_plain: str, ids: list[str]) -> str:
    s = sentence_plain.rstrip()
    end = ""
    if s and s[-1] in ".!?":
        s, end = s[:-1], s[-1]
    end = "." if end in ("", "!") else end
    return s + "".join(f"[{i}]" for i in ids) + end


# ---------------------------------------------------------------- checks

def numbers_in(text: str) -> list[tuple[str, str, str]]:
    out = []
    for m in NUM_RE.finditer(text):
        num = m.group(1).replace(",", "")
        out.append((num, (m.group(2) or "").strip(), (m.group(3) or "").lower()))
    return out


def number_ok(num: str, pct: str, mult: str, text_norm: str) -> bool:
    pat = r"(?<![\d.])" + re.escape(num) + r"(?![\d])"
    if pct:
        pat += r"\s?%"
    for m in re.finditer(pat, text_norm):
        if not mult:
            return True
        tail = text_norm[m.end(): m.end() + 14]
        if any(re.match(r"\s?" + re.escape(w) + r"\b", tail) for w in MULTIPLIERS[mult]):
            return True
    return False


def names_in(sentence_plain: str) -> list[tuple[str, bool]]:
    """Proper-name-like words: capitalised, camel-cased or alphanumeric. Returns (word, is_sentence_start)."""
    out = []
    for idx, m in enumerate(WORD_RE.finditer(sentence_plain)):
        w = m.group(0).rstrip(".'’").removesuffix("'s").removesuffix("’s")
        if not w:
            continue
        has_upper = any(c.isupper() for c in w)
        mixed = any(c.isdigit() for c in w) and any(c.isalpha() for c in w)
        if not (has_upper or mixed) or w.isdigit():
            continue
        if w.lower() in ALWAYS_OK or w.lower().rstrip("s") in ALWAYS_OK:
            continue
        out.append((w, idx == 0))
    return out


def name_ok(word: str, text_norm: str) -> bool:
    w = norm(word)
    return re.search(r"(?<![a-z0-9])" + re.escape(w) + r"(?![a-z0-9])", text_norm) is not None


def check_sentence(sentence: str, ids: list[str], corpora: dict[str, str], vocab: set[str]) -> list[str]:
    """Return a list of problems; empty means verified."""
    if not ids:
        return ["no citation"]
    missing = [i for i in ids if i not in corpora]
    if missing:
        return [f"cites unknown source {','.join(missing)}"]
    text = " ".join(corpora[i] for i in ids)
    p = plain(sentence)
    problems = []
    for num, pct, mult in numbers_in(p):
        if not number_ok(num, pct, mult, text):
            problems.append(f"number '{num}{pct}{(' ' + mult) if mult else ''}' not in cited source")
    for word, at_start in names_in(p):
        if name_ok(word, text):
            continue
        if at_start and (word.lower() in vocab or word.lower() in COMMON_STARTERS) \
                and not any(c.isdigit() for c in word) and not any(c.isupper() for c in word[1:]):
            continue                      # ordinary word that just starts the sentence
        problems.append(f"name '{word}' not in cited source")
    low = norm(p)
    for hw in HYPE_WORDS:
        if re.search(r"(?<![a-z])" + re.escape(hw) + r"(?![a-z])", low):
            problems.append(f"hype word '{hw}'")
    return problems


class Verifier:
    def __init__(self, sources: list[dict], max_quotes: int = 1):
        self.sources = {s["id"]: s for s in sources}
        self.corpora = {s["id"]: corpus(s) for s in sources}
        self.vocab = set(re.findall(r"[a-z][a-z'\-]+", " ".join(self.corpora.values())))
        self.max_quotes = max_quotes
        self.quotes_used = 0
        self.log: list[dict] = []

    def story_ids(self, sid: str) -> list[str]:
        story = self.sources.get(sid, {}).get("story")
        return [k for k, s in self.sources.items() if s.get("story") == story]

    def sentence(self, s: str, where: str, fallback_ids: list[str]) -> str | None:
        ids = cites(s) or list(fallback_ids)
        problems = check_sentence(s, ids, self.corpora, self.vocab)
        repaired = False
        if problems and ids and not problems[0].startswith(("no citation", "cites unknown")) \
                and not any(p.startswith("hype") for p in problems):
            # the fact may sit in a sibling source of the same story: widen and re-cite
            wider = list(dict.fromkeys(ids + [k for i in ids for k in self.story_ids(i)]))
            if not check_sentence(s, wider, self.corpora, self.vocab):
                cur = list(ids)
                for k in wider:
                    if k in cur:
                        continue
                    cur.append(k)
                    if not check_sentence(s, cur, self.corpora, self.vocab):
                        break
                ids, problems, repaired = cur, [], True
        quote_problem = self._inline_quotes(plain(s), ids)
        if quote_problem:
            problems.append(quote_problem)
        status = "dropped" if problems else ("repaired" if repaired or not cites(s) else "ok")
        self.log.append({"where": where, "text": plain(s), "sources": ids, "status": status, "problems": problems})
        return None if problems else tidy(plain(s), ids)

    def _inline_quotes(self, p: str, ids: list[str]) -> str | None:
        for q in QUOTE_RE.findall(p):
            if len(q.split()) < 4:
                continue                      # a quoted term or title, not a quotation
            if norm(q) not in " ".join(self.corpora.get(i, "") for i in ids):
                return "quotation not verbatim in source"
            if self.quotes_used >= self.max_quotes:
                return "more than one quotation"
            self.quotes_used += 1
        return None

    def paragraph(self, text: str, where: str) -> str:
        sents = split_sentences(text)
        para_ids = list(dict.fromkeys(i for s in sents for i in cites(s)))
        kept = [self.sentence(s, where, para_ids) for s in sents]
        return " ".join(k for k in kept if k)

    def quote(self, q: dict | None) -> dict | None:
        if not q:
            return None
        sid = q.get("source")
        ok = sid in self.corpora and norm(q.get("text", "")) in self.corpora[sid] and len(q.get("text", "").split()) <= 25
        speaker_ok = not q.get("speaker") or all(name_ok(w, self.corpora.get(sid, "")) for w, _ in names_in(q["speaker"]))
        if ok and speaker_ok and self.quotes_used < self.max_quotes:
            self.quotes_used += 1
            self.log.append({"where": "quote", "text": q["text"], "sources": [sid], "status": "ok", "problems": []})
            return q
        self.log.append({"where": "quote", "text": q.get("text", ""), "sources": [sid], "status": "dropped",
                         "problems": ["quotation not verbatim in source" if not ok else "speaker or quota check failed"]})
        return None

    def chart(self, c: dict | None) -> dict | None:
        if not c:
            return None
        sid = c.get("source")
        text = self.corpora.get(sid, "")
        bars = []
        for b in c.get("bars", []):
            try:
                val = float(b.get("value"))
            except (TypeError, ValueError):
                continue
            num = f"{val:g}"
            label_names = [w for w, _ in names_in(str(b.get("label", "")))] or str(b.get("label", "")).split()
            label_hit = any(name_ok(w, text) for w in label_names)
            value_hit = number_ok(num, "", "", text)
            status = "ok" if (label_hit and value_hit) else "dropped"
            self.log.append({"where": "chart", "text": f"{b.get('label')}: {num}", "sources": [sid], "status": status,
                             "problems": [] if status == "ok" else ["value or label not in chart source"]})
            if status == "ok":
                bars.append({"label": str(b["label"]), "value": val})
        if len(bars) < 2:
            return None
        title_ok = not check_sentence(c.get("title", "") + f" [{sid}]", [sid], self.corpora, self.vocab)
        return {"title": c.get("title", "") if title_ok else "Figures reported in the source", "unit": c.get("unit", ""),
                "source": sid, "bars": bars}

    def diagram(self, d: dict | None) -> dict | None:
        if not d:
            return None
        sid = d.get("source")
        steps = [str(x) for x in d.get("steps", [])][:5]
        good = [st for st in steps if not check_sentence(st + f" [{sid}]", [sid], self.corpora, self.vocab)]
        status = "ok" if len(good) == len(steps) and len(good) >= 3 else "dropped"
        self.log.append({"where": "diagram", "text": " → ".join(steps), "sources": [sid], "status": status,
                         "problems": [] if status == "ok" else ["a step could not be traced to the source"]})
        return {"title": d.get("title", ""), "source": sid, "steps": good} if status == "ok" else None

    def section_title(self, section: dict, paras: list[str]) -> str:
        """Titles must use only names found in that section's sources; otherwise fall back to the lead source's title."""
        ids = list(dict.fromkeys(i for p in paras for i in cites(p)))
        ids = list(dict.fromkeys(ids + [k for i in ids for k in self.story_ids(i)]))
        title = plain(section.get("title", ""))
        problems = check_sentence(title + "".join(f"[{i}]" for i in ids), ids, self.corpora, self.vocab) if title else ["empty"]
        self.log.append({"where": "section title", "text": title, "sources": ids,
                         "status": "dropped" if problems else "ok", "problems": problems})
        if not problems:
            return title
        lead = self.sources.get(ids[0], {}).get("title", "") if ids else ""
        return (lead[:90].rsplit(" ", 1)[0] + "…") if len(lead) > 90 else lead

    def headline(self, h: str) -> tuple[str, list[str]]:
        all_ids = list(self.corpora)
        problems = []
        p = plain(h)
        text = " ".join(self.corpora.values())
        for num, pct, mult in numbers_in(p):
            if not number_ok(num, pct, mult, text):
                problems.append(f"number '{num}' not in any source")
        for word, _ in names_in(p):
            if not name_ok(word, text) and word.lower() not in self.vocab:
                problems.append(f"name '{word}' not in any source")
        self.log.append({"where": "headline", "text": p, "sources": all_ids,
                         "status": "dropped" if problems else "ok", "problems": problems})
        return p, problems


def verify_draft(draft: dict, sources: list[dict], max_quotes: int = 1) -> tuple[dict, dict]:
    """Run layer 1. Returns the cleaned post body and a report."""
    v = Verifier(sources, max_quotes=max_quotes)
    headline, head_problems = v.headline(draft.get("headline", ""))
    post = {"headline": headline, "tags": draft.get("tags", [])}
    post["quote"] = v.quote(draft.get("quote"))
    post["dek"] = v.paragraph(draft.get("dek", ""), "dek")
    post["what_happened"] = [x for x in (v.paragraph(b, f"what_happened[{n}]") for n, b in enumerate(draft.get("what_happened", []))) if x]
    post["sections"] = []
    for n, s in enumerate(draft.get("sections", [])):
        paras = [x for x in (v.paragraph(p, f"sections[{n}]") for p in s.get("paragraphs", [])) if x]
        words = sum(len(plain(x).split()) for x in paras)
        if words >= 80:
            post["sections"].append({**s, "title": v.section_title(s, paras), "paragraphs": paras})
        else:
            v.log.append({"where": f"sections[{n}]", "text": s.get("title", ""), "sources": [], "status": "dropped",
                          "problems": [f"only {words} verified words left in section"]})
    post["why_it_matters"] = []
    for n, w in enumerate(draft.get("why_it_matters", [])):
        t = v.paragraph(w.get("text", ""), f"why_it_matters[{n}]")
        if t:
            post["why_it_matters"].append({"text": t, "speculative": bool(w.get("speculative"))})
    post["chart"] = v.chart(draft.get("chart"))
    post["diagram"] = v.diagram(draft.get("diagram"))
    report = summarise(v.log)
    report["headline_problems"] = head_problems
    return post, report


def summarise(log: list[dict]) -> dict:
    counts = {"ok": 0, "repaired": 0, "dropped": 0}
    for e in log:
        counts[e["status"]] = counts.get(e["status"], 0) + 1
    return {"checked": len(log), **counts, "entries": log, "layer1_done": True, "layer2_done": False}


# ---------------------------------------------------------------- layer 2

LLM_CHECK_SYSTEM = """You are a strict fact-checker. You compare sentences with the source text they cite.
You reply with one JSON object and nothing else."""


def llm_check(chain, post: dict, sources: list[dict], report: dict) -> tuple[dict, dict]:
    """Ask the model which sentences their cited sources don't support, and drop those."""
    by_id = {s["id"]: s for s in sources}
    sentences: list[tuple[str, str, str]] = []   # (key, sentence, location)

    def collect(text: str, where: str):
        for s in split_sentences(text):
            sentences.append((f"C{len(sentences) + 1}", s, where))

    collect(post["dek"], "dek")
    for b in post["what_happened"]:
        collect(b, "what_happened")
    for s in post["sections"]:
        for p in s["paragraphs"]:
            collect(p, "sections")
    for w in post["why_it_matters"]:
        if not w["speculative"]:
            collect(w["text"], "why_it_matters")
    used = sorted({i for _, s, _ in sentences for i in cites(s)}, key=lambda x: int(x[1:]))
    src_block = "\n\n".join(f"[{i}] {by_id[i]['publisher']} — {by_id[i]['title']}\n{by_id[i]['text'][:2600]}" for i in used if i in by_id)
    claims = "\n".join(f"{k}: {s}" for k, s, _ in sentences)
    prompt = (f"For each claim, decide whether the cited source text supports it. A claim is unsupported if it "
              f"states something the source does not say, gets a number, name or date wrong, or attributes something "
              f"to the wrong party. Paraphrase is fine. Reply as {{\"unsupported\": [{{\"id\": \"C3\", \"reason\": \"...\"}}]}} "
              f"with an empty list if all are supported.\n\nCLAIMS\n{claims}\n\nSOURCES\n{src_block}")
    result = chain.ask_json(LLM_CHECK_SYSTEM, prompt, temperature=0.0)
    bad = {str(x.get("id")): str(x.get("reason", "")) for x in result.get("unsupported", []) if isinstance(x, dict)}
    drop = {s: bad[k] for k, s, _ in sentences if k in bad}

    def filt(text: str) -> str:
        return " ".join(s for s in split_sentences(text) if s not in drop)

    post = {**post}
    post["dek"] = filt(post["dek"])
    post["what_happened"] = [x for x in (filt(b) for b in post["what_happened"]) if x]
    post["sections"] = [{**s, "paragraphs": [x for x in (filt(p) for p in s["paragraphs"]) if x]} for s in post["sections"]]
    post["sections"] = [s for s in post["sections"] if sum(len(plain(p).split()) for p in s["paragraphs"]) >= 80]
    post["why_it_matters"] = [{**w, "text": filt(w["text"])} for w in post["why_it_matters"] if filt(w["text"])]
    for s, reason in drop.items():
        report["entries"].append({"where": "layer2", "text": plain(s), "sources": cites(s), "status": "dropped",
                                  "problems": [f"model check: {reason}"]})
        report["dropped"] += 1
    report["layer2_done"] = True
    report["layer2_flagged"] = len(drop)
    return post, report
