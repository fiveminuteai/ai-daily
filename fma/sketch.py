"""Hand-drawn doodles for the story Reels: wobbly pen strokes that draw themselves on, then "boil" (redrawn with
fresh wobble four times a second, the classic hand-drawn animation look). Drawn in code, so the style is the same
every day, nothing is licensed, and no picture can show something that didn't happen.

A doodle is a list of strokes; a stroke is a list of points in a 0..1 box. `pick()` chooses doodles for a story's
card from its words."""
from __future__ import annotations

import math
import random
import re

# ---------------------------------------------------------------- stroke helpers (0..1 box coordinates)


def line(*pts):
    return [tuple(p) for p in pts]


def arc(cx, cy, rx, ry, a0, a1, n=28):
    return [(cx + rx * math.cos(math.radians(a0 + (a1 - a0) * k / n)),
             cy + ry * math.sin(math.radians(a0 + (a1 - a0) * k / n))) for k in range(n + 1)]


def circle(cx, cy, r, ry=None, overshoot=25):
    """A hand-drawn loop: it overshoots its start, as a pen does."""
    return arc(cx, cy, r, ry or r, -100, 260 + overshoot, n=40)


def rect(x0, y0, x1, y1):
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0 + 0.01)]


def arrow(x0, y0, x1, y1, head=0.12):
    ang = math.atan2(y1 - y0, x1 - x0)
    h1 = (x1 - head * math.cos(ang - 0.5), y1 - head * math.sin(ang - 0.5))
    h2 = (x1 - head * math.cos(ang + 0.5), y1 - head * math.sin(ang + 0.5))
    return [line((x0, y0), (x1, y1)), line(h1, (x1, y1), h2)]


# ---------------------------------------------------------------- the doodle library
# Each entry: strokes in a square box; "hi" marks strokes drawn in the story's colour.

def _padlock_cracked():
    return [line(*rect(0.22, 0.45, 0.78, 0.92)),
            arc(0.5, 0.45, 0.2, 0.3, 180, 360),
            circle(0.5, 0.63, 0.055),
            line((0.5, 0.69), (0.5, 0.79)),
            {"hi": line((0.22, 0.58), (0.36, 0.64), (0.31, 0.72), (0.47, 0.78), (0.43, 0.86))}]


def _package_update():
    return [line((0.2, 0.42), (0.5, 0.3), (0.8, 0.42), (0.5, 0.54), (0.2, 0.42)),
            line((0.2, 0.42), (0.2, 0.78), (0.5, 0.9), (0.8, 0.78), (0.8, 0.42)),
            line((0.5, 0.54), (0.5, 0.9)),
            *[{"hi": s} for s in arrow(0.5, 0.02, 0.5, 0.25, 0.08)]]


def _key_tunnel():
    return [circle(0.22, 0.5, 0.11),
            line((0.33, 0.5), (0.7, 0.5)), line((0.6, 0.5), (0.6, 0.6)), line((0.68, 0.5), (0.68, 0.58)),
            {"hi": arc(0.82, 0.5, 0.12, 0.3, 90, 270)},
            *[{"hi": s} for s in arrow(0.76, 0.2, 0.98, 0.2, 0.07)]]


def _removed():
    return [line(*rect(0.22, 0.25, 0.78, 0.85)), line((0.3, 0.4), (0.7, 0.4)), line((0.3, 0.52), (0.62, 0.52)),
            line((0.3, 0.64), (0.66, 0.64)),
            {"hi": line((0.12, 0.15), (0.88, 0.95))}, {"hi": line((0.88, 0.15), (0.12, 0.95))}]


def _magnifier():
    return [circle(0.42, 0.42, 0.24), line((0.59, 0.59), (0.88, 0.88)), line((0.62, 0.56), (0.91, 0.85)),
            {"hi": line((0.3, 0.42), (0.39, 0.52), (0.56, 0.32))}]


def _satellite():
    return [line(*rect(0.4, 0.4, 0.6, 0.6)), line(*rect(0.06, 0.44, 0.34, 0.56)), line(*rect(0.66, 0.44, 0.94, 0.56)),
            line((0.34, 0.5), (0.4, 0.5)), line((0.6, 0.5), (0.66, 0.5)),
            {"hi": arc(0.5, 0.82, 0.45, 0.12, 200, 340)}]


def _graduate_ghost():
    return [line((0.15, 0.3), (0.5, 0.15), (0.85, 0.3), (0.5, 0.45), (0.15, 0.3)), line((0.82, 0.31), (0.82, 0.5)),
            {"hi": line((0.3, 0.92), *arc(0.5, 0.62, 0.2, 0.22, 180, 360)[1:], (0.7, 0.92), (0.63, 0.85), (0.57, 0.92),
                        (0.5, 0.85), (0.43, 0.92), (0.37, 0.85), (0.3, 0.92))},
            circle(0.43, 0.62, 0.025), circle(0.57, 0.62, 0.025)]


