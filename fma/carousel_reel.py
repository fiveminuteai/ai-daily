"""The daily carousel, made with the Reels' rules (22 Nov 2026).

Pavan: the carousel "is lousy, content is repeated and it looks cheap as if there is no content left to publish.
Apply same rules of reels to carousel too." The old slides (fma/carousel.py) put the headline on the cover, the same
headline again on slide 2, and each story as its title plus its first sentence, in long newspaper lines.

The rules the Reels already follow, applied here in code:
- a hook first: the cover leads with the lead card's short cover line (fact-checked like the hook), not the headline;
- one idea per slide in big plain words: a short line with its key words lit up and at most two short points;
- nothing said twice: no line, point or joke appears on two slides, and a point that only restates its slide's
  title is left out;
- the cast: Spark and the day's guest, with the guest's own (code-checked) reactions in speech bubbles;
- one question at the end (the lead card's), then the follow line.
Every word comes from the checked post: card cover lines, hooks, points and questions passed both fact-check layers,
and the guest's lines state no facts. Drawn by Remotion (reels/src/Slide.tsx); if that fails, the old slides are used.
"""
from __future__ import annotations

import json
import logging
import re
import shutil
import subprocess
import uuid
from pathlib import Path

from .social import plain

log = logging.getLogger(__name__)
SHORT_WORDS = 12          # a slide title longer than this reads as a paragraph
POINT_WORDS = 20          # Reel lines are 8-15 words; a carousel point may run a little longer
CAT = {"models": "MODELS", "architecture": "ARCHITECTURE", "research": "RESEARCH", "products": "PRODUCTS",
       "tools": "TOOLS", "policy": "POLICY", "impact": "IMPACT"}


def clean(text: str) -> str:
    return re.sub(r"\s*\[S\d+\]", "", plain(text or "")).strip()


def _key(s: str) -> set[str]:
    small = {"a", "an", "the", "is", "of", "to", "and", "in", "on", "for", "its", "it", "with", "at", "by"}
    return {w for w in re.findall(r"[a-z0-9$%.]+", s.lower()) if w not in small}


def repeats(s: str, said: list[str], share: float = 0.6) -> bool:
    """True when `s` mostly says what one of `said` already says (60% of its words)."""
    k = _key(s)
    return bool(k) and any(len(k & _key(x)) / len(k) >= share for x in said)


def words(s: str) -> int:
    return len(s.split())


def short_line(sec: dict, said: list[str]) -> tuple[str, str]:
    """The slide's big line and its lit-up words: the card's cover line, its title or its hook, whichever is short
    and not said already."""
    card = sec.get("card") or {}
    hi = (card.get("cover_hi") or "").strip()
    for cand, lit in ((card.get("cover"), hi), (sec.get("title"), ""), (card.get("hook"), "")):
        c = clean(cand or "").rstrip(".")
        if c and words(c) <= SHORT_WORDS and not repeats(c, said):
            return c, (lit if lit and lit.lower() in c.lower() else "")
    for cand in (card.get("hook"), *(card.get("points") or [])):     # longer, but not said yet
        c = clean(cand or "").rstrip(".")
        if c and words(c) <= 20 and not repeats(c, said):
            return c, ""
    c = clean(sec.get("title") or card.get("hook") or "").rstrip(".")
    return c, ""


def points(sec: dict, title: str, said: list[str], n: int = 2) -> list[str]:
    card = sec.get("card") or {}
    cands = [*(card.get("points") or []), card.get("hook") or ""]
    if not card:
        from .verify import split_sentences
        cands += [s for p in sec.get("paragraphs", [])[:1] for s in split_sentences(p)]
    out = []
    for c in map(clean, cands):
        if c and words(c) <= POINT_WORDS and not repeats(c, [title, *said, *out]):
            out.append(c if c.endswith((".", "?", "!")) else c + ".")
        if len(out) == n:
            break
    return out


def guest_lines(sec: dict) -> list[str]:
    duo = (sec.get("card") or {}).get("duo") or {}
    return [clean(ln["text"]) for ln in duo.get("lines", []) if ln.get("who") == "guest"]


def pick_bubble(sec: dict, said: list[str], max_chars: int = 64) -> str | None:
    lines = [g for g in guest_lines(sec) if len(g) <= max_chars and not repeats(g, said, 0.5)]
    return lines[-1] if lines else None


def key_number(title: str, pts: list[str]) -> str:
    """The story's key number, shown big as the Reels pop each number (money, scale or percentage only; a year or a
    plain count is not a headline number). Empty when the title or points have none."""
    from .carousel import key_figure, short_figure
    for s in (title, *pts):
        f = key_figure(s)
        if f and re.search(r"[$%€£]|(?:million|billion|trillion)", f, re.I):
            return short_figure(f)
    return ""


