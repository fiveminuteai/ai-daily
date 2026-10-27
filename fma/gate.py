"""The quality gate. A post is published only if every check here passes."""
from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from .rank import jaccard, tokens
from .verify import plain
from .write import HYPE_WORDS

# 401/403/429 mean the server answered but refuses bots; the page exists, so the link is not broken.
REACHABLE = {401, 403, 405, 429}


def body_texts(post: dict) -> list[str]:
    parts = [post.get("dek", "")] + post.get("what_happened", [])
    for s in post.get("sections", []):
        parts.append(s.get("title", ""))
        parts.extend(s.get("paragraphs", []))
    parts.extend(w["text"] for w in post.get("why_it_matters", []))
    if post.get("quote"):
        parts.append(post["quote"]["text"])
    return parts


def word_count(post: dict) -> int:
    return sum(len(re.findall(r"[\w’'\-]+", plain(t))) for t in body_texts(post)) + len(post.get("headline", "").split())


def check_links(urls: list[str], http) -> dict[str, str]:
    """Return {url: problem} for links that don't resolve."""
    def probe(u: str):
        try:
            r = http.head(u)
            if r.status_code in (403, 404, 405) or r.status_code >= 500:   # some servers reject HEAD; ask properly
                r = http.get(u, stream=True)
                r.close()
            if r.status_code < 400 or r.status_code in REACHABLE:
                return u, None
            return u, f"HTTP {r.status_code}"
        except Exception as exc:  # noqa: BLE001
            return u, type(exc).__name__

    with ThreadPoolExecutor(max_workers=8) as pool:
        return {u: p for u, p in pool.map(probe, sorted(set(urls))) if p}


def check_images(html_text: str, out_dir: Path, base_path: str) -> list[str]:
    """Every <img src> and og:image in the page must exist in the built site."""
    missing = []
    refs = re.findall(r'<img[^>]+src="([^"]+)"', html_text) + re.findall(r'property="og:image" content="([^"]+)"', html_text)
    for ref in refs:
        rel = re.sub(r"^https?://[^/]+", "", ref)
        if rel.startswith(base_path):
            rel = rel[len(base_path):]
        if not (out_dir / rel.lstrip("/")).exists():
            missing.append(ref)
    return missing


def is_duplicate(post: dict, recent_posts: list[dict], threshold: float = 0.5) -> str | None:
    """Compare headline and section titles with recent posts."""
    def sig(p):
        return tokens(" ".join([p.get("headline", "")] + [s.get("title", "") for s in p.get("sections", [])]))

    mine = sig(post)
    for other in recent_posts:
        if other.get("date") == post.get("date"):
            continue
        if jaccard(mine, sig(other)) >= threshold or post.get("headline", "").strip().lower() == other.get("headline", "").strip().lower():
            return other.get("date")
    return None


def run_gate(post: dict, report: dict, pipe: dict, recent_posts: list[dict], http=None, skip_links: bool = False) -> list[str]:
    """Return a list of failures. Empty list = publish."""
    fails = []
    n = word_count(post)
    if not pipe.get("words_min", 880) <= n <= pipe.get("words_max", 1150):
        fails.append(f"word count {n} outside {pipe.get('words_min', 880)}-{pipe.get('words_max', 1150)}")
    if not post.get("headline") or report.get("headline_problems"):
        fails.append(f"headline not verified: {report.get('headline_problems')}")
    if len(post.get("what_happened", [])) != 3:
        fails.append(f"'what happened' has {len(post.get('what_happened', []))} bullets, needs 3")
    if not pipe.get("min_stories", 3) <= len(post.get("sections", [])) <= 5:
        fails.append(f"{len(post.get('sections', []))} sections, needs {pipe.get('min_stories', 3)}-5")
    if not post.get("why_it_matters"):
        fails.append("no 'why it matters'")
    if not report.get("layer1_done"):
        fails.append("verification pass not run")
    if pipe.get("llm_check") and not report.get("layer2_done"):
        fails.append("model fact-check pass not run")
    low = " ".join(plain(t) for t in body_texts(post)).lower()
    hype = [w for w in HYPE_WORDS if re.search(r"(?<![a-z])" + re.escape(w) + r"(?![a-z])", low)]
    if hype:
        fails.append(f"hype words: {hype}")
    if "!" in low:
        fails.append("exclamation mark in body")
    cited = {i for t in body_texts(post) for i in re.findall(r"\[(S\d+)\]", t)}
    listed = {s["id"] for s in post.get("sources", [])}
    if cited - listed:
        fails.append(f"citations without a listed source: {sorted(cited - listed)}")
    if not post.get("visuals"):
        fails.append("no visual")
    dup = is_duplicate(post, recent_posts)
    if dup:
        fails.append(f"too similar to the post of {dup}")
    if not skip_links and http is not None:
        bad = check_links([s["url"] for s in post.get("sources", [])], http)
        if bad:
            fails.append(f"broken links: {bad}")
    return fails