def _robot():
    return [line(*rect(0.25, 0.3, 0.75, 0.75)), line((0.5, 0.3), (0.5, 0.16)), circle(0.5, 0.13, 0.04),
            circle(0.4, 0.48, 0.05), circle(0.6, 0.48, 0.05), {"hi": line((0.38, 0.63), (0.62, 0.63))}]


def _server_leak():
    return [line(*rect(0.25, 0.1, 0.75, 0.32)), line(*rect(0.25, 0.36, 0.75, 0.58)), circle(0.66, 0.21, 0.025),
            circle(0.66, 0.47, 0.025),
            {"hi": line((0.75, 0.47), (0.88, 0.47), (0.88, 0.75))}, {"hi": circle(0.88, 0.86, 0.04)}]


def _money():
    return [circle(0.5, 0.5, 0.36), {"hi": line((0.6, 0.34), (0.42, 0.34), (0.4, 0.48), (0.6, 0.52), (0.58, 0.66),
                                               (0.4, 0.66))}, {"hi": line((0.5, 0.24), (0.5, 0.76))}]


def _gavel():
    """A judge's gavel, tilted, about to hit its block, with two impact marks."""
    head = [(0.18, 0.32), (0.44, 0.12), (0.58, 0.3), (0.32, 0.5), (0.18, 0.32)]
    return [line(*head), line((0.24, 0.27), (0.38, 0.45)), line((0.4, 0.17), (0.52, 0.34)),
            line((0.45, 0.4), (0.78, 0.78)), line((0.5, 0.36), (0.82, 0.74)),
            line(*rect(0.15, 0.8, 0.6, 0.92)),
            {"hi": line((0.66, 0.62), (0.8, 0.58))}, {"hi": line((0.62, 0.7), (0.72, 0.8))}]


def _chip():
    pins = []
    for k in range(4):
        y = 0.32 + k * 0.12
        pins += [line((0.12, y), (0.25, y)), line((0.75, y), (0.88, y))]
    return [line(*rect(0.25, 0.25, 0.75, 0.75)), *pins, {"hi": line(*rect(0.38, 0.38, 0.62, 0.62))}]


def _spark():
    return [{"hi": line((0.5, 0.1), (0.56, 0.44), (0.9, 0.5), (0.56, 0.56), (0.5, 0.9), (0.44, 0.56), (0.1, 0.5),
                        (0.44, 0.44), (0.5, 0.1))}]


LIBRARY = {"padlock": _padlock_cracked, "package": _package_update, "key": _key_tunnel, "removed": _removed,
           "magnifier": _magnifier, "satellite": _satellite, "graduate": _graduate_ghost, "robot": _robot,
           "server": _server_leak, "money": _money, "gavel": _gavel, "chip": _chip, "spark": _spark}

# first match wins; the words come from the card line the doodle sits under
CUES = [("removed", r"\b(removed|pulled|deleted|banned|shut down)\b"),
        ("key", r"\b(ssh|key|keys|password|login|logins|credential|tunnel)\b"),
        ("padlock", r"\b(hack|hacked|backdoor|breach|malicious|compromised|attack|security)\b"),
        ("package", r"\b(update|version|release|released|ships|shipped|launch)\b"),
        ("magnifier", r"\b(check|review|audit|investigat|found|analysis)\w*"),
        ("satellite", r"\b(satellite|orbit|space)\b"),
        ("graduate", r"\b(student|students|college|university|school)\b"),
        ("money", r"[$€£₹]|\b(million|billion|price|cost|funding|crypto|seized)\b"),
        ("gavel", r"\b(charged|court|law|lawsuit|regulat|prosecutor|fine|fined)\w*"),
        ("server", r"\b(data|leak|leaked|sent|system|server|database)\b"),
        ("chip", r"\b(chip|chips|gpu|gpus|tpu|tpus|nvidia)\b"),
        ("robot", r"\b(agent|agents|robot|model|ai)\b")]


def pick(text: str, avoid: set[str] | None = None) -> str:
    low = text.lower()
    for name, pat in CUES:
        if name not in (avoid or set()) and re.search(pat, low):
            return name
    return "spark"


# ---------------------------------------------------------------- drawing

def _length(pts):
    return sum(math.dist(a, b) for a, b in zip(pts, pts[1:]))


