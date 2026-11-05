"""The "pulse" story Reel (5 Nov 2026): built to keep a viewer from swiping. Same fact-checked card and narrator as
story_reel.py; a different look and presenter.

Brief: one surprising AI story in about 40 seconds, told by Spark (fma/spark.py), a glowing jelly orb, on a night
studio of drifting light. Something changes every second or two:
  - big captions, two or three words at a time, lit word by word as the voice says them (most people watch muted);
  - the stage changes every line: a giant number when the line has a figure; otherwise Spark shapeshifts into the
    line's idea (a coin for money, a chip for compute, a star for a launch, a speech bubble for the question);
  - Spark moves only with a reason: aside for a number, home after it, a jump to press Follow;
  - a slow camera push-in on every scene, a slide and a whoosh on every cut, story-style progress segments on top;
  - Spark reacts: eyes wide at a number, a tilt and a raised brow at the question, a tap on "Follow" at the end.
Frame one already shows the hook's first words, so the cover is the hook.
Text stays inside Instagram's safe band (clear of the caption at the bottom and the buttons on the right)."""
from __future__ import annotations

import math
import re
import subprocess
from functools import lru_cache
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from . import spark, voice
from .carousel import CAT_NAMES, key_figure, publishers, short_figure
from .music import BAR, BEAT, write_wav
from .reel import FPS, H, M, W, ease
from .social import plain
from .story_reel import voice_plan
from .visuals import _font

BG_TOP, BG_BOTTOM = (13, 15, 38), (38, 18, 60)
INK = (246, 244, 255)
MUTED = (160, 156, 196)
YELLOW = (255, 214, 90)
WASHES = [(64, 214, 196), (148, 110, 255), (255, 120, 96), (90, 160, 255)]     # one per scene, in turn
STAGE_Y = (470, 1080)
CAPTION_Y = 1215
SOURCE_Y = 1440
SR = voice.SR


# ---------------------------------------------------------------- the night studio

@lru_cache(maxsize=1)
def _gradient() -> Image.Image:
    yy = np.linspace(0, 1, H)[:, None, None]
    rgb = np.array(BG_TOP) * (1 - yy) + np.array(BG_BOTTOM) * yy
    return Image.fromarray(np.repeat(rgb, W, axis=1).astype(np.uint8), "RGB").convert("RGBA")


@lru_cache(maxsize=16)
def _soft(r: int, colour: tuple, alpha: int) -> Image.Image:
    """A blurred light disc: bokeh and the colour wash behind the stage."""
    s = r * 4
    im = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    ImageDraw.Draw(im).ellipse([r, r, 3 * r, 3 * r], fill=colour + (alpha,))
    return im.filter(ImageFilter.GaussianBlur(r * 0.6))


def _bokeh(seed: int):
    rng = np.random.default_rng(seed)
    cols = [(255, 132, 96), (64, 214, 196), (255, 214, 90), (148, 110, 255)]
    return [(rng.uniform(0, W), rng.uniform(0, H), int(rng.choice([8, 14, 22, 34])), cols[i % 4],
             rng.uniform(8, 26), rng.uniform(0, 6.3), int(rng.uniform(40, 90))) for i in range(24)]


