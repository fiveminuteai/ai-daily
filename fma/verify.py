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

from .write import BASELINE_BLOCKS, HYPE_WORDS

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
NUM_RE = re.compile(r"(?<![\w.])[$€£₹]?(\d+(?:[.,]\d+)*)(\s?%)?"
                    r"(?:\s?(trillion|billion|million|thousand|tn|bn|mn|[TBMK])(?![\w-]))?", re.I)
MULT_ALIAS = {"tn": "trillion", "t": "trillion", "bn": "billion", "b": "billion", "mn": "million", "m": "million",
              "k": "thousand"}
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
        protected = protected.replace(a, a.replace(".", "\u2024"))
    # a middle initial ("Frederick P. Brooks") doesn't end a sentence
    protected = re.sub(r"\b([A-Z][a-z]+ [A-Z])\.(?= [A-Z])", "\\1\u2024", protected)
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
        mult = (m.group(3) or "").lower()
        out.append((num, (m.group(2) or "").strip(), MULT_ALIAS.get(mult, mult)))
    return out


def strip_number_units(text: str) -> str:
    """Remove the unit letter in '$18 M' / '3.1B' so it isn't mistaken for a name."""
    return re.sub(r"(\d)\s?[TBMK]\b", r"\1", text)


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


def in_vocab(w: str, vocab: set[str]) -> bool:
    """Is this an ordinary word from the day's sources, allowing simple endings (reveal/reveals/revealed/revealing)?"""
    bases = {w}
    for suf in ("ing", "ies", "es", "ed", "s", "d"):
        if w.endswith(suf) and len(w) - len(suf) >= 3:
            bases.add(w[: -len(suf)] + ("y" if suf == "ies" else ""))
    forms = set()
    for b in bases:
        forms |= {b, b + "s", b + "es", b + "d", b + "ed", b + "ing", b + "e", b + "er"}
        if b.endswith("e"):
            forms.add(b[:-1] + "ing")
        if b.endswith("y"):
            forms |= {b[:-1] + "ies", b[:-1] + "ied"}
    return bool(forms & vocab)


def is_title_case(text: str) -> bool:
    words = [w for w in re.findall(r"[A-Za-z][A-Za-z'’\-]*", text) if len(w) > 3]
    return len(words) >= 3 and sum(w[0].isupper() for w in words) / len(words) > 0.6