def build_slides(post: dict, site: dict, date_label: str) -> list[dict]:
    """The slides' props, cover to close. Raises ValueError when the post has no story to show."""
    secs = [s for s in post.get("sections", []) if s.get("title")]
    if not secs:
        raise ValueError("no stories")
    total = len(secs) + 2
    lead = secs[0]
    lead_card = lead.get("card") or {}
    guest = ((lead_card.get("duo") or {}).get("guest")) or "solo"
    said: list[str] = []

    title, hi = short_line(lead, said)
    said.append(title)
    others = []
    for s in secs[1:]:
        t, _ = short_line(s, said + others)
        others.append(t)
    bubble = pick_bubble(lead, said)
    if bubble:
        said.append(bubble)
    weekday = date_label.split(" ")[0].upper() if date_label else ""
    slides = [{"kind": "cover", "n": 1, "total": total, "title": title, "hi": hi, "points": [], "label": "",
               "kicker": f"{weekday} · {len(secs)} AI STORIES".strip(" ·"), "bubble": bubble, "guest": guest,
               "source": "", "others": [o if words(o) <= 9 else " ".join(o.split()[:9]) + "…" for o in others[:4]]}]

    from .carousel import publishers
    for k, s in enumerate(secs):
        # the lead's slide may not repeat the cover: its short line is chosen with the cover already said
        t, h = short_line(s, said) if k == 0 else (others[k - 1], (s.get("card") or {}).get("cover_hi") or "")
        h = h if h and h.lower() in t.lower() else ""
        said.append(t)
        pts = points(s, t, said)
        said += pts
        b = pick_bubble(s, said)
        if b:
            said.append(b)
        g = ((s.get("card") or {}).get("duo") or {}).get("guest") or "solo"
        src = publishers(post, s)
        fig = key_number(t, pts)
        slides.append({"kind": "story", "n": k + 2, "total": total, "title": t, "hi": h, "points": pts, "fig": fig,
                       "label": CAT.get(s.get("category", ""), ""), "kicker": f"{k + 1:02d} / {len(secs):02d}",
                       "bubble": b, "guest": g, "source": f"Source: {src}" if src else "", "others": []})

    ask = next((clean(c.get("ask")) for c in [lead_card, *[(s.get("card") or {}) for s in secs[1:]]]
                if c.get("ask")), "")
    ask = ask or "Which story surprised you most?"
    domain = re.sub(r"^https?://|/$", "", site.get("base_url", ""))
    slides.append({"kind": "close", "n": total, "total": total, "title": ask, "hi": "", "label": "",
                   "points": ["Follow @fiveminute_ai for tomorrow's five", f"Every claim checked against its source · {domain}"],
                   "kicker": "FIVE MINUTE AI", "bubble": None, "guest": guest, "source": "", "others": []})
    return slides


def render(out_dir: Path, slides: list[dict]) -> list[Path]:
    """Draw the slides with Remotion in one render (frame k = slide k) and save 01.jpg, 02.jpg, ... Raises on failure."""
    from PIL import Image
    from .duo_reel import REELS, remotion_ready
    if not remotion_ready():
        raise RuntimeError("Remotion is not installed")
    job = REELS / "public" / "jobs" / uuid.uuid4().hex[:10]
    job.mkdir(parents=True)
    try:
        (job / "props.json").write_text(json.dumps({"slides": slides}, ensure_ascii=False), encoding="utf-8")
        frames = job / "frames"
        r = subprocess.run([shutil.which("npx"), "remotion", "render", "src/index.ts", "Carousel", str(frames.resolve()),
                            "--sequence", "--image-format=png", f"--props={job / 'props.json'}", "--log=error"],
                           cwd=REELS, capture_output=True, text=True, timeout=600)
        pngs = sorted(frames.glob("*.png")) if frames.exists() else []
        if r.returncode != 0 or len(pngs) != len(slides):
            raise RuntimeError(f"remotion render failed ({len(pngs)} of {len(slides)}): {(r.stderr or r.stdout)[-500:]}")
        out_dir.mkdir(parents=True, exist_ok=True)
        paths = []
        for k, png in enumerate(pngs, 1):
            # JPEG: Instagram's publishing API takes only JPEG
            paths.append(out_dir / f"{k:02d}.jpg")
            Image.open(png).convert("RGB").save(paths[-1], "JPEG", quality=92, subsampling=0, optimize=True, progressive=True)
        return paths
    finally:
        shutil.rmtree(job, ignore_errors=True)
