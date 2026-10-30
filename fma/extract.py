"""Pull readable text out of an article page. This text is what the writer reads and what the
verifier checks every claim against, so it only ever comes from the linked page itself."""
from __future__ import annotations

import logging
import re

from bs4 import BeautifulSoup

from .feeds import Http, fix_mojibake, strip_html
from .models import Item

log = logging.getLogger(__name__)

MAX_CHARS = 7000
DROP_TAGS = ["script", "style", "noscript", "nav", "header", "footer", "aside", "form", "svg", "figure", "button"]


def html_to_text(raw: bytes | str) -> str:
    soup = BeautifulSoup(raw, "lxml")
    for t in soup(DROP_TAGS):
        t.decompose()
    root = soup.find("article") or soup.find("main") or soup.body or soup
    parts = []
    for el in root.find_all(["h1", "h2", "h3", "p", "li", "td", "blockquote"]):
        txt = re.sub(r"\s+", " ", el.get_text(" ", strip=True))
        if len(txt) >= 25 or el.name in ("h1", "h2", "h3", "td"):
            parts.append(txt)
    text = "\n".join(dict.fromkeys(parts))  # drop exact repeats, keep order
    return text[:MAX_CHARS]


def arxiv_abs_url(url: str) -> str:
    m = re.search(r"arxiv\.org/(?:abs|pdf|html)/([\w.\-/]+?)(?:v\d+)?(?:\.pdf)?$", url)
    return f"https://arxiv.org/abs/{m.group(1)}" if m else url


def extract_item(item: Item, http: Http) -> str:
    """Return the best available source text for an item. Falls back to the feed summary."""
    url = arxiv_abs_url(item.url)
    if "github.com" in url:
        return _github_text(item, http)
    m = re.match(r"https://huggingface\.co/([^/]+/[^/#?]+)$", url)
    if m:                                   # a model page: read its model card in plain markdown
        try:
            r = http.get(f"https://huggingface.co/{m.group(1)}/raw/main/README.md")
            if r.status_code == 200 and len(r.text) > 200:
                return _strip_front_matter(r.text)[:MAX_CHARS]
        except Exception:  # noqa: BLE001
            pass
    try:
        r = http.get(url)
        if r.status_code == 200 and "html" in r.headers.get("content-type", "html"):
            text = fix_mojibake(html_to_text(r.content))
            if len(text) > 200:
                return text
    except Exception as exc:  # noqa: BLE001
        log.info("extract failed for %s: %s", url, exc)
    return strip_html(item.summary)[:MAX_CHARS]


def _strip_front_matter(md: str) -> str:
    md = re.sub(r"^---\n.*?\n---\n", "", md, flags=re.S)
    md = re.sub(r"<[^>]+>", " ", md)                 # inline HTML badges
    md = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", md)      # images
    return re.sub(r"\n{3,}", "\n\n", md).strip()


def _github_text(item: Item, http: Http) -> str:
    m = re.search(r"github\.com/([^/]+/[^/#?]+)", item.url)
    text = item.summary
    if m:
        try:
            r = http.get(f"https://raw.githubusercontent.com/{m.group(1)}/HEAD/README.md")
            if r.status_code == 200:
                text = f"{item.summary}\n{r.text}"
        except Exception:  # noqa: BLE001
            pass
    return text[:MAX_CHARS]
