"""One Reel per story, 1080x1920, about 25 seconds, built only from the story's fact-checked card
(hook, takeaways, "our read" or "do this"), with the original music from music.py.

Structure, on the music's bar grid (100 BPM, one bar = 2.4 s):
  bars 1-2   story number, topic and the hook, word by word; a money or scale figure counts up above it
  2 bars each  the takeaways, one at a time; numbers and names drawn in the topic colour
  bars +2    "Our read" or "Do this"
  last bar   end card: full story in bio, follow
The source names stay on screen throughout. Text sits inside Instagram's safe band (clear of the caption and the
buttons on the right). Needs ffmpeg on the PATH, like reel.py."""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from .carousel import CAT_NAMES, THEMES, key_figure, mark, marker_underline, publishers, short_figure, wrap
from .music import BAR, BEAT, write_wav
from .reel import FPS, H, M, W, _count, background, ease
from . import sketch
from .social import plain
from .visuals import _font

TEXT_W = W - 2 * M - 60            # keep clear of Instagram's like/comment/share column
EMPH_RE = re.compile(r"\d")      # numbers and money get the topic colour; highlighting words like "AI" reads random
MID_TOP, MID_BOTTOM = 570, 930     # text is centred in this band; the doodle sits below it
DOODLE = 420                       # doodle box size; centred in the text column between the text and the source line
DOODLE_Y = 955
SOURCE_Y = 1405


# Looks for the story Reels. "cutout" is the house look (Pavan's choice, 1 Nov 2026); "doodle" keeps the site's
# night/paper themes; the others bring their own.
DEFAULT_STYLE = "cutout"
STYLE_THEMES = {
    "chalk": {"bg": (31, 49, 42), "ink": (238, 236, 226), "ink2": (210, 214, 200), "muted": (165, 182, 168),
              "line": (66, 90, 78), "accent": (246, 214, 110), "dot": (40, 60, 52), "c": (246, 214, 110),
              "hi": (255, 158, 140), "font": "serif"},
    "cutout": {"bg": (245, 237, 222), "ink": (30, 35, 60), "ink2": (60, 64, 88), "muted": (112, 106, 96),
               "line": (222, 210, 190), "accent": (240, 110, 80), "dot": (232, 222, 204), "c": (240, 110, 80),
               "hi": (38, 150, 140), "font": "serif"},
    "comic": {"bg": (255, 228, 112), "ink": (15, 15, 15), "ink2": (40, 40, 40), "muted": (90, 74, 30),
              "line": (232, 196, 80), "accent": (222, 38, 44), "dot": (245, 160, 60), "c": (222, 38, 44),
              "hi": (58, 186, 230), "font": "sans_bold"},
}


# Paper cut-out colour sets. Each topic has a home set, so the colour hints at the kind of story; a day's Reels never
# share a set. "fills" are the papers the drawings are cut from: never the disc colour or the highlight colour, or
# shapes vanish. Dusk is the darker set for security, law and harm stories.
PALETTES = {
    "cream": {"bg": (245, 237, 222), "ink": (30, 35, 60), "muted": (112, 106, 96), "line": (222, 210, 190),
              "c": (232, 96, 66), "hi": (38, 150, 140), "disc": (242, 190, 64),
              "fills": [(240, 110, 80), (122, 104, 220), (255, 251, 242)], "shapes": [(38, 150, 140), (242, 190, 64)]},
    "mint": {"bg": (224, 241, 232), "ink": (22, 44, 46), "muted": (92, 118, 112), "line": (196, 222, 210),
             "c": (104, 82, 214), "hi": (232, 96, 66), "disc": (255, 255, 255),
             "fills": [(38, 150, 140), (242, 190, 64), (122, 104, 220)], "shapes": [(122, 104, 220), (38, 150, 140)]},
    "sky": {"bg": (222, 234, 248), "ink": (20, 34, 72), "muted": (96, 110, 140), "line": (196, 212, 236),
            "c": (214, 72, 52), "hi": (38, 150, 140), "disc": (242, 190, 64),
            "fills": [(74, 108, 226), (255, 251, 242), (240, 110, 80)], "shapes": [(74, 108, 226), (242, 190, 64)]},
    "blush": {"bg": (250, 232, 228), "ink": (54, 26, 40), "muted": (130, 100, 108), "line": (236, 210, 206),
              "c": (22, 128, 122), "hi": (122, 104, 220), "disc": (255, 255, 255),
              "fills": [(240, 110, 80), (242, 190, 64), (38, 150, 140)], "shapes": [(240, 110, 80), (22, 128, 122)]},
    "dusk": {"bg": (34, 38, 60), "ink": (240, 236, 228), "muted": (168, 170, 192), "line": (66, 72, 100),
             "c": (255, 176, 92), "hi": (110, 214, 198), "disc": (62, 72, 122),
             "fills": [(240, 110, 80), (255, 251, 242), (242, 190, 64)], "shapes": [(110, 214, 198), (255, 176, 92)]},
}
HOME_PALETTE = {"products": "cream", "models": "sky", "architecture": "mint", "research": "mint", "tools": "blush",
                "impact": "dusk", "policy": "dusk"}


