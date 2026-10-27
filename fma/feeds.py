"""Fetchers for every source kind. Each one returns a list of Items.

All network access goes through an `Http` object so tests can swap in a fake.
"""
from __future__ import annotations

import html
import logging
import re
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

import requests
from urllib.parse import urlparse
from lxml import etree

from .models import Item

log = logging.getLogger(__name__)

USER_AGENT = "Mozilla/5.0 (compatible; FiveMinuteAI/1.0; +https://github.com/saipavan333/ai-daily)"


class Http:
    """Thin wrapper over requests with a polite user agent and timeouts."""

    def __init__(self, timeout: float = 20.0):
        self.session = requests.Session()
        self.session.headers["User-Agent"] = USER_AGENT
        self.timeout = timeout

    def get(self, url: str, **kw) -> requests.Response:
        return self.session.get(url, timeout=self.timeout, **kw)

    def head(self, url: str, **kw) -> requests.Response:
        return self.session.head(url, timeout=self.timeout, allow_redirects=True, **kw)


# ---------------------------------------------------------------- helpers

TAG_RE = re.compile(r"<[^>]+>")
WS_RE = re.compile(r"\s+")


def strip_html(s: str) -> str:
    return WS_RE.sub(" ", html.unescape(TAG_RE.sub(" ", s or ""))).strip()


def parse_date(s: str | None) -> datetime | None:
    if not s:
        return None
    s = s.strip()
    try:
        d = parsedate_to_datetime(s)
    except (TypeError, ValueError, IndexError):
        try:
            d = datetime.fromisoformat(s.replace("Z", "+00:00"))
        except ValueError:
            return None
    if d.tzinfo is None:
        d = d.replace(tzinfo=timezone.utc)
    return d.astimezone(timezone.utc)


def _first(node, *names: str) -> str:
    for n in names:
        found = node.xpath(f"./*[local-name()='{n}']")
        if found:
            el = found[0]
            if n == "link" and el.get("href"):
                return el.get("href")
            txt = "".join(el.itertext()).strip()
            if txt:
                return txt
    return ""


def _atom_link(node) -> str:
    links = node.xpath("./*[local-name()='link']")
    for el in links:
        if el.get("href") and el.get("rel", "alternate") == "alternate":
            return el.get("href")
    for el in links:
        if el.get("href"):
            return el.get("href")
        if (el.text or "").strip():
            return el.text.strip()
    return ""


def parse_feed(content: bytes) -> list[dict]:
    """Parse RSS 2.0, RSS 1.0/RDF or Atom into dicts: title, url, published, summary."""
    root = etree.fromstring(content, etree.XMLParser(recover=True, huge_tree=True, resolve_entities=False))
    if root is None:
        return []
    out = []
    for node in root.xpath("//*[local-name()='item' or local-name()='entry']"):
        title = strip_html(_first(node, "title"))
        url = _atom_link(node)
        published = parse_date(_first(node, "pubDate", "published", "updated", "date"))
        summary = strip_html(_first(node, "description", "summary", "content", "encoded"))
        if title and url:
            out.append({"title": title, "url": url.strip(), "published": published, "summary": summary[:2000]})
    return out


def is_ai_related(text: str, terms: list[str]) -> bool:
    for t in terms:
        if re.search(r"(?<![\w-])" + re.escape(t) + r"(?![\w-])", text, flags=re.I if t != "AI" else 0):
            return True
    return False


def _item(src: dict, title: str, url: str, published, summary: str = "", points: int = 0, comments_url: str = "") -> Item:
    return Item(
        source_id=src["id"], source_name=src["name"], title=title, url=url, published=published,
        summary=summary, category=src.get("category", "products"), weight=float(src.get("weight", 1.0)),
        primary=bool(src.get("primary", False)), points=points, comments_url=comments_url,
        outlet=src.get("outlet", ""), strict_match=bool(src.get("strict_match", False)),
        max_age_h=int(src.get("lookback_hours", 0)),
    )


# ---------------------------------------------------------------- fetchers

def fetch_rss(src: dict, http: Http, **_) -> list[Item]:
    r = http.get(src["url"])
    r.raise_for_status()
    rows = parse_feed(r.content)[: int(src.get("max_items", 40))]
    return [_item(src, x["title"], x["url"], x["published"], x["summary"]) for x in rows]


