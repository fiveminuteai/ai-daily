"""Checks: one-off pieces outside the daily news post, where we read something people are being told to do and check
it against the original pages (20 Nov 2026, Pavan: "go ahead with your recommendations"; the first one is the Claude
plugins a viral carousel says to install).

Each lives in content/checks/<name>.json, written by hand from a draft Pavan approved, with its facts re-read on the
sources the day it was checked. The site gives it a page at /checks/<slug>/ and draws its carousel slides next to it
(checks/<slug>/NN.jpg). The social queue for its date carries it as an Instagram carousel at `post_at` (India time).
Text may use **bold**, `code` and [S1] citations, which link to the piece's own source list."""
from __future__ import annotations

import html
import json
import re
from pathlib import Path

from markupsafe import Markup

FIELDS = ("slug", "date", "headline", "dek", "blocks", "sources", "slides", "caption", "post_at")


def load_checks(content_dir: Path) -> list[dict]:
    """Every check, newest first. A file missing a field is an error: a half-written piece must never go out."""
    out = []
    for f in sorted((content_dir / "checks").glob("*.json")):
        c = json.loads(f.read_text(encoding="utf-8"))
        missing = [k for k in FIELDS if not c.get(k)]
        if missing:
            raise ValueError(f"{f.name}: missing {', '.join(missing)}")
        ids = {s["id"] for s in c["sources"]}
        cited = set(re.findall(r"\[(S\d+)\]", json.dumps(c["blocks"])))
        if cited - ids:
            raise ValueError(f"{f.name}: cites {', '.join(sorted(cited - ids))} with no source")
        out.append(c)
    return sorted(out, key=lambda c: c["date"], reverse=True)


def inline(text: str) -> Markup:
    """**bold**, `code` and [S1] citations, on escaped text."""
    t = html.escape(text, quote=False)
    t = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", t)
    t = re.sub(r"`(.+?)`", r"<code>\1</code>", t)
    t = re.sub(r"\s?\[(S(\d+))\]", r'<sup class="cite"><a href="#\1" aria-label="source \2">\2</a></sup>', t)
    return Markup(t)


def plain(text: str) -> str:
    return re.sub(r"\s?\[S\d+\]", "", text).replace("**", "").replace("`", "")


def slide_urls(base_url: str, check: dict) -> list[str]:
    return [f"{base_url}checks/{check['slug']}/{k:02d}.jpg" for k in range(1, len(check["slides"]) + 1)]


def queue_items(content_dir: Path, date: str, site: dict) -> list[dict]:
    """Instagram carousel items for the checks dated `date`, queued already approved (Pavan approved each piece
    before it was written into content/checks)."""
    from .social_queue import slot_utc
    items = []
    for c in load_checks(content_dir):
        if c["date"] != date:
            continue
        items.append({"id": f"{date}-check-{c['slug']}", "platform": "instagram", "kind": "carousel", "posting": "api",
                      "note": f"A check, not the daily post: {site['base_url']}checks/{c['slug']}/",
                      "slides": True, "text": c["caption"], "edited_text": None, "status": "approved",
                      "decided_at": None, "posted_url": None, "media": slide_urls(site["base_url"], c),
                      "scheduled_at": slot_utc(date, c["post_at"])})
    return items


# ---------------------------------------------------------------- slides

def slides(out_dir: Path, check: dict, site: dict) -> list[Path]:
    """The carousel, drawn with the daily carousel's own pieces (fma/carousel.py) so it looks like the same page."""
    from .carousel import H, M, THEMES, W, canvas, fit, footer, grain, mark, marker_underline, tag
    from .visuals import _font

    out_dir.mkdir(parents=True, exist_ok=True)
    total = len(check["slides"])
    domain = re.sub(r"^https?://|/$", "", site["base_url"])
    paths = []
    for n, s in enumerate(check["slides"]):
        theme = "night" if n % 2 == 0 else "paper"
        T = THEMES[theme]
        img, d = canvas(theme, glow=(139, 156, 255) if theme == "night" else (255, 184, 107),
                        corner="top-right" if n % 2 == 0 else "bottom-left", seed=n)
        mark(d, M + 26, 118, 26, T["accent"])
        d.text((M + 70, 100), site["name"].upper(), font=_font("sans_bold", 30), fill=T["accent"])
        if s["kind"] == "cover":
            d.text((M, 260), "WE CHECKED", font=_font("sans_bold", 32), fill=T["muted"])
            f, size, lines = fit(d, s["text"], "serif", (112, 104, 96, 88, 80), W - 2 * M, 6)
            y = 330
            for ln in lines:
                d.text((M, y), ln, font=f, fill=T["ink"])
                y += int(size * 1.06)
            marker_underline(d, M - 6, M + min(d.textlength(lines[-1], font=f), W - 2 * M) + 6, y + 8, T["accent"], seed=3)
            d.text((M, y + 80), "What the slides didn't say, from the GitHub pages", font=_font("sans", 36), fill=T["ink2"])
            d.text((M, H - 120), "Swipe", font=_font("sans_bold", 40), fill=T["accent"])
            ax = M + d.textlength("Swipe", font=_font("sans_bold", 40)) + 22
            d.line([ax, H - 96, ax + 70, H - 96], fill=T["accent"], width=5)
            d.polygon([(ax + 70, H - 108), (ax + 92, H - 96), (ax + 70, H - 84)], fill=T["accent"])
        elif s["kind"] == "checks":
            f = _font("serif", 96)
            d.text((M, 250), s["text"], font=f, fill=T["ink"])
            marker_underline(d, M - 4, M + d.textlength(s["text"], font=f), 370, T["accent"], seed=7)
            y = 440
            for it in s["items"]:
                d.rounded_rectangle([M, y + 6, M + 46, y + 52], radius=10, outline=T["accent"], width=5)
                d.text((M + 76, y), it, font=_font("sans_bold", 54), fill=T["ink"])
                y += 92
            d.text((M, y + 40), f"Every claim sourced at {domain}", font=_font("sans", 36), fill=T["ink2"])
            d.text((M, y + 92), "Link in bio", font=_font("sans_bold", 40), fill=T["accent"])
        else:
            if s.get("label"):
                tag(img, s["label"].upper(), T["accent"], (M - 4, 220), theme, angle=-4 if n % 2 else 3)
                from PIL import ImageDraw
                d = ImageDraw.Draw(img)
            f, size, lines = fit(d, s["text"], "serif", (104, 96, 88, 80, 72), W - 2 * M, 7)
            y = max(330, int((H - len(lines) * size * 1.08) / 2) - 30)        # centred, below the tag
            for ln in lines:
                d.text((M, y), ln, font=f, fill=T["ink"])
                y += int(size * 1.08)
            if s.get("source"):
                d.text((M, H - 112), f"Source: {s['source']}", font=_font("sans", 27), fill=T["muted"])
        footer(d, theme, n, total)
        paths.append(out_dir / f"{n + 1:02d}.jpg")
        grain(img, seed=40 + n).convert("RGB").save(paths[-1], "JPEG", quality=92, subsampling=0, optimize=True,
                                                     progressive=True)
    return paths
