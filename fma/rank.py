"""Group items into stories, score them, drop anything already covered, and pick the day's lineup."""
from __future__ import annotations

import math
import re
from datetime import datetime, timedelta, timezone

from .models import Item, Story

STOP = set("""a an and are as at be by for from has have how in into is it its of on or that the this to
was were what when why will with new you your our we can more over after about up out not vs via just now
says said say get gets one two three first year years day today week ai""".split())

CATEGORIES = ["models", "research", "products", "tools", "policy", "impact"]


def tokens(title: str) -> set[str]:
    words = re.findall(r"[a-z0-9][a-z0-9.\-+]*", title.lower())
    return {w.strip(".-") for w in words if w not in STOP and len(w) > 2}


def jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


# Words that name the same kind of event, so "files S-1" and "IPO prospectus" line up.
EVENT_SYNONYMS = {"s-1": "ipo", "prospectus": "ipo", "filing": "ipo", "files": "ipo", "debut": "ipo", "listing": "ipo",
                  "lawsuit": "sue", "sues": "sue", "sued": "sue", "acquires": "acqui", "acquisition": "acqui",
                  "buys": "acqui", "launches": "launc", "unveils": "launc", "introduces": "launc", "introducing": "launc"}
GENERIC = STOP | set("""model models agent agents language large llm llms learning using based toward towards build
building open data system systems help helps work works world better make makes making time back like""".split())


def stems(title: str) -> set[str]:
    """Coarse word roots for matching the same event across differently worded headlines."""
    out = set()
    for w in re.findall(r"[a-z0-9][a-z0-9\-]+", title.lower().replace("’", "'").replace("'s", "")):
        if w in EVENT_SYNONYMS:
            out.add(EVENT_SYNONYMS[w])
        elif w not in GENERIC and len(w) > 3:
            out.add(w[:5])
    return out


def same_story(t1: set[str], s1: set[str], t2: set[str], s2: set[str], strict: bool = False) -> bool:
    if jaccard(t1, t2) >= (0.6 if strict else 0.34):
        return True
    if strict:
        return False
    shared = s1 & s2
    return len(shared) >= 3 or (len(shared) >= 2 and jaccard(s1, s2) >= 0.2)


def norm_url(url: str) -> str:
    url = re.sub(r"[?#].*$", "", url.strip().lower())
    url = re.sub(r"^https?://(www\.)?", "", url)
    url = re.sub(r"(v\d+)?/?$", "", url) if "arxiv.org" in url else url.rstrip("/")
    return url.replace("arxiv.org/pdf/", "arxiv.org/abs/")


def cluster(items: list[Item]) -> list[Story]:
    """Greedy clustering: same URL, or a headline that matches any headline already in the story."""
    stories: list[tuple[list[tuple[set[str], set[str], bool]], set[str], Story]] = []
    for it in sorted(items, key=lambda i: -i.weight):
        t, s, u = tokens(it.title), stems(it.title), norm_url(it.url)
        for sigs, urls, st in stories:
            if u in urls or any(same_story(t, s, t2, s2, strict=it.strict_match or k) for t2, s2, k in sigs):
                st.items.append(it)
                sigs.append((t, s, it.strict_match))
                urls.add(u)
                break
        else:
            stories.append(([(t, s, it.strict_match)], {u}, Story(items=[it])))
    return [st for _, _, st in stories]


def guess_category(story: Story, hints: dict[str, list[str]]) -> str:
    if all(i.category == "research" for i in story.items):
        return "research"       # papers stay papers, whatever words their titles use
    text = " ".join(i.title for i in story.items)
    best, best_n = None, 0
    for cat, words in hints.items():
        # hints written with capitals (EU, IPO, "AI Act") match case-sensitively
        n = sum(1 for w in words if re.search(r"(?<!\w)" + re.escape(w) + r"(?!\w)", text, 0 if w != w.lower() else re.I))
        if n > best_n:
            best, best_n = cat, n
    if best:
        return best
    cats = [i.category for i in story.items]
    return max(set(cats), key=cats.count)


