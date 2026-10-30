"""The daily Reel: a beat-synced kinetic edit, 1080x1920, about 20 seconds, with the original music from music.py.

The music is generated, so the beat grid is known exactly: every cut lands on a kick, words arrive on the beat,
and the key figure counts up. Structure (100 BPM, one bar = 2.4 s):
  bar 1      hook: the day's headline, word by word
  bars 2-6   one story per bar: number and topic, title, then its figure counting up or a marker sweep
  bar 7      "Every claim checked against its source."
  bar 8+     end card: where to read it, who to follow
Frames are drawn with Pillow and piped straight into ffmpeg (needs ffmpeg on the PATH)."""
from __future__ import annotations

import math
import re
import subprocess
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from .carousel import CAT_NAMES, THEMES, key_figure, marker_underline, mark, plan, short_figure, wrap
from .music import BAR, BEAT, write_wav
from .social import plain
from .visuals import _font

W, H, FPS = 1080, 1920, 30
M = 96                       # side margin; Instagram's buttons sit on the right, so text stays left of ~960
TOP, BOTTOM = 330, 1450      # safe band clear of the caption and profile overlays


def ease(x: float) -> float:
    x = min(max(x, 0.0), 1.0)
    return 1 - (1 - x) ** 3


def background(theme: str, glow, corner: str):
    th = THEMES[theme]
    img = Image.new("RGB", (W, H), th["bg"])
    if glow:
        layer = Image.new("RGB", (W, H), th["bg"])
        cx, cy = {"top-right": (W - 80, 260), "bottom-left": (100, H - 300), "centre": (W // 2, H // 2)}[corner]
        k = (0.30 if glow[2] > 150 else 0.18) if theme == "night" else 0.12
        ImageDraw.Draw(layer).ellipse([cx - 640, cy - 560, cx + 640, cy + 560],
                                      fill=tuple(int(th["bg"][j] + (glow[j] - th["bg"][j]) * k) for j in range(3)))
        img = Image.blend(img, layer.filter(ImageFilter.GaussianBlur(190)), 1.0)
    d = ImageDraw.Draw(img)
    for x in range(40, W, 40):
        for y in range(40, H, 40):
            d.point((x, y), fill=th["dot"])
    return img


class Words:
    """A block of text laid out once, revealed word by word: each word rises 28 px and fades in over 0.2 s."""

    def __init__(self, d, text, font, size, x, y, max_w, lead=1.06):
        self.items = []
        yy = y
        for line in wrap(d, text, font, max_w):
            xx = x
            for word in line.split(" "):
                self.items.append((word, xx, yy))
                xx += d.textlength(word + " ", font=font)
            yy += int(size * lead)
        self.font, self.bottom = font, yy
        self.last_line_w = (xx - x) if self.items else 0

    def draw(self, layer_d, t, start, per_word, colour):
        for k, (word, x, y) in enumerate(self.items):
            p = ease((t - start - k * per_word) / 0.2)
            if p <= 0:
                continue
            layer_d.text((x, y + (1 - p) * 28), word, font=self.font, fill=colour + (int(255 * p),))


def _count(fig: str, p: float) -> str:
    """"$7.6B" at progress p in [0, 1]: the number climbs, prefix and suffix stay."""
    m = re.match(r"^(\D*)(\d+(?:\.\d+)?)(.*)$", fig)
    if not m:
        return fig
    pre, num, suf = m.groups()
    dec = len(num.split(".")[1]) if "." in num else 0
    return f"{pre}{float(num) * ease(p):.{dec}f}{suf}"


def render_frames(post: dict, site: dict, date_label: str, seconds: float):
    """Yield RGB frames as bytes."""
    items = plan(post)[:5]
    probe = ImageDraw.Draw(Image.new("RGB", (8, 8)))
    rng = np.random.default_rng(5)
    grains = [rng.normal(0, 5, (H, W, 1)).astype(np.int16)]          # one static grain plate: film texture without the bitrate

    # scenes: (start, end, kind, data)
    scenes = [(0, BAR, "hook", None)]
    for k, it in enumerate(items):
        scenes.append((BAR * (k + 1), BAR * (k + 2), "story", (k, it)))
    scenes.append((BAR * (len(items) + 1), BAR * (len(items) + 2), "trust", None))
    scenes.append((BAR * (len(items) + 2), seconds, "end", None))

    bgs = {}

    def bg_for(i, kind, data):
        if i not in bgs:
            if kind == "story":
                k, it = data
                theme = "paper" if k % 2 == 0 else "night"
                c = THEMES[theme]["topic"].get(it["section"].get("category"), THEMES[theme]["accent"])
                bgs[i] = (theme, background(theme, c, "top-right" if k % 2 else "bottom-left"))
            else:
                bgs[i] = ("night", background("night", (139, 156, 255) if kind != "end" else (255, 184, 107),
                                              "top-right" if kind == "hook" else "centre"))
        return bgs[i]

    # lay out text once per scene
    head = plain(post["headline"])
    hsize = 148
    while True:
        hf = _font("serif", hsize)
        lines = wrap(probe, head, hf, W - 2 * M - 40)
        if (len(lines) <= 5 and max(probe.textlength(x, font=hf) for x in lines) <= W - 2 * M - 40) or hsize <= 84:
            break
        hsize -= 8
    hook = Words(probe, head, hf, hsize, M, 600 + max(0, (5 - len(lines)) * hsize // 2), W - 2 * M - 40)
    story_words = []
    for k, it in enumerate(items):
        title = plain(it["section"]["title"])
        ts = 132
        while True:
            tf = _font("serif", ts)
            tl = wrap(probe, title, tf, W - 2 * M - 40)
            if (len(tl) <= 4 and max(probe.textlength(x, font=tf) for x in tl) <= W - 2 * M - 40) or ts <= 84:
                break
            ts -= 6
        story_words.append((Words(probe, title, tf, ts, M, 700 + max(0, (4 - len(tl)) * ts // 3), W - 2 * M - 40), ts))
    tf_trust = _font("serif", 140)
    trust = Words(probe, "Every claim checked against its source.", tf_trust, 140, M, 680, W - 2 * M - 40)

    total = int(seconds * FPS)
    for fi in range(total):
        t = fi / FPS
        i = next(j for j, s in enumerate(scenes) if s[0] <= t < s[1] or j == len(scenes) - 1)
        start, end, kind, data = scenes[i]
        theme, bg = bg_for(i, kind, data)
        T = THEMES[theme]
        frame = bg.copy()
        layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        ld = ImageDraw.Draw(layer)
        lt = t - start

        if kind == "hook":
            a = ease(lt / 0.3)
            mark(ld, M + 34, 420, 34, T["accent"] + (int(255 * a),))
            ld.text((M + 88, 398), site["name"].upper(), font=_font("sans_bold", 42), fill=T["accent"] + (int(255 * a),))
            ld.text((M, 476), date_label, font=_font("sans", 40), fill=T["muted"] + (int(255 * a),))
            per = min(BEAT / 2, (BAR - 0.6) / max(1, len(hook.items)))
            hook.draw(ld, lt, 0.15, per, T["ink"])
            p = ease((lt - 0.15 - per * len(hook.items)) / 0.35)
            if p > 0:
                marker_underline(ld, M - 6, M - 6 + (min(hook.last_line_w, W - 2 * M)) * p, hook.bottom + 10,
                                 T["accent"] + (255,), seed=1)

        elif kind == "story":
            k, it = data
            sec = it["section"]
            c = T["topic"].get(sec.get("category"), T["accent"])
            p0 = ease(lt / 0.25)
            ld.text((M, 400 - (1 - p0) * 40), f"{k + 1:02d}", font=_font("serif", 190), fill=c + (int(255 * p0),))
            label = CAT_NAMES.get(sec.get("category", ""), "").upper()
            lf = _font("sans_bold", 34)
            lw = ld.textlength(label, font=lf)
            ld.rounded_rectangle([W - M - lw - 60 + (1 - p0) * 60, 470, W - M + (1 - p0) * 60, 540], radius=35,
                                 fill=c + (int(255 * p0),))
            ld.text((W - M - lw - 30 + (1 - p0) * 60, 482), label, font=lf, fill=T["bg"] + (int(255 * p0),))
            words, ts = story_words[k]
            per = min(0.09, (BEAT * 1.4) / max(1, len(words.items)))
            words.draw(ld, lt, BEAT * 0.25, per, T["ink"])
            y = words.bottom + 40
            fig = key_figure(it["line"]) if it["kind"] in ("number", "chart") else ""
            if it["kind"] == "chart":
                ch = post["chart"]
                b0 = ch["bars"][0]
                unit = ch.get("unit", "")
                fig = ("$" if unit.startswith("$") else "") + f"{b0['value']:g}" + ("B" if "billion" in unit else "")
            p = (lt - BEAT * 2) / (BEAT * 0.9)
            if fig and p > 0:
                big = short_figure(fig)
                ld.text((M - 6, y), _count(big, p), font=_font("serif", 270), fill=c + (255,))
            elif p > 0:
                marker_underline(ld, M - 6, M - 6 + min(words.last_line_w, W - 2 * M) * ease(p), words.bottom + 6,
                                 c + (255,), seed=k + 3)

        elif kind == "trust":
            mark(ld, M + 70, 500, 70, T["accent"] + (int(255 * ease(lt / 0.3)),))
            trust.draw(ld, lt, 0.1, BEAT / 2, T["ink"])
            p = ease((lt - 0.1 - BEAT / 2 * len(trust.items)) / 0.3)
            if p > 0:
                ld.text((M, trust.bottom + 50), "A second model fact-checks every sentence.", font=_font("sans", 46),
                        fill=T["ink2"] + (int(255 * p),))

        else:   # end card
            a = ease(lt / 0.35)
            r = 120
            mark(ld, W // 2, 640, int(r * (0.6 + 0.4 * a)), T["accent"] + (int(255 * a),))
            for text, font, colour, y, delay in (
                    ("Full five-minute read", _font("serif", 100), T["ink"], 880, 0.15),
                    ("link in bio", _font("serif", 100), T["accent"], 992, 0.3),
                    (re.sub(r"^https?://|/$", "", site["base_url"]), _font("sans", 50), T["muted"], 1150, 0.45),
                    ("Follow for tomorrow's five", _font("sans_bold", 56), T["ink"], 1320, 0.6)):
                p = ease((lt - delay) / 0.3)
                tw = ld.textlength(text, font=font)
                ld.text(((W - tw) / 2, y + (1 - p) * 24), text, font=font, fill=colour + (int(255 * p),))

        frame.paste(layer, (0, 0), layer)
        # cut flash: a 2-frame brightness kick on every scene change, in time with the kick drum
        arr = np.asarray(frame).astype(np.int16) + grains[0]
        if i > 0 and lt < 2 / FPS:
            arr = arr + 18
        yield np.clip(arr, 0, 255).astype(np.uint8).tobytes()


def reel(post: dict, site: dict, date_label: str, out: Path) -> Path:
    items = min(5, len(post["sections"]))
    bars = items + 3
    wav, _ = write_wav(out.with_suffix(".wav"), bars=bars)
    seconds = bars * BAR + 1.2
    cmd = ["ffmpeg", "-y", "-loglevel", "error",
           "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
           "-i", str(wav),
           "-af", "loudnorm=I=-14:TP=-1.5:LRA=9,aresample=48000",
           "-c:v", "libx264", "-preset", "slow", "-crf", "19", "-maxrate", "14M", "-bufsize", "28M", "-pix_fmt", "yuv420p", "-profile:v", "high",
           "-c:a", "aac", "-b:a", "256k", "-ar", "48000", "-t", f"{seconds:.2f}", "-movflags", "+faststart", str(out)]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for frame in render_frames(post, site, date_label, seconds):
        proc.stdin.write(frame)
    proc.stdin.close()
    if proc.wait() != 0:
        raise RuntimeError("ffmpeg failed to encode the reel")
    wav.unlink(missing_ok=True)
    return out