def _wobble(pts, rng, amount):
    """Hand tremor: nudge every point a little, more on long straight runs (they get midpoints added)."""
    out = []
    for a, b in zip(pts, pts[1:]):
        steps = max(1, int(math.dist(a, b) / 0.08))
        for k in range(steps):
            t = k / steps
            out.append((a[0] + (b[0] - a[0]) * t + rng.uniform(-amount, amount),
                        a[1] + (b[1] - a[1]) * t + rng.uniform(-amount, amount)))
    out.append((pts[-1][0] + rng.uniform(-amount, amount), pts[-1][1] + rng.uniform(-amount, amount)))
    return out


def _partial(pts, frac):
    if frac >= 1:
        return pts
    total, acc, out = _length(pts), 0.0, [pts[0]]
    target = total * frac
    for a, b in zip(pts, pts[1:]):
        d = math.dist(a, b)
        if acc + d >= target:
            t = (target - acc) / d if d else 0
            out.append((a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t))
            return out
        out.append(b)
        acc += d
    return out


CUTOUT = [(240, 110, 80), (38, 150, 140), (242, 190, 64), (122, 104, 220)]   # coral, teal, mustard, violet paper


def _closed(pts) -> bool:
    return len(pts) > 3 and math.dist(pts[0], pts[-1]) < 0.04


def burst(ld, box, t, colour, outline=(20, 20, 20, 255), seed=0, grow=0.3):
    """Comic starburst behind a doodle."""
    if t <= 0:
        return
    x, y, size = box
    k = 1 - (1 - min(1.0, t / grow)) ** 3
    cx, cy = x + size * 0.5, y + size * 0.52
    rng = random.Random(seed)
    pts = []
    for n in range(28):
        a = math.radians(n * 360 / 28 + (int(t * 4) % 2) * 3)
        r = size * (0.52 if n % 2 == 0 else 0.36) * k * rng.uniform(0.94, 1.06)
        pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    ld.polygon(pts, fill=colour, outline=outline, width=8)


def paper(ld, box, t, colour, seed=0, grow=0.35):
    """A cut-paper disc behind a doodle, with a soft shadow, sliding up into place."""
    if t <= 0:
        return
    x, y, size = box
    k = 1 - (1 - min(1.0, t / grow)) ** 3
    r = size * 0.47
    cx, cy = x + size * 0.5, y + size * 0.52 + (1 - k) * 120
    ld.ellipse([cx - r + 12, cy - r + 14, cx + r + 12, cy + r + 14], fill=(0, 0, 0, int(45 * k)))
    ld.ellipse([cx - r, cy - r, cx + r, cy + r], fill=colour[:3] + (int(255 * k),))


def blob(ld, box, t, colour, seed=0, grow=0.35):
    """A hand-painted colour patch behind a doodle: an uneven round shape that pops in, then boils."""
    if t <= 0:
        return
    x, y, size = box
    rng = random.Random(seed * 7 + int(t * 4))
    k = min(1.0, t / grow)
    k = 1 - (1 - k) ** 3
    cx, cy, r = x + size * 0.5, y + size * 0.52, size * 0.46 * k
    pts = []
    for a in range(0, 360, 15):
        rr = r * (0.86 + 0.14 * math.sin(math.radians(a * 3 + seed * 40)) + rng.uniform(-0.03, 0.03))
        pts.append((cx + rr * math.cos(math.radians(a)), cy + rr * 0.92 * math.sin(math.radians(a))))
    ld.polygon(pts, fill=colour)


