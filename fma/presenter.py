"""The Reels' presenter: an original cartoon news-anchor robot, drawn in code in the paper cut-out look, so there is
nothing to license and no real person's likeness. Its mouth follows the narrator's voice frame by frame; it blinks,
bobs on the beat and glances at the line being read.

Drawn at 2x on its own canvas and scaled down, so the edges are smooth at 1080x1920."""
from __future__ import annotations

import math

from PIL import Image, ImageDraw


# Fixed brand colours: yellow head, navy face-screen, teal jacket, coral tie (4 Nov 2026: taking them from the
# Reel's palette made the face vanish on the dark "dusk" palette).
COLOURS = {"head": (242, 190, 64), "ink": (30, 35, 60), "body": (38, 150, 140), "accent": (232, 96, 66),
           "light": (255, 251, 242)}


def _shade(rgb, k):
    return tuple(max(0, min(255, int(v * k))) for v in rgb)


def draw(size: int, t: float, mouth: float, colours: dict, seed: int = 0, beat: float = 0.6,
         talking: bool = True) -> Image.Image:
    """One frame of the presenter, `size` px square, RGBA. `mouth` is 0..1 from voice.envelope."""
    S = size * 2
    im = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    u = S / 100                                    # one unit = 1% of the box
    body_c, face_c, ink, accent, light = (colours["body"], colours["head"], colours["ink"], colours["accent"],
                                          colours.get("light", (255, 251, 242)))
    shadow = (0, 0, 0, 46)
    off = 2.2 * u                                  # cut-out paper: every piece casts the same small shadow

    bob = (math.sin(2 * math.pi * t / beat) * 1.1 * u) if talking else math.sin(t * 1.6) * 0.6 * u
    tilt = math.sin(t * 0.9 + seed) * 1.4 * u

    # shoulders and jacket
    jacket = [(14 * u, 100 * u), (20 * u, 74 * u), (34 * u, 66 * u), (66 * u, 66 * u), (80 * u, 74 * u), (86 * u, 100 * u)]
    d.polygon([(x + off, y + off) for x, y in jacket], fill=shadow)
    d.polygon(jacket, fill=body_c + (255,))
    d.polygon([(42 * u, 66 * u), (50 * u, 80 * u), (58 * u, 66 * u)], fill=light + (255,))        # shirt
    d.polygon([(47.5 * u, 70 * u), (52.5 * u, 70 * u), (54 * u, 92 * u), (50 * u, 97 * u), (46 * u, 92 * u)],
              fill=accent + (255,))                                                                 # tie
    d.ellipse([24 * u, 76 * u, 31 * u, 83 * u], fill=accent + (255,))                               # lapel pin

    # neck
    d.rounded_rectangle([44 * u, 58 * u + bob, 56 * u, 68 * u], radius=2 * u, fill=_shade(face_c, 0.82) + (255,))

    # head: a rounded screen-face on a body, tilting slightly as it talks
    hx0, hy0, hx1, hy1 = 24 * u + tilt, 14 * u + bob, 76 * u + tilt, 60 * u + bob
    d.rounded_rectangle([hx0 + off, hy0 + off, hx1 + off, hy1 + off], radius=12 * u, fill=shadow)
    d.rounded_rectangle([hx0, hy0, hx1, hy1], radius=12 * u, fill=face_c + (255,))
    # antenna with a light that pulses on the beat
    ax = (hx0 + hx1) / 2
    d.line([ax, hy0, ax + tilt * 0.6, hy0 - 8 * u], fill=_shade(face_c, 0.7) + (255,), width=int(1.6 * u))
    glow = 0.5 + 0.5 * math.cos(2 * math.pi * t / beat)
    r = (2.6 + 0.8 * glow) * u
    d.ellipse([ax + tilt * 0.6 - r, hy0 - 8 * u - r, ax + tilt * 0.6 + r, hy0 - 8 * u + r], fill=accent + (255,))
    # ear pieces
    for ex in (hx0 - 3 * u, hx1 - 1 * u):
        d.rounded_rectangle([ex, hy0 + 17 * u, ex + 4 * u, hy0 + 31 * u], radius=2 * u, fill=_shade(face_c, 0.75) + (255,))

    # the face screen
    sx0, sy0, sx1, sy1 = hx0 + 6 * u, hy0 + 7 * u, hx1 - 6 * u, hy1 - 7 * u
    d.rounded_rectangle([sx0, sy0, sx1, sy1], radius=8 * u, fill=ink + (255,))

    # eyes: blink every few seconds, glance up-left at the text now and then
    period = 3.7 + (seed % 3) * 0.6
    ph = (t + seed * 0.37) % period
    blink = 1.0 - (max(0.0, 1 - abs(ph - 0.09) / 0.09) if ph < 0.18 else 0.0)
    glance = -1.6 * u if math.sin(t * 0.7 + seed) > 0.55 else 0.0
    ey = sy0 + 11 * u
    for cx in (sx0 + 12 * u, sx1 - 12 * u):
        h = max(0.6 * u, 6.4 * u * blink)
        d.rounded_rectangle([cx - 3.2 * u + glance, ey - h / 2 + glance * 0.6, cx + 3.2 * u + glance,
                             ey + h / 2 + glance * 0.6], radius=3 * u, fill=light + (255,))
    # cheeks
    for cx in (sx0 + 7 * u, sx1 - 7 * u):
        d.ellipse([cx - 2.6 * u, ey + 6 * u, cx + 2.6 * u, ey + 9.4 * u], fill=accent + (130,))

    # mouth: a smile line when quiet, an opening oval that follows the voice when talking
    mx, my = (sx0 + sx1) / 2, sy1 - 9 * u
    w = 9 * u + 4.5 * u * mouth                     # wider more than taller: talking, not shocked
    h = 0.9 * u + 5.2 * u * mouth
    if h < 1.6 * u:
        d.arc([mx - w / 2, my - 3 * u, mx + w / 2, my + 2 * u], 20, 160, fill=light + (255,), width=int(1.4 * u))
    else:
        d.rounded_rectangle([mx - w / 2, my - h / 2, mx + w / 2, my + h / 2], radius=min(h, w) / 2,
                            fill=light + (255,))
        if h > 4 * u:                               # a tongue when the mouth opens wide
            d.ellipse([mx - w / 3, my + h / 2 - 2.6 * u, mx + w / 3, my + h / 2 - 0.2 * u], fill=accent + (255,))
    return im.resize((size, size), Image.LANCZOS)
