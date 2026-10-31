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


def style_background(style: str, n: int):
    """Backgrounds for the non-doodle looks, drawn once per Reel."""
    th = STYLE_THEMES[style]
    img = Image.new("RGB", (W, H), th["bg"])
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
    elif style == "cutout":                      # two big paper shapes in the corners
        d.ellipse([W - 230, 150, W + 250, 630], fill=(38, 150, 140, 60))
        d.pieslice([-300, H - 470, 420, H + 250], 270, 360, fill=(242, 190, 64, 110))
        d.rectangle([0, 0, W, 10], fill=(240, 110, 80, 255))
    else:                                        # comic: halftone dots, bigger toward the bottom-right corner
        for y in range(0, H, 34):
            for x in range(0, W, 34):
                k = ((x / W) * 0.5 + (y / H) * 0.8)
                r = max(0.0, (k - 0.35) * 14)
                if r > 0.6:
                    d.ellipse([x - r, y - r, x + r, y + r], fill=th["dot"] + (150,))
        d.rectangle([24, 24, W - 24, H - 24], outline=(15, 15, 15, 255), width=10)   # the panel border
    return img


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


def render_frames(post: dict, section: dict, n: int, site: dict, seconds: float, style: str = DEFAULT_STYLE):
    card = section["card"]
    probe = ImageDraw.Draw(Image.new("RGB", (8, 8)))
    if style == "doodle":
        theme = "night" if n % 2 == 0 else "paper"
        T = THEMES[theme]
        c = T["topic"].get(section.get("category"), T["accent"])
        bg = background(theme, c, "top-right" if n % 2 == 0 else "bottom-left")
        face, mode, hi = "serif", "pen", None
    else:
        theme = "night" if style == "chalk" else "paper"
        T = STYLE_THEMES[style]
        c, face, mode, hi = T["c"], T["font"], style, T["hi"]
        bg = style_background(style, n)
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
        name = sketch.pick(text, used) if text else "spark"
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
            sketch.paper(ld, dbox, t, (242, 190, 64, 255), seed=seed)
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
            sketch.draw(ld, doodles[0], dbox, lt + 0.3, ink, hi_c, seed=n, mode=mode)
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
            backdrop(lt - 0.05, n * 10 + k)
            sketch.draw(ld, doodles[1 + k], dbox, lt - 0.15, ink, hi_c, seed=n * 10 + k, mode=mode)
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
            sketch.draw(ld, doodles[-1], dbox, lt - 0.15, ink, hi_c, seed=n * 10 + 9, mode=mode)
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


def story_reel(post: dict, section: dict, n: int, site: dict, out: Path, style: str = DEFAULT_STYLE) -> Path:
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
    for frame in render_frames(post, section, n, site, seconds, style):
        proc.stdin.write(frame)
    proc.stdin.close()
    if proc.wait() != 0:
        raise RuntimeError("ffmpeg failed to encode a story reel")
    wav.unlink(missing_ok=True)
    return out
