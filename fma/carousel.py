"""Instagram carousel for each day's post, 1080x1350 slides (Instagram's tallest feed size).

Design rules, from a critique that the first version "looked AI-generated":
- one idea per slide, about 25 words at most; the full story stays on the site;
- the cover leads with the day's headline as a hook, not a list;
- each story picks the layout that suits it (chart, quote, big number, statement), and slides alternate between
  night and paper themes, so no two neighbours look alike;
- small hand-made touches: film grain, a marker underline or circle, a slightly tilted tag.
Everything shown comes from the checked post, so a slide never says more than the post does."""
from __future__ import annotations

import math
import random
import re
from pathlib import Path

from .social import plain
from .verify import split_sentences
from .visuals import TOPIC_RGB, _font

W, H, M = 1080, 1350, 92
CAT_NAMES = {"models": "Models", "architecture": "Architecture", "research": "Research", "products": "Products",
             "tools": "Tools", "policy": "Policy", "impact": "Impact"}
# the site's light-theme topic colours, for paper slides
TOPIC_DARK = {"models": (74, 85, 208), "architecture": (125, 94, 0), "research": (11, 127, 119), "products": (182, 83, 7),
              "tools": (130, 54, 187), "policy": (201, 42, 85), "impact": (35, 128, 63)}
THEMES = {
    "night": {"bg": (11, 16, 34), "ink": (237, 240, 250), "ink2": (195, 202, 226), "muted": (149, 160, 196),
              "line": (40, 52, 92), "accent": (255, 184, 107), "dot": (28, 36, 66), "topic": TOPIC_RGB},
    "paper": {"bg": (243, 238, 228), "ink": (14, 20, 48), "ink2": (57, 65, 94), "muted": (104, 110, 134),
              "line": (214, 205, 188), "accent": (182, 83, 7), "dot": (226, 219, 204), "topic": TOPIC_DARK},
}


# ---------------------------------------------------------------- drawing helpers