def draw(ld, name: str, box: tuple[float, float, float], t: float, ink, hi, width: int = 11, draw_time: float = 1.1,
         seed: int = 0, mode: str = "pen"):
    """Draw doodle `name` into box (x, y, size) at time t (seconds since it started). Strokes draw on one after
    another over `draw_time`, then boil: the wobble is re-rolled 4 times a second.
    mode: "pen" (notebook doodle), "chalk" (grainy multi-pass strokes), "cutout" (closed shapes become filled paper
    pieces with a shadow), "comic" (thick black outlines, closed shapes filled flat)."""
    if mode in ("cutout", "comic"):
        return _draw_filled(ld, name, box, t, ink, hi, seed, mode, draw_time)
    if t <= 0:
        return
    x, y, size = box
    strokes = LIBRARY[name]()
    rng = random.Random(seed * 1000 + int(t * 4))           # boil
    lengths = [_length(s["hi"] if isinstance(s, dict) else s) for s in strokes]
    total = sum(lengths) or 1
    shown = total * min(1.0, t / draw_time)
    for s, ln in zip(strokes, lengths):
        if shown <= 0:
            break
        pts, colour = (s["hi"], hi) if isinstance(s, dict) else (s, ink)
        frac = min(1.0, shown / ln) if ln else 1.0
        shown -= ln
        part = _partial(_wobble(pts, rng, 0.008), frac)
        if len(part) < 2:
            continue
        xy = [(x + px * size, y + py * size) for px, py in part]
        if mode == "chalk":                 # three thin dusty passes, each with gaps where the chalk skipped
            for k in range(3):
                pr = random.Random(seed * 31 + k)
                pts2 = [(a + pr.uniform(-3, 3), b + pr.uniform(-3, 3)) for a, b in xy]
                for i in range(len(pts2) - 1):
                    if pr.random() > 0.12:
                        ld.line([pts2[i], pts2[i + 1]], fill=colour[:3] + (205,), width=7)
            continue
        ld.line(xy, fill=colour, width=width, joint="curve")
        ld.line([(a + 1.5, b + 1.0) for a, b in xy], fill=colour[:3] + (int(colour[3] * 0.35),), width=max(2, width // 3))


def _draw_filled(ld, name, box, t, ink, hi, seed, mode, draw_time):
    """Cut-out and comic doodles: shapes pop in one after another (scale from their centre) instead of being traced."""
    x, y, size = box
    strokes = LIBRARY[name]()
    rng = random.Random(seed * 1000 + int(t * 4))
    n = len(strokes)
    for i, s in enumerate(strokes):
        hi_stroke = isinstance(s, dict)
        pts = s["hi"] if hi_stroke else s
        k = min(1.0, max(0.0, (t - draw_time * i / max(1, n)) / 0.25))
        if k <= 0:
            continue
        k = 1 - (1 - k) ** 3 * (1 - 0.6 * k)               # quick pop with a touch of overshoot feel
        cx = sum(p[0] for p in pts) / len(pts)
        cy = sum(p[1] for p in pts) / len(pts)
        jig = 0.004 if mode == "comic" else 0.0
        xy = [(x + (cx + (px - cx) * k + rng.uniform(-jig, jig)) * size,
               y + (cy + (py - cy) * k + rng.uniform(-jig, jig)) * size) for px, py in pts]
        if mode == "cutout":
            if _closed(pts):
                fill = CUTOUT[(i + seed) % len(CUTOUT)] + (255,) if not hi_stroke else hi
                ld.polygon([(a + 9, b + 11) for a, b in xy], fill=(0, 0, 0, 50))
                ld.polygon(xy, fill=fill)
            else:
                ld.line([(a + 6, b + 8) for a, b in xy], fill=(0, 0, 0, 45), width=13, joint="curve")
                ld.line(xy, fill=hi if hi_stroke else ink, width=13, joint="curve")
        else:   # comic
            if _closed(pts):
                ld.polygon(xy, fill=hi if hi_stroke else (255, 255, 255, 255))
                ld.line(xy + [xy[0]], fill=(15, 15, 15, 255), width=12, joint="curve")
            else:
                ld.line(xy, fill=(15, 15, 15, 255), width=16, joint="curve")
                if hi_stroke:
                    ld.line(xy, fill=hi, width=8, joint="curve")


def ring(ld, bbox, t, colour, seed=0, width=5, draw_time=0.45, mode="pen"):
    """A quick hand-drawn ellipse around a word's box (x0, y0, x1, y1), drawn on, then boiling."""
    if t <= 0:
        return
    x0, y0, x1, y1 = bbox
    rng = random.Random(seed * 1000 + int(t * 4))
    pts = _wobble(circle(0.5, 0.5, 0.5, 0.5, overshoot=35), rng, 0.012)
    part = _partial(pts, min(1.0, t / draw_time))
    pad_x, pad_y = (x1 - x0) * 0.08 + 12, (y1 - y0) * 0.16 + 6
    xy = [(x0 - pad_x + px * (x1 - x0 + 2 * pad_x), y0 - pad_y + py * (y1 - y0 + 2 * pad_y)) for px, py in part]
    if len(xy) < 2:
        return
    if mode == "chalk":
        for k in range(2):
            ld.line([(a + k * 2, b - k * 2) for a, b in xy], fill=colour[:3] + (160,), width=3, joint="curve")
    elif mode == "cutout":                 # a paper sticker behind the number instead of a ring
        p = min(1.0, t / 0.3)
        ld.rounded_rectangle([x0 - 10, y0 + 2, x0 - 10 + (x1 - x0 + 20) * p, y1 + 6], radius=10,
                             fill=colour[:3] + (90,))
    elif mode == "comic":
        ld.line(xy, fill=colour, width=width + 4, joint="curve")
    else:
        ld.line(xy, fill=colour, width=width, joint="curve")
