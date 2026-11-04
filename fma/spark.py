"""Spark: the second presenter, a glowing jelly orb that is the voice of the news (5 Nov 2026, alongside the robot
anchor in presenter.py). Drawn in code, so there is nothing to license and no real person's likeness.

It squashes and stretches as it talks (the mouth follows the narrator's loudness), bobs on the beat, blinks,
widens its eyes at a big number ("wow"), raises a brow and tilts at a question ("ask"), and throws off sparkles.
Drawn at 2x and scaled down for smooth edges."""
from __future__ import annotations

import math
import re
from functools import lru_cache

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

BODY = (255, 132, 96)         # warm coral: reads on the night background and on phones with the brightness down
BODY_DARK = (214, 78, 74)
EYE = (255, 252, 246)
PUPIL = (28, 24, 52)
GLOW = (255, 160, 110)


@lru_cache(maxsize=8)
def _halo(size: int) -> Image.Image:
    """A soft glow disc behind the orb, made once per size."""
    S = size * 2
    im = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    r = S * 0.36
    d.ellipse([S / 2 - r, S / 2 - r, S / 2 + r, S / 2 + r], fill=GLOW + (150,))
    return im.filter(ImageFilter.GaussianBlur(S * 0.08))


@lru_cache(maxsize=8)
def _shade(size: int) -> Image.Image:
    """Shading for the jelly body: light top-left, deeper colour bottom-right. Masked by the blob shape each frame."""
    S = size * 2
    yy, xx = np.mgrid[0:S, 0:S] / S
    d = np.clip(np.hypot(xx - 0.38, yy - 0.32) / 0.75, 0, 1)[..., None]
    rgb = np.array(BODY) * (1 - d) + np.array(BODY_DARK) * d
    return Image.fromarray(np.dstack([rgb, np.full((S, S, 1), 255)]).astype(np.uint8), "RGBA")


# Shapeshifting (5 Nov 2026, Pavan: "can spark be shapeshifting too?"): instead of a doodle beside it, Spark becomes
# the idea of the line. Each shape is a radius per angle around the centre, so any shape morphs smoothly into any
# other: the outline is a mix of the two radii.
SHAPES = ("blob", "coin", "chip", "star", "bubble")


def _shape_r(shape: str, a: float) -> float:
    if shape == "chip":                       # a rounded square: a superellipse
        p = 6.0
        return 0.9 / (abs(math.cos(a)) ** p + abs(math.sin(a)) ** p) ** (1 / p)
    if shape == "star":                       # five soft points, one straight up
        return 0.86 + 0.2 * math.cos(5 * (a + math.pi / 2))
    if shape == "bubble":                     # a speech bubble: round, a little wider than tall
        return 1.0 / math.sqrt((math.cos(a) / 1.06) ** 2 + (math.sin(a) / 0.94) ** 2)
    return 1.0                                # blob and coin: round (the coin is the flat, still one)


def _blob(cx, cy, r, t, sx, sy, n=96, shape="blob", shape_from="blob", morph=1.0):
    pts = []
    calm = morph if shape != "blob" else 1 - morph if shape_from != "blob" else 0.0     # shapes hold still
    for i in range(n):
        a = 2 * math.pi * i / n
        wob = (0.022 * math.sin(3 * a + t * 2.1) + 0.014 * math.sin(5 * a - t * 3.3)) * (1 - 0.8 * calm)
        k = (_shape_r(shape_from, a) * (1 - morph) + _shape_r(shape, a) * morph) * (1 + wob)
        pts.append((cx + math.cos(a) * r * k * sx, cy + math.sin(a) * r * k * sy))
    return pts


def shape_for(text: str) -> str:
    """Which shape a line asks for, from its words. Most lines stay a blob: the shape is an accent, not a rule."""
    low = text.lower()
    if text.rstrip().endswith("?"):
        return "bubble"
    if re.search(r"\b(compute|chips?|gpus?|servers?|data cent(re|er)s?|processors?)\b", low):
        return "chip"
    if re.search(r"\$\d|\b(revenue|billion|million|pay(s|ing)?|price|cost|funding|raises?)\b", low):
        return "coin"
    if re.search(r"\b(launch(es|ed)?|first|beats?|record|tops?|wins?|new model)\b", low):
        return "star"
    return "blob"


