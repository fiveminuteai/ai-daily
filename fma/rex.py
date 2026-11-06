"""Rex: a guest for the duo Reels (5 Nov 2026), a tired old T. rex in reading glasses, brought on for stories about
power, fuel and emissions. Sarcastic, slow, unimpressed. Like Doubt, Rex never states a fact; Rex reacts.

Faces left, toward Spark. The jaw opens with Rex's voice; heavy lids blink slowly; the tiny arms gesture when Rex
talks. Drawn at 2x and scaled down."""
from __future__ import annotations

import math

from PIL import Image, ImageDraw

SKIN, SKIN_DARK, BELLY = (98, 176, 112), (62, 128, 80), (196, 226, 160)
EYE, PUPIL, GLASS = (255, 252, 240), (28, 24, 40), (40, 40, 52)


def draw(size: int, t: float, mouth: float, talking: bool, seed: int = 0, look: tuple[float, float] = (-0.8, 0.0)) -> Image.Image:
    S = size * 2
    im = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    u = S / 100
    breathe = math.sin(t * 1.6 + seed) * 0.7 * u
    nod = (math.sin(t * 3.2) * 1.2 * u) if talking else 0.0

    sh = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    ImageDraw.Draw(sh).ellipse([30 * u, 92 * u, 88 * u, 99 * u], fill=(0, 0, 0, 70))
    im.alpha_composite(sh)
    # legs (5 Nov 2026, Pavan: "why don't rex have legs?"): two thick T. rex legs with clawed feet; when Rex talks,
    # the front foot taps. The body is drawn on its own layer and lifted to stand on them.
    lift = 12 * u
    tap = max(0.0, math.sin(t * 5.0)) * 2.2 * u if talking else 0.0
    for k, (lx, foot_y) in enumerate(((47 * u, 95 * u - tap), (64 * u, 95 * u))):
        col = SKIN if k == 0 else SKIN_DARK
        d.ellipse([lx - 7 * u, 66 * u, lx + 7 * u, 84 * u], fill=col + (255,))                    # thigh
        d.polygon([(lx - 4.5 * u, 80 * u), (lx + 4.5 * u, 80 * u), (lx + 3 * u, foot_y - 2 * u),
                   (lx - 3 * u, foot_y - 2 * u)], fill=col + (255,))                              # shin
        d.rounded_rectangle([lx - 9 * u, foot_y - 4 * u, lx + 4 * u, foot_y + 1 * u], radius=2 * u,
                            fill=col + (255,))                                                    # foot, toes left
        for c in range(3):                                                                         # claws
            cx = lx - 8.5 * u + c * 3.2 * u
            d.polygon([(cx, foot_y - 0.5 * u), (cx - 2.2 * u, foot_y + 0.8 * u), (cx + 0.6 * u, foot_y + 1 * u)],
                      fill=(250, 248, 236, 255))
    body = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(body)
    # body and tail
    d.polygon([(64 * u, 60 * u), (98 * u, 86 * u), (96 * u, 92 * u), (70 * u, 88 * u)], fill=SKIN_DARK + (255,))
    d.ellipse([40 * u, 50 * u + breathe, 80 * u, 96 * u], fill=SKIN + (255,))
    d.ellipse([46 * u, 62 * u + breathe, 68 * u, 92 * u], fill=BELLY + (255,))
    # the tiny arms: they wave a little when Rex talks
    wave = math.sin(t * 6) * 3 * u if talking else 0.0
    for k, (ax, ay) in enumerate(((46 * u, 66 * u), (52 * u, 68 * u))):
        d.line([ax, ay + breathe, ax - 8 * u, ay + 4 * u + breathe - (wave if k == 0 else -wave * 0.5)],
               fill=SKIN_DARK + (255,), width=int(3 * u))
    # neck and head, nodding as it talks; the head faces left
    hy = 22 * u + nod + breathe
    d.polygon([(52 * u, 56 * u + breathe), (70 * u, 54 * u + breathe), (66 * u, hy + 26 * u), (50 * u, hy + 24 * u)],
              fill=SKIN + (255,))
    # upper head
    d.rounded_rectangle([18 * u, hy, 74 * u, hy + 22 * u], radius=10 * u, fill=SKIN + (255,))
    # lower jaw: hinged at the back, opens with the voice
    jaw = 2 * u + 9 * u * mouth
    d.polygon([(22 * u, hy + 18 * u), (70 * u, hy + 16 * u), (70 * u, hy + 24 * u), (26 * u, hy + 18 * u + jaw)],
              fill=SKIN_DARK + (255,))
    if mouth > 0.1:                                 # the inside of the mouth and two teeth
        d.polygon([(26 * u, hy + 19 * u), (66 * u, hy + 18 * u), (28 * u, hy + 18 * u + jaw * 0.85)], fill=(120, 40, 52, 255))
        for tx in (30 * u, 38 * u):
            d.polygon([(tx, hy + 19 * u), (tx + 2.4 * u, hy + 19 * u), (tx + 1.2 * u, hy + 22 * u)], fill=(250, 248, 236, 255))
    # nostril, brow ridge, a few scales
    d.ellipse([20 * u, hy + 5 * u, 23 * u, hy + 7.5 * u], fill=SKIN_DARK + (255,))
    for k in range(3):
        d.ellipse([56 * u + k * 5 * u, hy + 3 * u, 59 * u + k * 5 * u, hy + 6 * u], fill=SKIN_DARK + (200,))
    # the eye: half-lidded and slow to blink, behind round reading glasses
    ex, ey = 46 * u, hy + 9 * u
    period = 4.8 + (seed % 2) * 0.9
    ph = (t + seed * 0.29) % period
    shut = ph < 0.22
    d.ellipse([ex - 5 * u, ey - 5 * u, ex + 5 * u, ey + 5 * u], fill=EYE + (255,))
    if not shut:
        px, py = ex + look[0] * 2.2 * u, ey + 1 * u + look[1] * 1.5 * u
        d.ellipse([px - 2.4 * u, py - 2.4 * u, px + 2.4 * u, py + 2.4 * u], fill=PUPIL + (255,))
    lid = 9.5 * u if shut else (4.2 * u if not talking else 2.8 * u)    # heavier lids when it isn't talking
    d.rectangle([ex - 6 * u, ey - 6 * u, ex + 6 * u, ey - 6 * u + lid], fill=SKIN + (255,))
    d.arc([ex - 6.5 * u, ey - 8 * u, ex + 6.5 * u, ey - 1 * u], 200, 340, fill=SKIN_DARK + (255,), width=int(1.6 * u))
    d.ellipse([ex - 7 * u, ey - 7 * u, ex + 7 * u, ey + 7 * u], outline=GLASS + (255,), width=int(1.2 * u))
    d.line([ex + 7 * u, ey - 1 * u, ex + 14 * u, ey - 3 * u], fill=GLASS + (255,), width=int(1.2 * u))
    im.alpha_composite(body, dest=(0, 0), source=(0, int(lift)))     # the body stands on the legs
    return im.resize((size, size), Image.LANCZOS)