def palettes_for(stories: list[tuple[int, dict]]) -> list[str]:
    """One colour set per Reel of the day: the topic's home set, or the next unused one."""
    order, used, out = list(PALETTES), set(), []
    for _, sec in stories:
        name = HOME_PALETTE.get(sec.get("category"), "cream")
        while name in used:
            name = order[(order.index(name) + 1) % len(order)]
        used.add(name)
        out.append(name)
    return out


def _cutout_shapes(d, pal: dict, seed: int):
    """Two or three big paper shapes around the edges, different for every story (seeded), never behind the text."""
    rng = np.random.default_rng(seed)
    a, b = pal["shapes"]
    # top shapes stay in the margin above the header (y < 320); bottom ones below the source line (y > 1450)
    spots = [("tr", W - 110, 110), ("bl", 60, H - 300), ("br", W - 90, H - 230), ("tl", -20, 90)]
    picks = [spots[i] for i in rng.choice(len(spots), size=3, replace=False)]
    for k, (where, cx, cy) in enumerate(picks):
        colour = (a if k % 2 == 0 else b) + (70 if where in ("tr", "tl") else 110,)
        r = int(rng.integers(120, 180)) if where in ("tr", "tl") else int(rng.integers(170, 260))
        kind = rng.choice(["circle", "half", "square", "triangle", "pill"])
        if kind == "circle":
            d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=colour)
        elif kind == "half":
            start = {"tr": 90, "tl": 270, "bl": 270, "br": 180}[where]
            d.pieslice([cx - r, cy - r, cx + r, cy + r], start, start + 180, fill=colour)
        elif kind == "square":
            d.rounded_rectangle([cx - r * 0.8, cy - r * 0.8, cx + r * 0.8, cy + r * 0.8], radius=int(r * 0.25), fill=colour)
        elif kind == "triangle":
            d.polygon([(cx, cy - r), (cx + r, cy + r * 0.8), (cx - r, cy + r * 0.8)], fill=colour)
        else:
            d.rounded_rectangle([cx - r * 1.3, cy - r * 0.42, cx + r * 1.3, cy + r * 0.42], radius=int(r * 0.42), fill=colour)
    for _ in range(int(rng.integers(6, 12))):            # a few confetti dots
        x, y = int(rng.integers(40, W - 40)), int(rng.choice([rng.integers(130, 300), rng.integers(1480, 1860)]))
        rr = int(rng.integers(6, 14))
        d.ellipse([x - rr, y - rr, x + rr, y + rr], fill=(a if rng.random() < 0.5 else b) + (160,))