def _star(d, x, y, r, a, colour):
    pts = []
    for i in range(8):
        rr = r if i % 2 == 0 else r * 0.32
        ang = a + i * math.pi / 4
        pts.append((x + math.cos(ang) * rr, y + math.sin(ang) * rr))
    d.polygon(pts, fill=colour)


def _trim(im, shape: str, k: float, cx, cy, r, u) -> None:
    """The details that make a shape read: a coin's rim and stamp, a chip's pins, a bubble's tail, a star's glint.
    Faded in with the morph (k)."""
    if k <= 0.02 or shape == "blob":
        return
    a = int(255 * min(1.0, k))
    layer = Image.new("RGBA", im.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    gold = (255, 214, 90)
    if shape == "coin":
        d.ellipse([cx - r * 0.86, cy - r * 0.86, cx + r * 0.86, cy + r * 0.86], outline=gold + (a,), width=int(1.6 * u))
        for i in range(36):                   # the milled edge
            ang = i * math.pi / 18
            d.line([cx + math.cos(ang) * r * 0.93, cy + math.sin(ang) * r * 0.93,
                    cx + math.cos(ang) * r * 1.0, cy + math.sin(ang) * r * 1.0], fill=gold + (a // 2,), width=int(0.8 * u))
        f = _stamp_font(int(9 * u))
        d.text((cx, cy + r * 0.68), "$", font=f, fill=gold + (a,), anchor="mm")      # below the mouth, clear of the brows
    elif shape == "chip":
        for side in range(4):
            for j in range(-2, 3):
                o = j * r * 0.32
                L = r * 0.16
                x0, y0 = [(cx + o, cy - r * 0.9), (cx + r * 0.9, cy + o), (cx + o, cy + r * 0.9), (cx - r * 0.9, cy + o)][side]
                dx, dy = [(0, -1), (1, 0), (0, 1), (-1, 0)][side]
                d.line([x0, y0, x0 + dx * L, y0 + dy * L], fill=gold + (a,), width=int(2 * u))
    elif shape == "bubble":
        d.polygon([(cx - r * 0.55, cy + r * 0.72), (cx - r * 0.15, cy + r * 0.86), (cx - r * 0.86, cy + r * 1.18)],
                  fill=(232, 106, 84, a))
    elif shape == "star":
        d.ellipse([cx - r * 0.07, cy - r * 0.98, cx + r * 0.07, cy - r * 0.84], fill=(255, 255, 255, a))   # the top point
    im.alpha_composite(layer)


def _stamp_font(px: int):
    from .visuals import _font
    return _font("serif", px)


def draw(size: int, t: float, mouth: float, mood: str = "talk", beat: float = 0.6, seed: int = 0,
         look: tuple[float, float] = (0.0, 0.25), shape: str = "blob", shape_from: str = "blob",
         morph: float = 1.0) -> Image.Image:
    """One frame, `size` px square, RGBA. mood: "talk", "wow" (a big number), "ask" (a question), "idle".
    shape: what Spark has turned into (SHAPES); it is `morph` (0..1) of the way there from `shape_from`."""
    S = size * 2
    im = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    im.alpha_composite(_halo(size))
    u = S / 100
    bounce = math.sin(2 * math.pi * t / beat)
    sx = 1 + 0.05 * mouth - 0.012 * bounce                      # squash and stretch with the voice and the beat
    sy = 1 - 0.045 * mouth + 0.012 * bounce
    cx, cy, r = 50 * u, 52 * u - 1.4 * u * bounce, 30 * u

    # body: shaded jelly in the blob's shape, a rim light and a glossy highlight
    mask = Image.new("L", (S, S), 0)
    outline = _blob(cx, cy, r, t + seed, sx, sy, shape=shape, shape_from=shape_from, morph=morph)
    ImageDraw.Draw(mask).polygon(outline, fill=255)
    im.paste(_shade(size), (0, 0), mask)
    # see-through pieces go on their own layer and are blended: drawn straight onto the image they replace the
    # pixels and show the dark background through (pass 1, 5 Nov 2026: grey "bruises" for highlights)
    gloss = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    g = ImageDraw.Draw(gloss)
    rim = _blob(cx, cy, r * 0.985, t + seed, sx, sy, shape=shape, shape_from=shape_from, morph=morph)
    g.line(rim + [rim[0]], fill=(255, 214, 180, 140), width=int(0.9 * u))
    g.ellipse([cx - 17 * u, cy - 22 * u, cx - 5 * u, cy - 15 * u], fill=(255, 255, 255, 110))
    g.ellipse([cx - 3 * u, cy - 24.5 * u, cx + 1 * u, cy - 21.5 * u], fill=(255, 255, 255, 90))
    for side in (-1, 1):
        g.ellipse([cx + side * 17 * u - 3.4 * u, cy + 2 * u, cx + side * 17 * u + 3.4 * u, cy + 5.5 * u],
                  fill=(255, 80, 110, 110))
    im.alpha_composite(gloss)
    d = ImageDraw.Draw(im)
    _trim(im, shape, morph, cx, cy, r, u)
    if shape_from != shape:
        _trim(im, shape_from, 1 - morph, cx, cy, r, u)

    # eyes: blink every few seconds; wide at a big number; pupils look where told (the caption, by default)
    period = 3.3 + (seed % 3) * 0.5
    ph = (t + seed * 0.41) % period
    blink = 1.0 - (max(0.0, 1 - abs(ph - 0.08) / 0.08) if ph < 0.16 else 0.0)
    wide = 1.25 if mood == "wow" else 1.0
    ey = cy - 5 * u
    for side in (-1, 1):
        ex = cx + side * 10.5 * u
        ew, eh = 6.2 * u * wide, 8.0 * u * wide * blink
        d.ellipse([ex - ew, ey - eh, ex + ew, ey + eh], fill=EYE + (255,))
        if blink > 0.3:
            px, py = ex + look[0] * 2.6 * u, ey + look[1] * 3.4 * u
            pr = 3.4 * u
            d.ellipse([px - pr, py - pr, px + pr, py + pr], fill=PUPIL + (255,))
            d.ellipse([px - pr * 0.25 - 1.4 * u, py - pr * 0.6, px - pr * 0.25, py - pr * 0.6 + 1.4 * u],
                      fill=(255, 255, 255, 255))
        # brows: one goes up at a question
        lift = (3.2 * u if (mood == "ask" and side == 1) else 0) + (1.6 * u if mood == "wow" else 0)
        d.arc([ex - 6 * u, ey - eh - 6 * u - lift, ex + 6 * u, ey - eh + 1 * u - lift], 200, 340,
              fill=PUPIL + (230,), width=int(1.3 * u))

    # mouth: a smile when quiet; opens with the voice, wider than tall
    mx, my = cx, cy + 10.5 * u
    w, h = 8 * u + 6 * u * mouth, 0.8 * u + 7 * u * mouth
    if mood == "wow" and mouth < 0.2:
        w, h = 5 * u, 5 * u                                      # a little "oh"
    if h < 1.6 * u:
        d.arc([mx - w / 2, my - 3.4 * u, mx + w / 2, my + 2.2 * u], 15, 165, fill=PUPIL + (255,), width=int(1.4 * u))
    else:
        d.rounded_rectangle([mx - w / 2, my - h / 2, mx + w / 2, my + h / 2], radius=min(w, h) / 2, fill=PUPIL + (255,))
        if h > 4 * u:
            d.ellipse([mx - w / 3.2, my + h / 2 - 2.6 * u, mx + w / 3.2, my + h / 2 - 0.4 * u], fill=(255, 110, 120, 255))

    # sparkles: three little stars orbit and twinkle (blended, like the gloss)
    stars = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(stars)
    for k in range(3):
        a = t * 0.9 + k * 2.1 + seed
        rr = 40 * u + 3 * u * math.sin(t * 1.7 + k)
        x, y = cx + math.cos(a) * rr, cy + math.sin(a) * rr * 0.8
        tw = 0.5 + 0.5 * math.sin(t * 5 + k * 1.9)
        _star(d, x, y, (1.6 + 1.6 * tw) * u, t + k, (255, 232, 150, int(140 + 115 * tw)))

    im.alpha_composite(stars)
    out = im.resize((size, size), Image.LANCZOS)
    tilt = (7 if mood == "ask" else 0) + 2.2 * math.sin(t * 0.8 + seed)
    return out.rotate(tilt, resample=Image.BICUBIC)