def score_story(story: Story, now: datetime, half_life_h: float = 18.0) -> float:
    """Importance = best single item + breadth of coverage + community attention."""
    best = 0.0
    for it in story.items:
        age_h = max(0.0, (now - it.published).total_seconds() / 3600) if it.published else 24.0
        recency = 0.5 ** (age_h / half_life_h)
        best = max(best, it.weight * (0.4 + 0.6 * recency))
    outlets = len(story.publishers)
    coverage = 0.9 * math.log2(outlets) if outlets > 1 else 0.0
    points = max((i.points for i in story.items if i.source_id in ("hn", "hf-papers")), default=0)
    stars = max((i.points for i in story.items if i.source_id == "github"), default=0)
    attention = 0.35 * math.log10(1 + points) + 0.15 * math.log10(1 + stars)
    return round(best + coverage + attention, 4)


def recent_history(history: list[dict], today: str, days: int) -> list[dict]:
    cutoff = (datetime.fromisoformat(today) - timedelta(days=days)).date().isoformat()
    return [h for h in history if cutoff <= h["date"] < today]


def already_covered(story: Story, history: list[dict], today: str, dedupe_days: int, similar_days: int) -> bool:
    urls = {norm_url(i.url) for i in story.items}
    for h in recent_history(history, today, dedupe_days):
        if urls & set(h.get("urls", [])):
            return True
    toks = tokens(" ".join(i.title for i in story.items[:3]))
    for h in recent_history(history, today, similar_days):
        for prev in h.get("story_tokens", []):
            if jaccard(toks, set(prev)) >= 0.4:
                return True
    return False


def rank(items: list[Item], cfg: dict, pipe: dict, history: list[dict], now: datetime, today: str) -> list[Story]:
    """Return candidate stories, best first, with old and already-covered stories removed."""
    lookback = now - timedelta(hours=int(pipe.get("lookback_hours", 40)))
    fresh = [i for i in items if i.published is None or i.published >= lookback]
    stories = cluster(fresh)
    hints = cfg.get("category_hints", {})
    demote = [re.compile(p, re.I) for p in cfg.get("demote_patterns", [])]
    boost = [re.compile(p, re.I) for p in cfg.get("boost_patterns", [])]
    out = []
    for st in stories:
        if already_covered(st, history, today, int(pipe.get("dedupe_days", 14)), int(pipe.get("similar_title_days", 3))):
            continue
        st.category = guess_category(st, hints)
        st.score = score_story(st, now)
        if len(st.publishers) == 1 and any(p.search(st.title) for p in demote):
            st.score = round(st.score * 0.5, 4)
        if any(i.primary and p.search(i.title) for i in st.items for p in boost):
            st.score = round(st.score + 0.6, 4)
        out.append(st)
    out.sort(key=lambda s: s.score, reverse=True)
    return out


def pick_lineup(stories: list[Story], n: int = 5, max_per_category: int = 2, max_per_source: int = 1) -> list[Story]:
    """Top stories with caps per category and per single-source origin, so one busy topic or one prolific
    blog can't take over the post, and with a research story included when one ranks in the top 15."""
    picked: list[Story] = []
    counts: dict[str, int] = {}
    solo: dict[str, int] = {}
    for st in stories:
        if len(picked) >= n:
            break
        if counts.get(st.category, 0) >= max_per_category:
            continue
        src = (st.items[0].outlet or st.items[0].source_id) if len(st.publishers) == 1 else None
        cap = max_per_source if st.items[0].primary or st.items[0].outlet else max_per_source + 1
        if src and solo.get(src, 0) >= cap:
            continue
        mine = stems(" ".join(i.title for i in st.items))
        if any(len(mine & stems(" ".join(i.title for i in p.items)) - {"ipo", "launc", "acqui", "sue"}) >= 1
               and len(mine & stems(" ".join(i.title for i in p.items))) >= 2 for p in picked):
            continue          # another angle on a story already in the lineup
        picked.append(st)
        counts[st.category] = counts.get(st.category, 0) + 1
        if src:
            solo[src] = solo.get(src, 0) + 1
    if picked and not any(s.category == "research" for s in picked):
        research = next((s for s in stories[:15] if s.category == "research" and s not in picked), None)
        if research:
            if len(picked) >= n:
                picked[-1] = research
            else:
                picked.append(research)
    return picked[:n]


def history_entry(date: str, slug: str, stories: list[Story]) -> dict:
    urls = sorted({norm_url(i.url) for s in stories for i in s.items})
    return {"date": date, "slug": slug, "urls": urls,
            "tokens": sorted(tokens(" ".join(i.title for s in stories for i in s.items[:3]))),
            "story_tokens": [sorted(tokens(" ".join(i.title for i in s.items[:3]))) for s in stories]}