def check_sentence(sentence: str, ids: list[str], corpora: dict[str, str], vocab: set[str]) -> list[str]:
    """Return a list of problems; empty means verified."""
    if not ids:
        return ["no citation"]
    missing = [i for i in ids if i not in corpora]
    if missing:
        return [f"cites unknown source {','.join(missing)}"]
    text = " ".join(corpora[i] for i in ids)
    p = plain(sentence)
    titled = is_title_case(p)            # "Anthropic Files IPO, Revealing High Costs": capitals aren't names here
    problems = []
    for num, pct, mult in numbers_in(p):
        if not number_ok(num, pct, mult, text):
            problems.append(f"number '{num}{pct}{(' ' + mult) if mult else ''}' not in cited source")
    for word, at_start in names_in(strip_number_units(p)):
        if name_ok(word, text):
            continue
        if (at_start or titled) and (in_vocab(word.lower(), vocab) or word.lower() in COMMON_STARTERS) \
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
        self.raw = " ".join(f"{s.get('title', '')}. {s.get('text', '')}" for s in sources)   # original capitalisation
        self.max_quotes = max_quotes
        self.quotes_used = 0
        self.log: list[dict] = []

    def story_ids(self, sid: str) -> list[str]:
        story = self.sources.get(sid, {}).get("story")
        return [k for k, s in self.sources.items() if s.get("story") == story]

    def auto_cite(self, s: str) -> list[str]:
        """For an uncited sentence with checkable facts, find the one story whose sources contain all of them."""
        p = plain(s)
        if not numbers_in(p) and not [w for w, start in names_in(p) if not start]:
            return []                     # nothing checkable: don't guess a source
        stories = list(dict.fromkeys(src.get("story") for src in self.sources.values()))
        for st in stories:
            ids = [k for k, src in self.sources.items() if src.get("story") == st]
            if not check_sentence(s, ids, self.corpora, self.vocab):
                cur = []
                for k in ids:               # smallest prefix of the story's sources that covers the facts
                    cur.append(k)
                    if not check_sentence(s, cur, self.corpora, self.vocab):
                        return cur
                return ids
        return []

    def sentence(self, s: str, where: str, fallback_ids: list[str]) -> str | None:
        ids = cites(s) or list(fallback_ids) or self.auto_cite(s)
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
        if status != "ok":
            return None
        out = {"title": d.get("title", ""), "source": sid, "steps": good, "kind": "flow"}
        if d.get("kind") == "compare":
            allowed = {b.lower(): b for b in BASELINE_BLOCKS}
            base = [allowed[str(b).strip().lower()] for b in d.get("baseline", []) if str(b).strip().lower() in allowed][:5]
            if len(base) >= 2:
                out.update(kind="compare", baseline=base)
            else:
                self.log.append({"where": "diagram", "text": "standard-transformer side", "sources": [], "status": "dropped",
                                 "problems": ["baseline blocks not from the allowed list; drawn as a plain flow"]})
        return out

    def section_title(self, section: dict, paras: list[str]) -> str:
        """Titles must use only names found in that section's sources; otherwise fall back to the lead source's title."""
        ids = list(dict.fromkeys(i for p in paras for i in cites(p)))
        ids = list(dict.fromkeys(ids + [k for i in ids for k in self.story_ids(i)]))
        title = self.sentence_case(plain(section.get("title", "")))
        problems = check_sentence(title + "".join(f"[{i}]" for i in ids), ids, self.corpora, self.vocab) if title else ["empty"]
        self.log.append({"where": "section title", "text": title, "sources": ids,
                         "status": "dropped" if problems else "ok", "problems": problems})
        if not problems:
            return title
        lead = self.sources.get(ids[0], {}).get("title", "") if ids else ""
        return (lead[:90].rsplit(" ", 1)[0] + "…") if len(lead) > 90 else lead

    def sentence_case(self, text: str) -> str:
        """Turn 'Anthropic's IPO Filing Reveals High Costs' into 'Anthropic's IPO filing reveals high costs'.
        A capitalised word is lowered only if it is an ordinary word in today's sources and the sources never
        capitalise it mid-sentence. Anything else keeps its capital and must pass the name check."""
        if not is_title_case(text):
            return text
        words = text.split(" ")
        for n, w in enumerate(words[1:], 1):
            core = re.sub(r"[^\w'’\-]", "", w).removesuffix("'s").removesuffix("’s")
            if not core or not core[0].isupper() or any(c.isupper() or c.isdigit() for c in core[1:]):
                continue
            low = core.lower()
            ordinary = in_vocab(low, self.vocab) or low in COMMON_STARTERS
            capitalised_in_sources = re.search(r"[a-z,;] " + re.escape(core) + r"\b", self.raw) is not None
            if ordinary and not capitalised_in_sources:
                words[n] = w.replace(core, low, 1)
        return " ".join(words)

    def headline(self, h: str) -> tuple[str, list[str]]:
        all_ids = list(self.corpora)
        problems = []
        p = self.sentence_case(plain(h))
        text = " ".join(self.corpora.values())
        for num, pct, mult in numbers_in(p):
            if not number_ok(num, pct, mult, text):
                problems.append(f"number '{num}' not in any source")
        for word, start in names_in(p):
            if name_ok(word, text) or (start and (in_vocab(word.lower(), self.vocab) or word.lower() in COMMON_STARTERS)):
                continue
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
            # "why it matters" is analysis by nature: always shown labelled as our read; its names and numbers
            # were still checked above
            post["why_it_matters"].append({"text": t, "speculative": True})
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