def fetch_hn(src: dict, http: Http, **_) -> list[Item]:
    r = http.get(src["url"])
    r.raise_for_status()
    out = []
    for h in r.json().get("hits", []):
        url = h.get("url") or f"https://news.ycombinator.com/item?id={h.get('objectID')}"
        published = datetime.fromtimestamp(h["created_at_i"], tz=timezone.utc) if h.get("created_at_i") else None
        it = _item(src, h.get("title") or "", url, published, "", points=int(h.get("points") or 0),
                   comments_url=f"https://news.ycombinator.com/item?id={h.get('objectID')}")
        domain = urlparse(url).netloc.lower().removeprefix("www.")
        if domain != "news.ycombinator.com":
            it.source_name = f"{domain} (via Hacker News)"   # credit the site that wrote it; HN only pointed to it
        out.append(it)
    return out


def fetch_hf_papers(src: dict, http: Http, **_) -> list[Item]:
    r = http.get(src["url"])
    r.raise_for_status()
    out = []
    for row in r.json():
        p = row.get("paper", {})
        pid = p.get("id")
        if not pid:
            continue
        out.append(_item(src, strip_html(p.get("title") or row.get("title") or ""), f"https://arxiv.org/abs/{pid}",
                         parse_date(row.get("publishedAt") or p.get("publishedAt")),
                         strip_html(p.get("summary") or ""), points=int(p.get("upvotes") or 0)))
    return out


def fetch_github(src: dict, http: Http, now: datetime | None = None, **_) -> list[Item]:
    """New repositories with AI topics that gathered stars fast. Uses GitHub's official search API."""
    now = now or datetime.now(timezone.utc)
    since = (now - timedelta(days=7)).strftime("%Y-%m-%d")
    out, seen = [], set()
    for topic in ("llm", "ai-agents", "machine-learning"):
        q = f"topic:{topic} created:>{since} stars:>={int(src.get('min_stars', 300))}"
        r = http.get(src["url"], params={"q": q, "sort": "stars", "order": "desc", "per_page": 10})
        if r.status_code != 200:
            continue
        for repo in r.json().get("items", []):
            if repo["html_url"] in seen:
                continue
            seen.add(repo["html_url"])
            desc = repo.get("description") or ""
            out.append(_item(src, f"{repo['full_name']}: {desc}"[:200], repo["html_url"],
                             parse_date(repo.get("created_at")), desc, points=int(repo.get("stargazers_count") or 0)))
    return out


SKIP_MODEL = re.compile(r"gguf|gptq|awq|exl2|mlx|-bnb|quantized|uncensored|abliterated|comfy|lora|merge", re.I)


def fetch_hf_models(src: dict, http: Http, now: datetime | None = None, **_) -> list[Item]:
    """New, popular model repositories. The model card (README) is the primary source for how the model is built."""
    now = now or datetime.now(timezone.utc)
    r = http.get(src["url"])
    r.raise_for_status()
    out = []
    for m in r.json():
        mid = m.get("id") or m.get("modelId") or ""
        created = parse_date(m.get("createdAt"))
        if not mid or SKIP_MODEL.search(mid) or not created or created < now - timedelta(days=7):
            continue
        if int(m.get("likes") or 0) < int(src.get("min_likes", 150)):
            continue
        task = (m.get("pipeline_tag") or "").replace("-", " ")
        out.append(_item(src, f"New on Hugging Face: {mid}" + (f" ({task})" if task else ""), f"https://huggingface.co/{mid}",
                         created, task, points=int(m.get("likes") or 0)))
    return out


FETCHERS = {"rss": fetch_rss, "hn": fetch_hn, "hf_papers": fetch_hf_papers, "github": fetch_github, "hf_models": fetch_hf_models}


def fetch_all(cfg: dict, http: Http, now: datetime | None = None) -> tuple[list[Item], dict]:
    """Fetch every enabled source. One broken source never stops the run; it is logged in the stats."""
    items: list[Item] = []
    stats: dict[str, str] = {}
    terms = cfg.get("ai_terms", [])
    for src in cfg["sources"]:
        if src.get("enabled", True) is False:
            stats[src["id"]] = "disabled"
            continue
        try:
            got = FETCHERS[src["kind"]](src, http, now=now)
            if src.get("ai_filter"):
                got = [i for i in got if is_ai_related(f"{i.title} {i.summary[:400]}", terms)]
            items.extend(got)
            stats[src["id"]] = f"ok:{len(got)}"
        except Exception as exc:  # noqa: BLE001 - any failure of one source is non-fatal
            log.warning("source %s failed: %s", src["id"], exc)
            stats[src["id"]] = f"error:{type(exc).__name__}"
    return items, stats