def _background(t: float, dots, wash_from, wash_to, mix: float) -> Image.Image:
    im = _gradient().copy()
    for x, y, r, col, speed, ph, a in dots:      # drifting up, swaying a little
        yy = (y - t * speed) % (H + 200) - 100
        xx = x + math.sin(t * 0.6 + ph) * 30
        sp = _soft(r, col, a)
        im.alpha_composite(sp, (int(xx - sp.width / 2), int(yy - sp.height / 2)))
    cy = (STAGE_Y[0] + STAGE_Y[1]) // 2
    for col, k in ((wash_from, 1 - mix), (wash_to, mix)):
        if k > 0.02:
            sp = _soft(260, col, int(110 * k))
            im.alpha_composite(sp, (W // 2 - sp.width // 2, cy - sp.height // 2))
    return im


# ---------------------------------------------------------------- figures

PCT_RE = re.compile(r"\d+(?:\.\d+)?%")


def figure(text: str) -> str:
    """The number to show big: a money or scale figure first, else a percentage."""
    t = plain(text)
    fig = short_figure(key_figure(t))
    if fig:
        return fig
    m = PCT_RE.search(t)
    if m:
        return m.group(0)
    return count_figure(t)


COUNT_RE = re.compile(r"(?:\b(at least|more than|over|up to|as many as|nearly|about)\s+)?(?<![\d,.])"
                      r"(\d{1,3}(?:,\d{3})+|\d{2,})\s+(?:(\w+)\s+)?([a-z]+s)\b", re.I)


def fig_size(d, text: str, top: int = 250, width: int = 820) -> int:
    """The largest size up to `top` at which `text` fits `width` px: "$17B" stays huge, "35+ turbines" shrinks."""
    w = d.textlength(text, font=_font("serif", top))
    return max(80, min(top, int(top * width / max(1.0, w))))


def count_figure(text: str) -> str:
    """A plain count with what it counts ("35 turbines"), keeping its limits: "at least 35" shows as "35+" and "up to
    35" as "up to 35", never a bare number that claims more than the source (the ceiling rule, 31 Oct 2026). Years
    and dates are skipped."""
    for m in COUNT_RE.finditer(text):
        qual, num, noun = (m.group(1) or "").lower(), m.group(2), m.group(4).lower()
        mid = (m.group(3) or "").lower()
        if mid and len(f"{num} {mid} {noun}") <= 16:          # "12 data centres" reads; "35 combustion turbines" won't fit
            noun = f"{mid} {noun}"
        if re.fullmatch(r"(19|20)\d\d", num) or noun in ("years", "days", "months", "weeks", "hours", "minutes"):
            continue
        if qual in ("at least", "more than", "over"):
            return f"{num}+ {noun}"
        if qual in ("up to", "as many as"):
            return f"up to {num} {noun}"
        if qual in ("nearly", "about"):
            return f"~{num} {noun}"
        return f"{num} {noun}"
    return ""


def figure_time(timed: list[tuple[str, float]], fig: str) -> float:
    """When the voice reaches the figure: the number appears then, never before (pass 1, 5 Nov 2026: a counter
    climbing early showed "$15B" for a $17 billion line)."""
    digits = re.sub(r"\D", "", fig)[:2]
    for word, t in timed:
        if digits and digits in re.sub(r"\D", "", word):
            return t
    return timed[0][1] if timed else 0.0


def burst(d, cx: float, cy: float, t: float, colour, half_w: float = 150) -> None:
    """Rays that fly out as a number lands, starting outside the number (pass 2: they crossed "58%")."""
    if not 0 < t < 0.5:
        return
    p = t / 0.5
    for k in range(12):
        a = k * math.pi / 6 + 0.26
        r0, r1 = half_w + 40 + 160 * p, half_w + 80 + 220 * ease(p)
        d.line([cx + math.cos(a) * r0, cy + math.sin(a) * r0 * 0.6, cx + math.cos(a) * r1, cy + math.sin(a) * r1 * 0.6],
               fill=colour + (int(255 * (1 - p)),), width=8)


def hologram(layer: Image.Image, cx: float, cy: float, text_w: float, p: float, t: float, beam_from: float) -> None:
    """The panel Spark projects a number onto: a soft beam up from Spark, a teal-edged pane with scan lines that
    flickers on over its first 0.3 s. Drawn on its own layer and blended (see-through)."""
    if p <= 0:
        return
    on = min(1.0, p / 0.5)
    flick = 1.0 if p > 0.5 else (0.35 + 0.65 * (math.sin(p * 90) > -0.3))   # a quick flicker as it powers on
    a = on * flick
    w, h = text_w + 120, 300
    x0, y0, x1, y1 = cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2
    hl = Image.new("RGBA", layer.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(hl)
    d.polygon([(cx - 46, beam_from), (cx + 46, beam_from), (x1 - 40, y1), (x0 + 40, y1)], fill=(64, 214, 196, int(46 * a)))
    d.rounded_rectangle([x0, y0, x1, y1], radius=28, fill=(20, 60, 80, int(120 * a)),
                        outline=(64, 214, 196, int(230 * a)), width=4)
    for k in range(int(y0) + 12, int(y1) - 8, 9):            # scan lines, drifting
        if (k + int(t * 60)) % 18 < 9:
            d.line([(x0 + 14, k), (x1 - 14, k)], fill=(140, 240, 230, int(22 * a)))
    for cxk in (x0, x1):                                     # corner ticks
        d.line([(cxk, y0 + 30), (cxk, y0 + 6)], fill=(180, 255, 245, int(255 * a)), width=6)
    layer.alpha_composite(hl)


SLOGAN = "Hype not included."
LOGO = (255, 122, 60)                # the brand's clock mark, lifted for the night background


def draw_logo(layer: Image.Image, cx: float, cy: float, r: float, sweep: float, alpha: float) -> None:
    """The brand mark: a ring and a five-minute slice, the slice sweeping round as the card arrives."""
    d = ImageDraw.Draw(layer)
    a = int(255 * alpha)
    d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=LOGO + (a,), width=max(4, int(r * 0.19)))
    if sweep > 0:
        inner = r * 0.84
        d.pieslice([cx - inner, cy - inner, cx + inner, cy + inner], -90, -90 + 60 * sweep, fill=LOGO + (a,))


# ---------------------------------------------------------------- captions

def word_times(text: str, said: float, lead: float) -> list[tuple[str, float]]:
    """When each word is spoken, by its share of the letters: closer than an even split, as long words take longer."""
    words = plain(text).split()
    w = [len(x) + 1.5 for x in words]
    total, acc, out = sum(w), 0.0, []
    for word, k in zip(words, w):
        out.append((word, lead + said * acc / total))
        acc += k
    return out


def chunks(timed: list[tuple[str, float]], max_words: int = 3, max_chars: int = 18) -> list[list[tuple[str, float]]]:
    out, cur = [], []
    for wt in timed:
        if cur and (len(cur) >= max_words or len(" ".join(x for x, _ in cur + [wt])) > max_chars):
            out.append(cur)
            cur = []
        cur.append(wt)
        if wt[0][-1] in ".,;:?!":             # a pause in the sentence ends the chunk
            out.append(cur)
            cur = []
    if cur:
        out.append(cur)
    return out


def draw_caption(layer: Image.Image, groups, lt: float, hi: tuple = YELLOW, y_mid: float = CAPTION_Y) -> None:
    """The chunk being said, big and centred; the word being said sits on a pill in the speaker's colour."""
    k = max((i for i, g in enumerate(groups) if g[0][1] <= lt), default=0)
    g = groups[k]
    start = g[0][1] if k else min(0.0, g[0][1])
    p = ease((lt - start) / 0.14) if k else 1.0       # frame one already shows the first chunk: the cover
    d = ImageDraw.Draw(layer)
    size = 116
    while True:
        f = _font("serif", size)
        widths = [d.textlength(w, font=f) for w, _ in g]
        space = d.textlength(" ", font=f)
        total = sum(widths) + space * (len(g) - 1)
        if total <= W - 2 * M - 40 or size <= 70:
            break
        size -= 6
    x = (W - total) / 2
    y = y_mid - size / 2 + (1 - p) * 26
    active = max((i for i, (_, t) in enumerate(g) if t <= lt), default=-1)
    for i, ((word, _), wd) in enumerate(zip(g, widths)):
        if i == active:
            d.rounded_rectangle([x - 16, y - 6, x + wd + 16, y + size * 1.08], radius=22, fill=hi + (int(255 * p),))
            d.text((x, y), word, font=f, fill=BG_TOP + (int(255 * p),))
        else:
            d.text((x, y), word, font=f, fill=INK + (int(255 * p),), stroke_width=5, stroke_fill=BG_TOP + (int(200 * p),))
        x += wd + space


# ---------------------------------------------------------------- sound effects

def _whoosh(sec: float = 0.42) -> np.ndarray:
    n = int(sec * SR)
    rng = np.random.default_rng(3)
    noise = rng.normal(0, 1, n)
    env = np.sin(np.linspace(0, np.pi, n)) ** 2
    out, y, k = np.zeros(n), 0.0, np.linspace(0.02, 0.35, n)      # a low-pass that opens up: the sweep
    for i in range(n):
        y += k[i] * (noise[i] - y)
        out[i] = y
    return (out * env / max(1e-6, np.abs(out).max()) * 0.35).astype(np.float32)


def _pop(freq: float = 880, sec: float = 0.09) -> np.ndarray:
    t = np.arange(int(sec * SR)) / SR
    f = freq * (1 - 0.45 * t / sec)
    return (np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 38) * 0.3).astype(np.float32)


def sfx_track(seconds: float, cuts: list[float], pops: list[float]) -> np.ndarray:
    track = np.zeros(int((seconds + 1) * SR), np.float32)
    wh, pp = _whoosh(), _pop()
    for at, clip in [(c - 0.18, wh) for c in cuts] + [(p, pp) for p in pops]:
        i = max(0, int(at * SR))
        track[i:i + len(clip)] += clip[: len(track) - i]
    return track


# ---------------------------------------------------------------- frames

def render_frames(post: dict, section: dict, n: int, site: dict, plan: dict):
    card = section["card"]
    lead = 0.3
    lines = [("hook", card["hook"])] + [(f"p{k}", p) for k, p in enumerate(card["points"])]
    if card.get("take"):
        lines.append(("take", card["take"]))
    starts, t = [], 0.0
    for length in plan["lens"]:
        starts.append(t)
        t += length
    t_end = t
    seconds = plan["seconds"]
    scenes = [(s, s + ln, key, text) for (key, text), s, ln in zip(lines, starts, plan["lens"])]
    scenes.append((t_end, seconds, "end", None))
    groups = {key: chunks(word_times(text, plan["said"][key], lead)) for key, text in lines}
    end_timed = []
    if card.get("ask"):
        end_timed += word_times(card["ask"], plan["said"]["ask"], lead)
    end_timed += word_times(voice.OUTRO, plan["said"]["outro"], plan["outro_at"])
    groups["end"] = chunks(end_timed)
    figs = {key: figure(text) for key, text in lines}
    fig_at = {key: figure_time(word_times(text, plan["said"][key], lead), figs[key]) for key, text in lines if figs[key]}
    # Spark's choreography: an anchor, not an acrobat (5 Nov 2026, Pavan: jumping to one corner for every number
    # "making it comedy"). Spark keeps its place at centre stage and shapeshifts into each line's idea. When a number
    # lands it glides a little smaller and lower, no hop, and projects the number above itself as a hologram; it
    # glides back for the next line. The one jump left is the press on Follow. Spots: (centre x, bottom y, size);
    # the last field is the hop height, 0 for a glide.
    PRESENT = (540, 1110, 360)
    HOME = (540, 1100, 470)
    keys_ = [(0.0, *(PRESENT if figs["hook"] else HOME), 0)]
    presenting = bool(figs["hook"])
    for k, (sa, sb, skey, _) in enumerate(scenes):
        if skey == "end":
            if presenting:
                keys_.append((sa + 0.45, *HOME, 0))
            tap = sa + plan["outro_at"] + 1.6
            keys_.append((tap + 0.05, *HOME, 90))                  # the Follow press
            continue
        if k and presenting:
            keys_.append((sa + 0.45, *HOME, 0))
            presenting = False
        if figs[skey] and k:
            keys_.append((sa + fig_at[skey] - 0.25 + 0.35, *PRESENT, 0))
            presenting = True
    keys_.sort()
    HOP = 0.45

    # what Spark has turned into, scene by scene: each line's shape, the question's speech bubble, back to itself
    # for the closing line
    scene_shape = [spark.shape_for(plain(text)) if skey != "end" else "bubble" for _, _, skey, text in scenes]

    def shape_at(tt: float, i: int, lt: float):
        s0, _, skey, _ = scenes[i]
        to = scene_shape[i]
        if skey == "end" and lt >= plan["outro_at"]:
            return "bubble", "blob", ease((lt - plan["outro_at"]) / 0.4)
        frm = scene_shape[i - 1] if i else to
        return frm, to, ease((lt - 0.1) / 0.4)

    def pose(tt: float):
        """(centre x, bottom y, size, squash x, squash y) at time tt."""
        prev = keys_[0]
        for kf in keys_[1:]:
            if tt < kf[0] - HOP:
                break
            if tt < kf[0]:                           # mid-hop: an arc from the last spot to this one
                p = ease((tt - (kf[0] - HOP)) / HOP)
                x = prev[1] + (kf[1] - prev[1]) * p
                y = prev[2] + (kf[2] - prev[2]) * p - kf[4] * math.sin(math.pi * p)
                s = prev[3] + (kf[3] - prev[3]) * p
                st = 1 + 0.08 * math.sin(math.pi * p) if kf[4] else 1.0     # stretched in the air (a hop, not a glide)
                return x, y, s, 1 / st, st
            prev = kf
        since = tt - prev[0]
        sq = 0.12 * max(0.0, 1 - since / 0.2) if prev[4] else 0.0  # squash on landing
        x = prev[1] + math.sin(tt * 1.3 + n) * 5                  # a slight float, no wandering
        y = prev[2] + math.sin(tt * 2.1) * 4
        return x, y, prev[3], 1 + sq, 1 - sq

    def hopping(tt: float) -> bool:
        return any(kf[0] - HOP <= tt < kf[0] and kf[4] for kf in keys_[1:])

    def place_spark(layer, tt, mth, mood, i, lt, look_at=None):
        frm, to, mp = shape_at(tt, i, lt)
        if hopping(tt):                              # a fading light trail behind a hop
            for back, alpha in ((0.10, 70), (0.05, 120)):
                gx, gy, gs, _, _ = pose(tt - back)
                ghost = spark.draw(int(gs), tt - back, 0.0, mood, beat=BEAT, seed=n, shape=to, shape_from=frm, morph=mp)
                ghost.putalpha(ghost.getchannel("A").point(lambda v, a=alpha: v * a // 255))
                layer.alpha_composite(ghost, (int(gx - ghost.width / 2), int(gy - ghost.height)))
        x, y, s, kx, ky = pose(tt)
        look = (0.0, 0.6)
        if look_at:
            dx, dy = look_at[0] - x, look_at[1] - (y - s / 2)
            r = max(1.0, math.hypot(dx, dy))
            look = (dx / r, dy / r)
        im = spark.draw(int(s), tt, mth, mood, beat=BEAT, seed=n, look=look, shape=to, shape_from=frm, morph=mp)
        im = im.resize((max(8, int(s * kx)), max(8, int(s * ky))), Image.BILINEAR)
        layer.alpha_composite(im, (int(x - im.width / 2), int(y - im.height)))

    dots = _bokeh(n)
    source = publishers(post, section)
    label = CAT_NAMES.get(section.get("category", ""), "").upper()
    mouth = plan["mouth"]
    total_frames = int(seconds * FPS)

    for fi in range(total_frames):
        tt = fi / FPS
        i = next(j for j, s in enumerate(scenes) if s[0] <= tt < s[1] or j == len(scenes) - 1)
        s0, s1, key, text = scenes[i]
        lt = tt - s0
        mix = ease(lt / 0.5)
        frame = _background(tt, dots, WASHES[(i - 1) % 4], WASHES[i % 4], mix if i else 1.0)
        layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(layer)

        # header: brand, topic, one progress segment per scene
        d.text((M, 300), site["name"].upper(), font=_font("sans_bold", 32), fill=YELLOW + (255,))
        lf = _font("sans_bold", 30)
        lw = d.textlength(label, font=lf)
        d.rounded_rectangle([W - M - lw - 116, 290, W - M - 60, 344], radius=27, outline=INK + (200,), width=3)
        d.text((W - M - lw - 88, 299), label, font=lf, fill=INK + (230,))
        segs, gap = len(scenes), 10
        sw = (W - 2 * M - 60 - gap * (segs - 1)) / segs
        for k in range(segs):
            x0 = M + k * (sw + gap)
            d.rounded_rectangle([x0, 372, x0 + sw, 380], radius=4, fill=INK + (60,))
            fill = 1.0 if k < i else (min(1.0, lt / max(0.1, s1 - s0)) if k == i else 0.0)
            if fill:
                d.rounded_rectangle([x0, 372, x0 + sw * fill, 380], radius=4, fill=INK + (235,))

        slide = (1 - ease(lt / 0.3)) * 160 if i else 0.0
        fi_m = min(len(mouth) - 1, fi)
        m = float(mouth[fi_m]) if len(mouth) else 0.0
        if key != "end":
            fig = figs[key]
            if fig:                                  # a giant number lands as the voice says it
                vs = fig_at[key] - 0.25
                # the hook's number is on screen from frame one (the cover) and stays: it showing on frame one, then
                # vanishing until spoken, read as a flicker (5 Nov 2026)
                pc = 1.0 if i == 0 else (lt - vs) / 0.6
                top = fig_size(d, fig)
                big = _font("serif", top)
                tw = d.textlength(fig, font=big)
                if pc > 0:
                    # the real number, whole, popping in with an overshoot: no count-up, because a frame of a
                    # climbing counter shows a false figure (pass 2, 5 Nov 2026: "$1B" on its way to $17B)
                    hologram(layer, W / 2 + slide, 620, tw, pc, tt, 1110 - 360 + 20)
                    q = min(1.0, pc / 0.5)
                    scale = 1.0 if q >= 1 else 0.6 + 0.4 * q + 0.12 * math.sin(math.pi * q)
                    fsz = max(40, int(top * scale))
                    f2 = _font("serif", fsz)
                    w2 = d.textlength(fig, font=f2)
                    d.text(((W - w2) / 2 + slide, 650 - fsz * 0.52), fig, font=f2, fill=YELLOW + (int(255 * min(1, q * 2)),),
                           stroke_width=6, stroke_fill=BG_TOP + (255,))
                place_spark(layer, tt, m, "wow" if 0 < pc < 2.2 else "talk", i, lt,
                            look_at=(W / 2, 650) if pc > 0 else None)
            else:                                    # Spark centre stage, shapeshifted into the line's idea
                place_spark(layer, tt, m, "talk", i, lt)
            draw_caption(layer, groups[key], lt)
            if source:
                sf = _font("sans", 32)
                st = f"Source: {source}"
                d.text(((W - d.textlength(st, font=sf)) / 2, SOURCE_Y), st, font=sf, fill=MUTED + (255,))
        elif plan.get("sign_at") is not None and lt >= plan["sign_at"] - 0.25:
            # the logo card: the clock mark sweeps its five-minute slice; Spark says the name and the slogan
            cp = ease((lt - plan["sign_at"] + 0.25) / 0.5)
            draw_logo(layer, W / 2, 640, 150 * (0.7 + 0.3 * cp), ease((lt - plan["sign_at"]) / 0.8), cp)
            d.text((W / 2, 880 + (1 - cp) * 30), site["name"], font=_font("serif", 92), fill=INK + (int(255 * cp),),
                   anchor="mm")
            sp = ease((lt - plan["sign_at"] - plan["said"]["sign"] * 0.45) / 0.3)
            if sp > 0:
                sf = _font("serif", int(66 * (0.85 + 0.15 * sp)))
                tw = d.textlength(SLOGAN, font=sf)
                d.rounded_rectangle([W / 2 - tw / 2 - 26, 958, W / 2 + tw / 2 + 26, 1052], radius=30,
                                    fill=YELLOW + (int(255 * sp),))
                d.text((W / 2, 1004), SLOGAN, font=sf, fill=BG_TOP + (int(255 * sp),), anchor="mm")
            mth = float(mouth[min(len(mouth) - 1, fi)]) if len(mouth) else 0.0
            im = spark.draw(300, tt, mth, "talk", beat=BEAT, seed=n, look=(0.0, 0.5))
            layer.alpha_composite(im, (W // 2 - 150, 1110))
            d.text((W / 2, 1490), "Follow @fiveminute_ai", font=_font("sans_bold", 40), fill=INK + (int(230 * cp),),
                   anchor="mm")
        else:
            asking = card.get("ask") and lt < plan["outro_at"]
            if card.get("ask"):
                cf = _font("sans_bold", 36)
                tag = "YOUR TAKE?"
                tw = d.textlength(tag, font=cf)
                a = ease(lt / 0.25)
                d.rounded_rectangle([(W - tw) / 2 - 28, 470, (W + tw) / 2 + 28, 530], radius=30, fill=YELLOW + (int(255 * a),))
                d.text(((W - tw) / 2, 478), tag, font=cf, fill=BG_TOP + (int(255 * a),))
            place_spark(layer, tt, m, "ask" if asking else "talk", i, lt)
            draw_caption(layer, groups["end"], lt)
            # the follow button: it arrives with the closing line and gets a tap
            fa = ease((lt - plan["outro_at"] - 0.2) / 0.3)
            if fa > 0:
                bf = _font("sans_bold", 46)
                label_f = "Follow @fiveminute_ai"
                bw = d.textlength(label_f, font=bf)
                tap = lt - plan["outro_at"] - 1.6
                press = 0.94 if 0 < tap < 0.16 else 1.0
                bx0, by0 = (W - bw) / 2 - 44, 1350
                bx1, by1 = (W + bw) / 2 + 44, 1446
                cx, cy = (bx0 + bx1) / 2, (by0 + by1) / 2
                hw, hh = (bx1 - bx0) / 2 * press, (by1 - by0) / 2 * press
                d.rounded_rectangle([cx - hw, cy - hh + (1 - fa) * 30, cx + hw, cy + hh + (1 - fa) * 30], radius=48,
                                    fill=(255, 132, 96, int(255 * fa)))
                d.text((cx - bw / 2 * press, cy - 28 + (1 - fa) * 30), label_f, font=_font("sans_bold", int(46 * press)),
                       fill=INK + (int(255 * fa),))
                if 0 < tap < 0.6:                    # the tap ripple
                    rr = 30 + tap * 220
                    d.ellipse([cx + 120 - rr, cy - rr, cx + 120 + rr, cy + rr], outline=INK + (int(220 * (1 - tap / 0.6)),),
                              width=5)

        frame.alpha_composite(layer)
        if i and lt < 2 / FPS:                       # a flash on the cut
            frame = Image.blend(frame, Image.new("RGBA", (W, H), (255, 255, 255, 255)), 0.12)
        z = 1 + 0.035 * min(1.0, lt / max(0.5, s1 - s0))   # slow push-in on every scene
        if z > 1.001:
            cw, ch = W / z, H / z
            frame = frame.crop((int((W - cw) / 2), int((H - ch) / 2), int((W + cw) / 2), int((H + ch) / 2))).resize(
                (W, H), Image.BILINEAR)
        yield frame.convert("RGB").tobytes()


def pulse_reel(post: dict, section: dict, n: int, site: dict, out: Path, who: str = "spark-american") -> Path:
    """Render the pulse Reel. Needs the narrator (voice.available()) and ffmpeg."""
    card = section["card"]
    plan = voice_plan(card, n, who, sign_off=f"{site['name']}. {SLOGAN}")
    seconds = plan["seconds"]
    out.parent.mkdir(parents=True, exist_ok=True)
    music, _ = write_wav(out.with_suffix(".m.wav"), bars=math.ceil(seconds / BAR) + 1, seed=7 + n)
    vo = voice.write_wav(out.with_suffix(".vo.wav"), plan["track"])
    cuts = [sum(plan["lens"][:k]) for k in range(1, len(plan["lens"]) + 1)]
    # a pop as each giant number lands, at the same moment the picture shows it
    lines = [card["hook"], *card["points"]] + ([card["take"]] if card.get("take") else [])
    keys = ["hook"] + [f"p{j}" for j in range(len(card["points"]))] + (["take"] if card.get("take") else [])
    pops = []
    for k, (key, text) in enumerate(zip(keys, lines)):
        fig = figure(text)
        if fig:
            at = figure_time(word_times(text, plan["said"][key], 0.3), fig)
            pops.append(sum(plan["lens"][:k]) + at - 0.25)
    pops.append(sum(plan["lens"]) + plan["outro_at"] + 1.6)          # the follow tap
    fx = voice.write_wav(out.with_suffix(".fx.wav"), sfx_track(seconds, cuts, pops))
    cmd = ["ffmpeg", "-y", "-loglevel", "error",
           "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
           "-i", str(music), "-i", str(vo), "-i", str(fx), "-filter_complex",
           "[2:a]aresample=48000,asplit=2[v][vk];[1:a]aresample=48000,volume=0.5[m];[3:a]aresample=48000[fx];"
           "[m][vk]sidechaincompress=threshold=0.02:ratio=8:attack=20:release=400[md];"
           "[md][v][fx]amix=inputs=3:weights=1 1.6 0.9:normalize=0,loudnorm=I=-14:TP=-1.5:LRA=9[a]",
           "-map", "0:v", "-map", "[a]",
           "-c:v", "libx264", "-preset", "slow", "-crf", "17", "-maxrate", "20M", "-bufsize", "40M",
           "-pix_fmt", "yuv420p", "-profile:v", "high", "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
           "-t", f"{seconds:.2f}", "-movflags", "+faststart", str(out)]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for frame in render_frames(post, section, n, site, plan):
        proc.stdin.write(frame)
    proc.stdin.close()
    if proc.wait() != 0:
        raise RuntimeError("ffmpeg failed to encode a pulse reel")
    for p in (music, vo, fx):
        p.unlink(missing_ok=True)
    return out