def canvas(theme: str, glow=None, corner: str = "top-right", seed: int = 0):
    from PIL import Image, ImageDraw, ImageFilter

    th = THEMES[theme]
    img = Image.new("RGB", (W, H), th["bg"])
    if glow:
        layer = Image.new("RGB", (W, H), th["bg"])
        cx, cy = {"top-right": (W - 100, 80), "bottom-left": (120, H - 120), "centre": (W // 2, H // 2)}[corner]
        k = (0.26 if glow[2] > 150 else 0.16) if theme == "night" else 0.10
        ImageDraw.Draw(layer).ellipse([cx - 560, cy - 460, cx + 560, cy + 460],
                                      fill=tuple(int(th["bg"][j] + (glow[j] - th["bg"][j]) * k) for j in range(3)))
        img = Image.blend(img, layer.filter(ImageFilter.GaussianBlur(170)), 1.0)
    d = ImageDraw.Draw(img)
    for x in range(40, W, 40):
        for y in range(40, H, 40):
            d.point((x, y), fill=th["dot"])
    return img, d


def grain(img, amount: int = 9, seed: int = 0):
    """Fine monochrome film grain: breaks up flat digital gradients."""
    import numpy as np
    from PIL import Image

    rng = np.random.default_rng(seed)
    a = np.asarray(img).astype(np.int16)
    noise = rng.normal(0, amount, a.shape[:2])[..., None]
    return Image.fromarray(np.clip(a + noise, 0, 255).astype(np.uint8))


def wrap(d, text: str, font, max_w: float) -> list[str]:
    words = re.sub(r"(\d) (?=\S)", "\\1\u00a0", text).split(" ")      # keep "29 October" together
    lines, cur = [], ""
    for word in words:
        trial = f"{cur} {word}".strip()
        if d.textlength(trial.replace("\u00a0", " "), font=font) <= max_w or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = word
    return [ln.replace("\u00a0", " ") for ln in lines + ([cur] if cur else [])]


def balanced(d, text: str, font, max_w: float) -> list[str]:
    """Wrap, narrowing the measure if the last line would be one lonely word."""
    for k in (1.0, .94, .88, .82, .76, .70):
        lines = wrap(d, text, font, max_w * k)
        if not (len(lines) > 1 and " " not in lines[-1]):
            return lines
    return wrap(d, text, font, max_w)


def fit(d, text: str, kind: str, sizes, max_w: float, max_lines: int):
    for s in sizes:
        f = _font(kind, s)
        lines = balanced(d, text, f, max_w)
        if len(lines) <= max_lines and max(d.textlength(ln, font=f) for ln in lines) <= max_w:
            return f, s, lines
    return f, s, lines


def marker_underline(d, x0, x1, y, colour, seed=0, width=14):
    """A hand-drawn highlighter stroke: slightly wavy, thicker in the middle, ragged ends."""
    rnd = random.Random(seed)
    pts = []
    n = 28
    for i in range(n + 1):
        t = i / n
        x = x0 + (x1 - x0) * t
        pts.append((x, y + math.sin(t * math.pi * 1.3 + rnd.random()) * 3 + rnd.uniform(-1.2, 1.2) - t * 4))
    for i in range(n):
        t = i / n
        w = width * (0.65 + 0.35 * math.sin(t * math.pi))
        d.line([pts[i], pts[i + 1]], fill=colour, width=int(w))


def marker_circle(d, box, colour, seed=0, width=7):
    """A loose hand-drawn loop around something, overshooting where it closes."""
    rnd = random.Random(seed)
    x0, y0, x1, y1 = box
    cx, cy, rx, ry = (x0 + x1) / 2, (y0 + y1) / 2, (x1 - x0) / 2 + 26, (y1 - y0) / 2 + 22
    pts = []
    start = rnd.uniform(-2.6, -2.2)
    for i in range(64):
        a = start + i / 60 * 2 * math.pi * 1.06
        wob = 1 + 0.03 * math.sin(a * 3 + rnd.random())
        pts.append((cx + rx * wob * math.cos(a), cy + ry * wob * math.sin(a) + i * 0.25))
    for i in range(len(pts) - 1):
        d.line([pts[i], pts[i + 1]], fill=colour, width=width)


def tag(img, text: str, colour, at, theme: str, angle: float = -4.0):
    """A small rounded label, rotated a few degrees as if stuck on by hand."""
    from PIL import Image, ImageDraw

    f = _font("sans_bold", 28)
    probe = ImageDraw.Draw(img)
    w = int(probe.textlength(text, font=f)) + 52
    lab = Image.new("RGBA", (w, 60), (0, 0, 0, 0))
    ld = ImageDraw.Draw(lab)
    ld.rounded_rectangle([0, 0, w - 1, 59], radius=30, fill=colour + (255,))
    ld.text((26, 12), text, font=f, fill=THEMES[theme]["bg"])
    lab = lab.rotate(angle, expand=True, resample=Image.BICUBIC)
    img.paste(lab, at, lab)


def mark(d, cx, cy, r, colour):
    d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=colour, width=max(3, r // 6))
    d.pieslice([cx - r + 3, cy - r + 3, cx + r - 3, cy + r - 3], start=-90, end=-30, fill=colour)


def footer(d, theme: str, n: int, total: int, source: str = ""):
    th = THEMES[theme]
    if source:
        d.text((M, H - 112), f"Source: {source}", font=_font("sans", 27), fill=th["muted"])
    gap, r = 24, 6
    x0 = W - M - (total - 1) * gap
    for k in range(total):
        d.ellipse([x0 + k * gap - r, H - 98 - r, x0 + k * gap + r, H - 98 + r],
                  fill=th["accent"] if k == n else th["line"])


# ---------------------------------------------------------------- content helpers

UNIT_RANK = {"trillion": 4, "billion": 3, "million": 2}
FIGURE_RE = re.compile(r"(\$?\d+(?:[.,]\d+)?)[\s-](trillion|billion|million)\b|(\$\d+(?:[.,]\d+)?)|(\d+(?:\.\d+)?)\s?(%|percent)\b")


def key_figure(text: str) -> str:
    """The biggest money or scale figure in the text; dates and plain counts are skipped."""
    best, rank = "", 0
    for m in FIGURE_RE.finditer(text):
        if m.group(2):
            fig, r = f"{m.group(1)} {m.group(2)}", UNIT_RANK[m.group(2)]
        elif m.group(3):
            fig, r = m.group(3), 1
        else:
            fig, r = f"{m.group(4)}%", 1
        if r > rank:
            best, rank = fig, r
    return best


def short_figure(fig: str) -> str:
    """"$7.6 billion" -> "$7.6B", for the giant number; the caption keeps the full words."""
    return re.sub(r"\s?(trillion|billion|million)$", lambda m: {"trillion": "T", "billion": "B", "million": "M"}[m.group(1)], fig)


def one_line(section: dict, max_words: int = 34) -> str:
    """The first sentence of the story short enough for one slide; failing that, the shortest of the first three."""
    sents = [plain(s) for s in split_sentences(section["paragraphs"][0])][:3]
    for s in sents:
        if len(s.split()) <= max_words:
            return s
    return min(sents, key=lambda s: len(s.split())) if sents else ""


def publishers(post: dict, section: dict) -> str:
    ids = list(dict.fromkeys(i for p in section["paragraphs"] for i in re.findall(r"S\d+", p)))
    by_id = {s["id"]: re.sub(r"\s*\(via .*\)$", "", s.get("publisher") or "") for s in post["sources"]}
    return ", ".join(list(dict.fromkeys(by_id[i] for i in ids if by_id.get(i)))[:2])


def plan(post: dict) -> list[dict]:
    """Choose a layout for each story: its chart, its quote, a big number, or a plain statement."""
    out, used = [], set()
    for s in post["sections"]:
        ids = {i for p in s["paragraphs"] for i in re.findall(r"S\d+", p)}
        line = one_line(s)
        chart, quote = post.get("chart"), post.get("quote")
        if chart and chart.get("source") in ids and "chart" not in used and len(chart.get("bars", [])) >= 2:
            kind = "chart"
        elif quote and quote.get("source") in ids and "quote" not in used:
            kind = "quote"
        elif key_figure(line):
            kind = "number"
        else:
            kind = "statement"
        used.add(kind)
        out.append({"section": s, "kind": kind, "line": line})
    return out


# ---------------------------------------------------------------- slides

def slide_cover(post, site, date_label, total, cols):
    th = "night"
    img, d = canvas(th, glow=(139, 156, 255), corner="top-right")
    T = THEMES[th]
    seg = W / len(cols)
    for n, c in enumerate(cols):
        d.rectangle([int(n * seg), 0, int((n + 1) * seg), 12], fill=c)
    mark(d, M + 26, 118, 26, T["accent"])
    d.text((M + 70, 100), site["name"].upper(), font=_font("sans_bold", 30), fill=T["accent"])
    d.text((W - M - d.textlength(date_label, font=_font("sans", 30)), 102), date_label, font=_font("sans", 30), fill=T["muted"])
    d.text((M, 250), "TODAY'S BIG ONE", font=_font("sans_bold", 30), fill=T["muted"])
    head = plain(post["headline"])
    f, s, lines = fit(d, head, "serif", (118, 108, 100, 92, 84, 76), W - 2 * M, 5)
    y = 310
    for line in lines:
        d.text((M, y), line, font=f, fill=T["ink"])
        y += int(s * 1.04)
    # marker stroke under the last line
    last_w = d.textlength(lines[-1], font=f)
    marker_underline(d, M - 6, M + min(last_w, W - 2 * M) + 6, y + 8, T["accent"], seed=1)
    y += 90
    d.text((M, y), f"+ {len(post['sections']) - 1} more stories, every claim sourced", font=_font("sans", 36), fill=T["ink2"])
    # small numbered strip of the other stories
    y += 80
    rows = max(0, min(3, int((H - 200 - y) // 56)))
    for n, sec in enumerate(post["sections"][1:1 + rows], 2):
        t = plain(sec["title"])
        ff = _font("sans_bold", 32)
        while d.textlength(t, font=ff) > W - 2 * M - 70 and " " in t:
            t = t.rsplit(" ", 1)[0].rstrip(",;:") + "…"
        d.text((M, y), f"{n:02d}", font=_font("sans_bold", 30), fill=cols[n - 1])
        d.text((M + 70, y - 1), t, font=ff, fill=T["ink2"])
        y += 56
    d.text((M, H - 120), "Swipe", font=_font("sans_bold", 40), fill=T["accent"])
    ax = M + d.textlength("Swipe", font=_font("sans_bold", 40)) + 22
    d.line([ax, H - 96, ax + 70, H - 96], fill=T["accent"], width=5)
    d.polygon([(ax + 70, H - 108), (ax + 92, H - 96), (ax + 70, H - 84)], fill=T["accent"])
    return grain(img, seed=11)


def slide_story(post, item, n, total, theme):
    s, kind, line = item["section"], item["kind"], item["line"]
    cat = s.get("category", "")
    T = THEMES[theme]
    c = T["topic"].get(cat, T["accent"])
    img, d = canvas(theme, glow=c, corner="top-right" if n % 2 else "bottom-left", seed=n)
    d.text((M, 96), f"{n - 1:02d}", font=_font("serif", 64), fill=c)
    tag(img, CAT_NAMES.get(cat, cat.title()).upper(), c, (W - M - 230, 92), theme, angle=(-4 if n % 2 else 3))
    from PIL import Image, ImageDraw
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    title = plain(s["title"])
    src = publishers(post, s)

    if kind == "number":
        fig = key_figure(line)
        big = short_figure(fig)
        bf, bs, _ = fit(d, big, "serif", (300, 270, 240, 210, 180), W - 2 * M, 1)
        y = 0
        d.text((M - 8, y), big, font=bf, fill=c)
        bw = d.textlength(big, font=bf)
        marker_circle(d, (M - 8, y + bs * 0.2, M - 8 + bw, y + bs * 1.02), T["ink"] if theme == "paper" else T["accent"], seed=n)
        y += int(bs * 1.25)
        tf, ts, tl = fit(d, title, "serif", (72, 66, 60, 54), W - 2 * M, 3)
        for ln in tl:
            d.text((M, y), ln, font=tf, fill=T["ink"])
            y += int(ts * 1.06)
        y += 30
        lf, ls, ll = fit(d, line, "sans", (40, 38, 36, 34), W - 2 * M, 5)
        for ln in ll:
            d.text((M, y), ln, font=lf, fill=T["ink2"])
            y += int(ls * 1.4)

    elif kind == "quote":
        q = post["quote"]
        d.text((M - 10, -60), "\u201c", font=_font("serif", 320), fill=c)
        qt = plain(q["text"]).rstrip(".")
        qt = "\u2026" + qt if qt[:1].islower() else qt          # a fragment says so
        qf, qs, ql = fit(d, qt, "serif", (104, 96, 88, 80, 72, 64), W - 2 * M, 5)
        y = 150
        for ln in ql:
            d.text((M, y), ln, font=qf, fill=T["ink"])
            y += int(qs * 1.1)
        y += 34
        marker_underline(d, M, M + 150, y, c, seed=n, width=10)
        y += 50
        d.text((M, y), f"\u2014 {plain(q['speaker'])}", font=_font("sans_bold", 38), fill=T["ink2"])
        y += 80
        tf, ts, tl = fit(d, title, "sans", (38, 36, 34), W - 2 * M, 2)
        for ln in tl:
            d.text((M, y), ln, font=tf, fill=T["muted"])
            y += int(ts * 1.35)

    elif kind == "chart":
        ch = post["chart"]
        tf, ts, tl = fit(d, title, "serif", (84, 76, 70, 64), W - 2 * M, 3)
        y = 0
        for ln in tl:
            d.text((M, y), ln, font=tf, fill=T["ink"])
            y += int(ts * 1.06)
        y += 40
        bars = ch["bars"][:4]
        top = max(b["value"] for b in bars) or 1
        unit = ch.get("unit", "")
        prefix = "$" if unit.startswith("$") else ""
        suffix = "B" if "billion" in unit else ("M" if "million" in unit else ("T" if "trillion" in unit else ""))
        bar_h, gap = 116, 54
        for k, b in enumerate(bars):
            w = int((W - 2 * M - 40) * b["value"] / top)
            col = c if k == 0 else T["line"]
            d.rounded_rectangle([M, y, M + max(w, 24), y + bar_h], radius=18, fill=col)
            val = f"{prefix}{b['value']:g}{suffix}"
            vf = _font("serif", 64)
            vcol = T["bg"] if k == 0 else T["ink"]
            d.text((M + 30, y + 22), val, font=vf, fill=vcol)
            d.text((M, y + bar_h + 10), plain(b["label"]), font=_font("sans", 32), fill=T["ink2"])
            y += bar_h + gap + 30
        y += 10
        lf, ls, ll = fit(d, line, "sans", (36, 34, 32), W - 2 * M, 4)
        for ln in ll:
            d.text((M, y), ln, font=lf, fill=T["ink2"])
            y += int(ls * 1.4)

    else:   # statement
        tf, ts, tl = fit(d, title, "serif", (128, 116, 106, 96, 88, 80), W - 2 * M, 4)
        y = 0
        for ln in tl:
            d.text((M, y), ln, font=tf, fill=T["ink"])
            y += int(ts * 1.03)
        marker_underline(d, M - 4, M + min(d.textlength(tl[-1], font=tf), W - 2 * M), y + 6, c, seed=n)
        y += 90
        lf, ls, ll = fit(d, line, "sans", (44, 42, 40, 38, 36), W - 2 * M, 6)
        for ln in ll:
            d.text((M, y), ln, font=lf, fill=T["ink2"])
            y += int(ls * 1.42)

    # centre the block between the header (ends ~200) and the footer (starts ~1200), a little above middle
    box = layer.getbbox()
    if box:
        block = layer.crop((0, box[1], W, box[3]))
        top, room = 215, 1190 - 215
        img.paste(block, (0, top + max(0, int((room - block.height) * 0.42))), block)
    footer(ImageDraw.Draw(img), theme, n - 1, total, src)
    return grain(img, amount=9 if theme == "night" else 6, seed=n)


def slide_close(site, total, cols):
    th = "night"
    img, d = canvas(th, glow=(255, 184, 107), corner="bottom-left")
    T = THEMES[th]
    mark(d, M + 60, 210, 60, T["accent"])
    f = _font("serif", 104)
    y = 360
    for ln in ("Every claim", "checked against", "its source."):
        d.text((M, y), ln, font=f, fill=T["ink"])
        y += 108
    marker_underline(d, M - 4, M + d.textlength("its source.", font=f), y + 4, T["accent"], seed=9)
    y += 90
    for ln in ("A second model fact-checks every sentence,", "and the full check log is public."):
        d.text((M, y), ln, font=_font("sans", 38), fill=T["ink2"])
        y += 54
    y += 60
    d.text((M, y), "Full five-minute read: link in bio", font=_font("sans_bold", 44), fill=T["accent"])
    y += 66
    d.text((M, y), re.sub(r"^https?://|/$", "", site["base_url"]), font=_font("sans", 36), fill=T["muted"])
    d.rounded_rectangle([M, H - 210, M + 560, H - 130], radius=40, fill=T["accent"])
    d.text((M + 40, H - 192), "Follow for tomorrow's five", font=_font("sans_bold", 38), fill=T["bg"])
    footer(d, th, total - 1, total)
    return grain(img, seed=99)


def carousel(out_dir: Path, post: dict, site: dict, date_label: str) -> list[Path]:
    """Render cover, one slide per story and a closing slide into out_dir as 01.jpg, 02.jpg, ..."""
    out_dir.mkdir(parents=True, exist_ok=True)
    items = plan(post)
    total = len(items) + 2
    cols = [TOPIC_RGB.get(s.get("category"), (255, 184, 107)) for s in post["sections"]]
    slides = [slide_cover(post, site, date_label, total, cols)]
    for n, item in enumerate(items, 2):
        slides.append(slide_story(post, item, n, total, "paper" if n % 2 == 0 else "night"))
    slides.append(slide_close(site, total, cols))
    paths = []
    for k, im in enumerate(slides, 1):
        # JPEG: Instagram's publishing API takes only JPEG, and grain makes PNGs four times the size
        paths.append(out_dir / f"{k:02d}.jpg")
        im.convert("RGB").save(paths[-1], "JPEG", quality=92, subsampling=0, optimize=True, progressive=True)
    return paths