def style_background(style: str, n: int, pal: dict | None = None, seed: int = 0):
    """Backgrounds for the non-doodle looks, drawn once per Reel."""
    th = STYLE_THEMES[style]
    img = Image.new("RGB", (W, H), (pal or th)["bg"])
    d = ImageDraw.Draw(img, "RGBA")
    rng = np.random.default_rng(40 + n)
    if style == "chalk":                         # old smudges where the board was wiped
        from PIL import ImageFilter
        smudge = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        sd = ImageDraw.Draw(smudge)
        for _ in range(9):
            x, y, r = rng.integers(0, W), rng.integers(200, H - 200), rng.integers(140, 380)
            sd.ellipse([x - r, y - r * 0.5, x + r, y + r * 0.5], fill=(255, 255, 255, int(rng.integers(8, 18))))
        img.paste(smudge.filter(ImageFilter.GaussianBlur(40)), (0, 0), smudge.filter(ImageFilter.GaussianBlur(40)))
        d = ImageDraw.Draw(img, "RGBA")
        d.rectangle([0, H - 300, W, H], fill=(20, 32, 27, 255))            # the chalk tray edge
        d.rectangle([0, H - 300, W, H - 288], fill=(90, 70, 50, 255))
    elif style == "cutout":                      # paper shapes around the edges, different for every story
        _cutout_shapes(d, pal or PALETTES["cream"], seed)
        d.rectangle([0, 0, W, 10], fill=(pal or PALETTES["cream"])["c"] + (255,))
    else:                                        # comic: halftone dots, bigger toward the bottom-right corner
        for y in range(0, H, 34):
            for x in range(0, W, 34):
                k = ((x / W) * 0.5 + (y / H) * 0.8)
                r = max(0.0, (k - 0.35) * 14)
                if r > 0.6:
                    d.ellipse([x - r, y - r, x + r, y + r], fill=th["dot"] + (150,))
        d.rectangle([24, 24, W - 24, H - 24], outline=(15, 15, 15, 255), width=10)   # the panel border
    return img


CHANGE_RE = re.compile(r"\bfrom\s+(\$?[\d.,]+\s?(?:trillion|billion|million|%|percent)?)\s+to\s+"
                       r"(\$?[\d.,]+\s?(?:trillion|billion|million|%|percent)?)", re.I)


def change_in(text: str) -> tuple[str, str] | None:
    m = CHANGE_RE.search(text)
    return (short_figure(m.group(1).strip()), short_figure(m.group(2).strip())) if m else None


def change_badge(ld, box, t, before: str, after: str, ink, accent, card_bg, grow=0.35):
    """A paper card showing a change: the old figure, an arrow, the new figure counting in."""
    if t <= 0:
        return
    x, y, size = box
    k = 1 - (1 - min(1.0, t / grow)) ** 3
    w, h = size * 1.5, size * 0.62
    cx, cy = x + size / 2, y + size / 2 + (1 - k) * 80
    x0, y0 = cx - w / 2, cy - h / 2
    ld.rounded_rectangle([x0 + 12, y0 + 14, x0 + w + 12, y0 + h + 14], radius=28, fill=(0, 0, 0, int(45 * k)))
    ld.rounded_rectangle([x0, y0, x0 + w, y0 + h], radius=28, fill=card_bg + (int(255 * k),))
    f = _font("serif", int(size * 0.24))
    bw, aw = ld.textlength(before, font=f), ld.textlength(after, font=f)
    gap = size * 0.22
    total = bw + gap + aw
    bx = cx - total / 2
    ty = cy - size * 0.15
    ld.text((bx, ty), before, font=f, fill=ink + (int(150 * k),))
    ld.line([(bx - 6, ty + size * 0.15), (bx + bw + 6, ty + size * 0.12)], fill=accent + (int(220 * k),), width=7)
    axs, axe = bx + bw + gap * 0.18, bx + bw + gap * 0.82
    ld.line([(axs, ty + size * 0.14), (axe, ty + size * 0.14)], fill=ink + (int(255 * k),), width=8)
    ld.polygon([(axe + 4, ty + size * 0.14), (axe - 18, ty + size * 0.14 - 14), (axe - 18, ty + size * 0.14 + 14)],
               fill=ink + (int(255 * k),))
    pa = min(1.0, max(0.0, (t - 0.3) / 0.8))
    if pa > 0:
        ld.text((bx + bw + gap, ty), _count(after, pa), font=f, fill=accent + (255,))


def card_stories(post: dict, limit: int = 3) -> list[tuple[int, dict]]:
    """The first `limit` stories that have a complete fact-checked card, in the post's order (most important first)."""
    return [(n, s) for n, s in enumerate(post.get("sections", [])) if (s.get("card") or {}).get("hook")][:limit]


