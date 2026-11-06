"""Doubt: Spark's sceptical sidekick in the duo Reels (5 Nov 2026). A little periwinkle cube with half-lidded eyes
that pushes back on the story with questions ("So it's making money?"). It only ever asks; every fact is Spark's,
from the checked text. Drawn in code, no real person's likeness.

Its mouth follows its own voice; while it listens it keeps one brow raised and a flat, unimpressed mouth; when it
talks it leans in. Drawn at 2x and scaled down."""
from __future__ import annotations

import math

from PIL import Image, ImageDraw

FRONT, TOP, SIDE = (122, 140, 214), (170, 184, 240), (78, 92, 170)
EYE, PUPIL = (255, 252, 246), (28, 24, 52)


def draw(size: int, t: float, mouth: float, talking: bool, seed: int = 0, look: tuple[float, float] = (-0.6, 0.0)) -> Image.Image:
    S = size * 2
    im = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    u = S / 100
    bob = math.sin(t * 2.0 + seed) * 0.8 * u
    lean = 1.8 * u if talking else 0.0                 # leans in when it talks
    ox, oy = -lean, bob

    # soft shadow on the floor
    sh = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    ImageDraw.Draw(sh).ellipse([22 * u, 88 * u, 84 * u, 96 * u], fill=(0, 0, 0, 70))
    im.alpha_composite(sh)
    f = [(22 * u + ox, 34 * u + oy), (70 * u + ox, 34 * u + oy), (70 * u + ox, 84 * u + oy), (22 * u + ox, 84 * u + oy)]
    top = [(22 * u + ox, 34 * u + oy), (36 * u + ox, 20 * u + oy), (84 * u + ox, 20 * u + oy), (70 * u + ox, 34 * u + oy)]
    side = [(70 * u + ox, 34 * u + oy), (84 * u + ox, 20 * u + oy), (84 * u + ox, 70 * u + oy), (70 * u + ox, 84 * u + oy)]
    d.polygon(side, fill=SIDE + (255,))
    d.polygon(top, fill=TOP + (255,))
    d.rounded_rectangle([f[0][0], f[0][1], f[2][0], f[2][1]], radius=4 * u, fill=FRONT + (255,))
    d.line([f[0][0] + 3 * u, f[0][1] + 2.5 * u, f[1][0] - 3 * u, f[0][1] + 2.5 * u], fill=(190, 202, 248, 255),
           width=int(1.2 * u))                          # a highlight along the top edge

    # eyes: half-lidded; open a little wider while it talks; blink now and then
    period = 4.1 + (seed % 2) * 0.7
    ph = (t + seed * 0.53) % period
    blink = ph < 0.14
    lid = 0.0 if talking else 1.6 * u
    for k, ex in enumerate((35 * u + ox, 57 * u + ox)):
        ey = 54 * u + oy
        if blink:
            d.line([ex - 6 * u, ey, ex + 6 * u, ey], fill=PUPIL + (255,), width=int(1.4 * u))
        else:
            d.ellipse([ex - 6 * u, ey - 6 * u, ex + 6 * u, ey + 6 * u], fill=EYE + (255,))
            px, py = ex + look[0] * 2.4 * u, ey + 1.2 * u + look[1] * 2 * u
            d.ellipse([px - 2.6 * u, py - 2.6 * u, px + 2.6 * u, py + 2.6 * u], fill=PUPIL + (255,))
            d.rectangle([ex - 7 * u, ey - 7 * u, ex + 7 * u, ey - 1.5 * u + lid - 1.6 * u], fill=FRONT + (255,))   # lid
        # brows: the right one always up (that's the character); both up a touch when it asks
        up = (5 * u if k == 1 else 0) + (1.2 * u if talking else 0)
        d.line([ex - 6 * u, ey - 6 * u - up + (1.5 * u if k == 0 else 0), ex + 6 * u, ey - 8 * u - up],
               fill=PUPIL + (255,), width=int(1.6 * u))
    # mouth: a flat, unimpressed line, opening with its voice
    mx, my = 46 * u + ox, 71 * u + oy
    if mouth < 0.08:
        d.line([mx - 7 * u, my + 1 * u, mx + 7 * u, my - 0.6 * u], fill=PUPIL + (255,), width=int(1.6 * u))
    else:
        w, h = 9 * u + 3 * u * mouth, 1.4 * u + 5 * u * mouth
        d.rounded_rectangle([mx - w / 2, my - h / 2, mx + w / 2, my + h / 2], radius=min(w, h) / 2, fill=PUPIL + (255,))
    out = im.resize((size, size), Image.LANCZOS)
    return out.rotate(-4 - (3 if talking else 0) * math.sin(t * 1.4), resample=Image.BICUBIC)