TOKEN_RE = re.compile(r"[a-z0-9]+")


def evidence_found(quote: str, corpus_norm: str, need: float = 0.85) -> bool:
    """The checker's quote must really be in the source. Each piece (split on '...') must have at least 85% of its
    words together in one short stretch of the source, so small differences in punctuation, quote marks or a
    dropped word don't matter, but a sentence assembled from scattered words or invented outright doesn't pass."""
    ctoks = TOKEN_RE.findall(corpus_norm)
    pieces = [TOKEN_RE.findall(norm(p)) for p in re.split(r"\.\.\.|…", quote)]
    pieces = [p for p in pieces if len(p) >= 4] or [TOKEN_RE.findall(norm(quote))]
    if not pieces or not pieces[0]:
        return False
    for q in pieces:
        span = int(len(q) * 1.3) + 2
        starts = {t for t in q[:3]}
        ok = False
        for i, t in enumerate(ctoks):
            if t not in starts:
                continue
            window = ctoks[i:i + span]
            pool = {}
            for w in window:
                pool[w] = pool.get(w, 0) + 1
            hit = 0
            for w in q:
                if pool.get(w, 0):
                    pool[w] -= 1
                    hit += 1
            if hit / len(q) >= need:
                ok = True
                break
        if not ok:
            return False
    return True


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
    # One check per story, with only that story's sources: small prompts fit tight per-minute token limits and
    # keep the checker focused. Claims citing several stories go with the first story they cite.
    groups: dict = {}
    for k, s, _ in sentences:
        ids = cites(s)
        story = by_id.get(ids[0], {}).get("story") if ids else None
        groups.setdefault(story, []).append((k, s))
    bad: dict[str, str] = {}
    for story, items in groups.items():
        used = sorted({i for _, s in items for i in cites(s)}, key=lambda x: int(x[1:]))
        src_block = "\n\n".join(f"[{i}] {by_id[i]['publisher']} — {by_id[i]['title']}\n{by_id[i]['text'][:2600]}"
                                for i in used if i in by_id)
        corpus_here = " ".join(corpus(by_id[i]) for i in used if i in by_id)
        for start in range(0, len(items), 6):          # small batches keep each reply short
            batch = items[start:start + 6]
            claims = "\n".join(f"{k}: {plain(s)}" for k, s in batch)
            prompt = (
                "Fact-check each claim against the SOURCES. For every claim, first copy the exact sentence or phrase from "
                "the sources that supports it (word for word, at most 40 words), then decide whether that evidence says "
                "the same thing. A claim is NOT supported if the evidence is about a different product, version, person, "
                "result or event than the claim says (for example the source's maths result described as the physics "
                "result, or a version 1 date or feature given to version 2), if a number, name or date differs, if it "
                "presents an older event as new, or if no evidence exists. Paraphrase is fine.\n"
                "Reply as {\"checks\": [{\"id\": \"C1\", \"evidence\": \"exact words from the source\", "
                "\"supported\": true, \"reason\": \"short reason\"}]} with one entry per claim.\n\n"
                f"CLAIMS\n{claims}\n\nSOURCES\n{src_block}")
            result = chain.ask_json(LLM_CHECK_SYSTEM, prompt, temperature=0.0, careful=True)
            checks = {str(c.get("id")): c for c in result.get("checks", []) if isinstance(c, dict)}
            for k, _ in batch:
                c = checks.get(k)
                if c is None:
                    bad[k] = "checker returned no verdict"
                elif not c.get("supported", False):
                    bad[k] = str(c.get("reason") or "not supported by the source")
                elif not evidence_found(str(c.get("evidence", "")), corpus_here):
                    bad[k] = f"checker's evidence quote is not in the source: \"{str(c.get('evidence', ''))[:200]}\""
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