class Block:
    """A paragraph laid out once and revealed word by word; emphasised words (numbers, names) get the topic colour."""

    def __init__(self, d, text, font, size, x, y, max_w, lead=1.12):
        self.items, yy = [], y
        lines = wrap(d, text, font, max_w)
        self.height = len(lines) * int(size * lead)
        if y is None:                              # centre the block in the text band
            yy = y = max(MID_TOP, (MID_TOP + MID_BOTTOM) // 2 - self.height // 2)   # never up into the header
        self.top = y
        for line in lines:
            xx = x
            for word in line.split(" "):
                self.items.append((word, xx, yy))
                xx += d.textlength(word + " ", font=font)
            yy += int(size * lead)
        self.font, self.size, self.bottom, self.last_w = font, size, yy, (xx - x) if self.items else 0

    def first_emph(self, d):
        """Box of the first number word, for the hand-drawn ring, with the time index of that word."""
        for k, (word, x, y) in enumerate(self.items):
            core = word.strip(".,;:!?()\"'’“”")
            if EMPH_RE.search(core):
                w = d.textlength(core, font=self.font)
                return k, (x, y + self.size * 0.12, x + w, y + self.size * 0.98)
        return None

    def draw(self, ld, t, start, per_word, ink, emph):
        for k, (word, x, y) in enumerate(self.items):
            p = ease((t - start - k * per_word) / 0.22)
            if p > 0:
                core = word.strip(".,;:!?()\"'’“”")
                colour = emph if EMPH_RE.search(core) else ink
                ld.text((x, y + (1 - p) * 30), word, font=self.font, fill=colour + (int(255 * p),))


def _fit(d, text: str, kind: str, start: int, floor: int, max_lines: int, max_w: int = TEXT_W):
    size = start
    while True:
        f = _font(kind, size)
        lines = wrap(d, text, f, max_w)
        if (len(lines) <= max_lines and max(d.textlength(x, font=f) for x in lines) <= max_w) or size <= floor:
            return f, size, len(lines)
        size -= 6


def render_frames(post: dict, section: dict, n: int, site: dict, seconds: float, style: str = DEFAULT_STYLE,
                  palette: str | None = None):
    card = section["card"]
    probe = ImageDraw.Draw(Image.new("RGB", (8, 8)))
    pal = None
    if style == "doodle":
        theme = "night" if n % 2 == 0 else "paper"
        T = THEMES[theme]
        c = T["topic"].get(section.get("category"), T["accent"])
        bg = background(theme, c, "top-right" if n % 2 == 0 else "bottom-left")
        face, mode, hi = "serif", "pen", None
    else:
        T = dict(STYLE_THEMES[style])
        if style == "cutout":
            pal = PALETTES[palette or HOME_PALETTE.get(section.get("category"), "cream")]
            T.update(pal, accent=pal["c"], ink2=pal["ink"])
        theme = "night" if style == "chalk" or palette == "dusk" else "paper"
        c, face, mode, hi = T["c"], T["font"], style, T["hi"]
        bg = style_background(style, n, pal, seed=sum(map(ord, section.get("title", ""))) + n)
    grain = np.random.default_rng(11 + n).normal(0, 5, (H, W, 1)).astype(np.int16)
    source = publishers(post, section)

    hook = plain(card["hook"])
    fig = short_figure(key_figure(hook))
    hf, hs, hl = _fit(probe, hook, face, 112, 70, 4)
    hook_b = Block(probe, hook, hf, hs, M, None, TEXT_W)
    if fig:                                        # the counting figure sits above the hook; centre the pair
        shift = 120
        hook_b = Block(probe, hook, hf, hs, M, hook_b.top + shift, TEXT_W)
    points = []
    for p in card["points"]:
        pf, ps, _ = _fit(probe, plain(p), face, 88, 58, 4)
        points.append(Block(probe, plain(p), pf, ps, M, None, TEXT_W))
    take = plain(card["take"]) if card.get("take") else ""
    take_b = None
    if take:
        tf, ts, _ = _fit(probe, take, face, 86, 58, 4)
        take_b = Block(probe, take, tf, ts, M, None, TEXT_W)

    # one doodle per scene, chosen from that line's words, never the same one twice in a Reel
    used: set[str] = set()
    doodles = []
    for text in [hook, *[plain(x) for x in card["points"]], take]:
        name = sketch.pick(text, used, section.get("category", "")) if text else "spark"
        used.add(name)
        doodles.append(name)
    def box_under(block):
        y = max(DOODLE_Y, block.bottom + 30)
        size = max(220, min(DOODLE, SOURCE_Y - 25 - y))
        return (M + (TEXT_W - size) / 2, y, size)
    dbox = box_under(hook_b)
    ink = T["ink"] + (235,)
    wash = c + (120 if theme == "night" else 80,)         # strong enough on navy to read as colour, not mud
    hi_c = (hi or c) + (255,)

    def backdrop(t, seed):
        if mode == "pen":
            sketch.blob(ld, dbox, t, wash, seed=seed)
        elif mode == "cutout":
            sketch.paper(ld, dbox, t, (pal or PALETTES["cream"])["disc"] + (255,), seed=seed)
        elif mode == "comic":
            sketch.burst(ld, dbox, t, (255, 255, 255, 255), seed=seed)
        # chalk: no backdrop, the board is the backdrop          # the colour patch behind each doodle
    rings = {"hook": hook_b.first_emph(probe), **{f"p{k}": b.first_emph(probe) for k, b in enumerate(points)}}

    scenes = [(0, 2 * BAR, "hook", None)]
    t = 2 * BAR
    for k, b in enumerate(points):
        scenes.append((t, t + 2 * BAR, "point", (k, b)))
        t += 2 * BAR
    if take_b:
        scenes.append((t, t + 2 * BAR, "take", None))
        t += 2 * BAR
    scenes.append((t, seconds, "end", None))

    label = CAT_NAMES.get(section.get("category", ""), "").upper()
    for fi in range(int(seconds * FPS)):
        tt = fi / FPS
        i = next(j for j, s in enumerate(scenes) if s[0] <= tt < s[1] or j == len(scenes) - 1)
        start, _end, kind, data = scenes[i]
        lt = tt - start
        frame = bg.copy()
        layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        ld = ImageDraw.Draw(layer)

        if kind != "end":
            a = 1.0                                 # no fade-in: frame one is the cover and the first glance
            mark(ld, M + 24, 362, 24, T["accent"] + (int(255 * a),))
            ld.text((M + 64, 345), site["name"].upper(), font=_font("sans_bold", 32), fill=T["accent"] + (int(255 * a),))
            lf = _font("sans_bold", 32)
            lw = ld.textlength(label, font=lf)
            ld.rounded_rectangle([W - M - lw - 120, 334, W - M - 60, 392], radius=29, fill=c + (int(255 * a),))
            ld.text((W - M - lw - 92, 344), label, font=lf, fill=T["bg"] + (int(255 * a),))
            if source:
                ld.text((M, SOURCE_Y), f"Source: {source}", font=_font("sans", 34), fill=T["muted"] + (int(255 * a),))
            # progress: a thin topic-coloured bar under the header, so viewers see how long is left
            end_t = scenes[-1][0]
            ld.rounded_rectangle([M, 420, W - M - 60, 426], radius=3, fill=T["line"] + (int(160 * a),))
            ld.rounded_rectangle([M, 420, M + (W - 2 * M - 60) * min(1, tt / end_t), 426], radius=3, fill=c + (255,))

        if kind == "hook":
            dbox = box_under(hook_b)
            if fig:
                pf = (lt - 0.2) / (BEAT * 1.5)
                if pf > 0:
                    ld.text((M - 6, hook_b.top - 250), _count(fig, pf), font=_font("serif", 200), fill=c + (255,))
            per = min(0.08, BAR * 0.45 / max(1, len(hook_b.items)))
            backdrop(lt + 0.2, n)
            sketch.draw(ld, doodles[0], dbox, lt + 0.3, ink, hi_c, seed=n, mode=mode, fills=(pal or {}).get("fills"))
            if rings["hook"]:
                k, bb = rings["hook"]
                sketch.ring(ld, bb, lt - per * k - 0.5, c + (255,), seed=n, mode=mode)
            hook_b.draw(ld, lt + 0.22, 0.0, per, T["ink"], c)        # the first word is already in place at frame one
            pu = ease((lt - per * len(hook_b.items)) / 0.35)
            if pu > 0:
                marker_underline(ld, M - 6, M - 6 + min(hook_b.last_w, TEXT_W) * pu, hook_b.bottom + 8, c + (255,), seed=n)

        elif kind == "point":
            k, b = data
            p0 = ease(lt / 0.25)
            ld.text((M, b.top - 90 - (1 - p0) * 30), f"{k + 1} / {len(points)}", font=_font("sans_bold", 44),
                    fill=c + (int(255 * p0),))
            per = min(0.11, (BAR * 1.2) / max(1, len(b.items)))
            dbox = box_under(b)
            chg = change_in(plain(card["points"][k]))
            if chg and mode == "cutout":
                change_badge(ld, dbox, lt - 0.1, chg[0], chg[1], T["ink"], c, (pal or {}).get("disc", (255, 255, 255)))
            else:
                backdrop(lt - 0.05, n * 10 + k)
            if not (chg and mode == "cutout"):
                sketch.draw(ld, doodles[1 + k], dbox, lt - 0.15, ink, hi_c, seed=n * 10 + k, mode=mode, fills=(pal or {}).get("fills"))
            if rings[f"p{k}"]:
                kk, bb = rings[f"p{k}"]
                sketch.ring(ld, bb, lt - per * kk - 0.45, c + (255,), seed=n * 10 + k, mode=mode)
            b.draw(ld, lt, 0.04, per, T["ink"], c)

        elif kind == "take":
            p0 = ease(lt / 0.25)
            tag = "DO THIS" if card.get("take_kind") == "do" else "OUR READ"
            tf = _font("sans_bold", 40)
            tw = ld.textlength(tag, font=tf)
            ty = take_b.top - 110
            ld.rounded_rectangle([M, ty, M + tw + 56, ty + 68], radius=34, outline=c + (int(255 * p0),), width=4)
            ld.text((M + 28, ty + 12), tag, font=tf, fill=c + (int(255 * p0),))
            per = min(0.11, (BAR * 1.2) / max(1, len(take_b.items)))
            dbox = box_under(take_b)
            backdrop(lt - 0.05, n * 10 + 9)
            sketch.draw(ld, doodles[-1], dbox, lt - 0.15, ink, hi_c, seed=n * 10 + 9, mode=mode, fills=(pal or {}).get("fills"))
            take_b.draw(ld, lt, 0.06, per, T["ink"], c)

        else:
            a = ease(lt / 0.35)
            mark(ld, W // 2, 640, int(110 * (0.6 + 0.4 * a)), T["accent"] + (int(255 * a),))
            for text, font, colour, y, delay in (
                    ("Full story, every claim sourced", _font("serif", 74), T["ink"], 860, 0.1),
                    ("link in bio", _font("serif", 96), T["accent"], 970, 0.25),
                    (re.sub(r"^https?://|/$", "", site["base_url"]), _font("sans", 48), T["muted"], 1120, 0.4),
                    ("Follow for tomorrow's AI news", _font("sans_bold", 52), T["ink"], 1270, 0.55)):
                p = ease((lt - delay) / 0.3)
                tw = ld.textlength(text, font=font)
                ld.text(((W - tw) / 2, y + (1 - p) * 24), text, font=font, fill=colour + (int(255 * p),))

        frame.paste(layer, (0, 0), layer)
        arr = np.asarray(frame).astype(np.int16) + grain
        if i > 0 and lt < 2 / FPS:          # cut flash on the kick
            arr = arr + 16
        yield np.clip(arr, 0, 255).astype(np.uint8).tobytes()


def story_reel(post: dict, section: dict, n: int, site: dict, out: Path, style: str = DEFAULT_STYLE,
               palette: str | None = None) -> Path:
    card = section["card"]
    bars = 2 + 2 * len(card["points"]) + (2 if card.get("take") else 0) + 1
    out.parent.mkdir(parents=True, exist_ok=True)
    wav, _ = write_wav(out.with_suffix(".wav"), bars=bars, seed=7 + n)
    seconds = bars * BAR + 1.0
    cmd = ["ffmpeg", "-y", "-loglevel", "error",
           "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
           "-i", str(wav), "-af", "loudnorm=I=-14:TP=-1.5:LRA=9,aresample=48000",
           "-c:v", "libx264", "-preset", "slow", "-crf", "16", "-maxrate", "20M", "-bufsize", "40M",
           "-pix_fmt", "yuv420p", "-profile:v", "high", "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
           "-t", f"{seconds:.2f}", "-movflags", "+faststart", str(out)]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for frame in render_frames(post, section, n, site, seconds, style, palette):
        proc.stdin.write(frame)
    proc.stdin.close()
    if proc.wait() != 0:
        raise RuntimeError("ffmpeg failed to encode a story reel")
    wav.unlink(missing_ok=True)
    return out
