"""The duo Reel (5 Nov 2026): Spark tells the story, Doubt pushes back. A back-and-forth holds attention better than
one voice: each question opens a small gap the next line closes.

Rules that keep it honest: every fact is Spark's and comes word for word from the checked post (the card's lines
and the section's sentences); Doubt only asks questions, which state no facts.

Staging: the two stand on fixed marks and never hop. Whoever talks leans in and brightens, the other dims a little
and listens; the camera eases toward the speaker (shot, reverse shot); numbers rise into the hologram between them;
captions take the speaker's colour under a name tag."""
from __future__ import annotations

import math
import subprocess
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from . import doubt, spark, voice
from .carousel import CAT_NAMES, publishers
from .music import BAR, BEAT, write_wav
from .pulse_reel import (BG_TOP, INK, MUTED, SOURCE_Y, WASHES, YELLOW, _background, _bokeh, chunks, draw_caption,
                         figure, figure_time, hologram, sfx_track, word_times)
from .reel import FPS, H, M, W, ease
from .social import plain
from .visuals import _font

DOUBT_HI = (160, 178, 255)
PANEL_Y = 560                        # the hologram's centre: clear of Spark's head
SPARK_AT = (330, 1110, 400)          # centre x, bottom y, size
DOUBT_AT = (785, 1100, 320)
GAP = {"spark": 0.42, "doubt": 0.3}  # Doubt comes in quick; Spark takes a breath before the answer
VOICES = {"spark": "spark-neutral", "doubt": "doubt"}


def plan(script: list[tuple[str, str]]) -> dict:
    """Speak the script, line by line, into one track per speaker (each mouth follows its own voice)."""
    lead, t, lines, clips = 0.25, 0.0, [], []
    for who, text in script:
        s = voice.say(plain(text), voice=VOICES[who])
        dur = len(s) / voice.SR
        lines.append({"who": who, "text": text, "start": t, "said": dur, "end": t + lead + dur + GAP[who]})
        clips.append((who, t + lead, s))
        t = lines[-1]["end"]
    seconds = t + 1.6
    tracks = {w: np.zeros(int((seconds + 1) * voice.SR), np.float32) for w in VOICES}
    for who, at, s in clips:
        i = int(at * voice.SR)
        tracks[who][i:i + len(s)] += s
    peak = max(float(np.abs(tr).max()) for tr in tracks.values()) or 1.0
    for w in tracks:
        tracks[w] = tracks[w] / peak * 0.9
    return {"lines": lines, "seconds": seconds, "lead": lead, "tracks": tracks,
            "mouth": {w: voice.envelope(tr, FPS) for w, tr in tracks.items()}}


def render_frames(post: dict, section: dict, n: int, site: dict, pl: dict):
    lines, lead = pl["lines"], pl["lead"]
    for ln in lines:
        timed = word_times(ln["text"], ln["said"], lead)
        ln["groups"] = chunks(timed)
        ln["fig"] = figure(ln["text"]) if ln["who"] == "spark" else ""
        ln["fig_at"] = figure_time(timed, ln["fig"]) if ln["fig"] else 0
        ln["shape"] = spark.shape_for(plain(ln["text"])) if ln["who"] == "spark" else None
    dots = _bokeh(n + 3)
    source = publishers(post, section)
    label = CAT_NAMES.get(section.get("category", ""), "").upper()
    total = int(pl["seconds"] * FPS)
    shown = {"text": lines[0]["fig"], "at": -9.0}     # the hook's number is the cover: on from frame one
    spark_shape = ["blob", lines[0]["shape"] or "blob", -9.0]

    for fi in range(total):
        tt = fi / FPS
        i = max([k for k, ln in enumerate(lines) if ln["start"] <= tt] or [0])
        ln = lines[i]
        lt = tt - ln["start"]
        speaking = ln["who"]
        last = i == len(lines) - 1
        frame = _background(tt, dots, WASHES[(i - 1) % 4], WASHES[i % 4], ease(lt / 0.6) if i else 1.0)
        layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(layer)
        d.text((M, 300), site["name"].upper(), font=_font("sans_bold", 32), fill=YELLOW + (255,))
        lf = _font("sans_bold", 30)
        lw = d.textlength(label, font=lf)
        d.rounded_rectangle([W - M - lw - 116, 290, W - M - 60, 344], radius=27, outline=INK + (200,), width=3)
        d.text((W - M - lw - 88, 299), label, font=lf, fill=INK + (230,))
        d.rounded_rectangle([M, 372, W - M - 60, 380], radius=4, fill=INK + (60,))
        d.rounded_rectangle([M, 372, M + (W - 2 * M - 60) * tt / pl["seconds"], 380], radius=4, fill=INK + (235,))

        # the number Spark is talking about rises into the hologram as it says it, and stays until the next one
        if ln["fig"] and i and lt >= ln["fig_at"] - 0.25 and shown["text"] != ln["fig"]:
            shown.update(text=ln["fig"], at=tt, off=None)
        # it powers off when Spark moves on to a line without a number (an old number under a new fact misleads);
        # while Doubt asks about it, it stays up
        if shown["text"] and speaking == "spark" and not ln["fig"] and shown.get("off") is None and i:
            shown["off"] = tt
        fade = 1.0 if shown.get("off") is None else max(0.0, 1 - (tt - shown["off"]) / 0.3)
        if fade == 0.0:
            shown.update(text="", off=None)
        if shown["text"] and not last:
            p = (tt - shown["at"]) / 0.6 * fade if fade < 1 else (tt - shown["at"]) / 0.6
            big = _font("serif", 200)
            tw = d.textlength(shown["text"], font=big)
            hologram(layer, W / 2, PANEL_Y, tw, min(p, fade * 1.0) if fade < 1 else p, tt, 680)
            q = min(1.0, p / 0.5)
            if p > 0:
                fsz = int(200 * (1.0 if q >= 1 else 0.6 + 0.4 * q + 0.12 * math.sin(math.pi * q)))
                f2 = _font("serif", fsz)
                d.text(((W - d.textlength(shown["text"], font=f2)) / 2, PANEL_Y - fsz * 0.52), shown["text"], font=f2,
                       fill=YELLOW + (int(255 * min(1, q * 2) * fade),), stroke_width=6, stroke_fill=BG_TOP + (int(255 * fade),))

        # Spark's shape follows its own lines and holds while Doubt talks
        if speaking == "spark" and ln["shape"] != spark_shape[1]:
            spark_shape[:] = [spark_shape[1], ln["shape"], tt]
        morph = ease((tt - spark_shape[2] - 0.1) / 0.4)

        for who in (("doubt", "spark") if speaking == "spark" else ("spark", "doubt")):   # the speaker on top
            talking = who == speaking
            m = pl["mouth"][who]
            mth = float(m[min(len(m) - 1, fi)]) if len(m) else 0.0
            cx, base, size = SPARK_AT if who == "spark" else DOUBT_AT
            k = ease(min(1.0, lt / 0.3))
            s = int(size * (1.0 + 0.06 * k if talking else 1.0 - 0.04 * k))
            if who == "spark":
                asked = not talking and ln["text"].rstrip().endswith("?")
                im = spark.draw(s, tt, mth, "ask" if asked else "talk", beat=BEAT, seed=n,
                                look=(0.0, 0.5) if last else (0.9, 0.0),
                                shape=spark_shape[1], shape_from=spark_shape[0], morph=morph)
            else:
                im = doubt.draw(s, tt, mth, talking, seed=n, look=(0.0, 0.5) if last else (-0.9, 0.1))
            if not talking:                                  # the listener steps back a little
                im.putalpha(im.getchannel("A").point(lambda v: v * 205 // 255))
            layer.alpha_composite(im, (int(cx - im.width / 2), int(base - im.height)))

        # caption: the speaker's name, then their words lit as they say them
        hi = YELLOW if speaking == "spark" else DOUBT_HI
        tag = "SPARK" if speaking == "spark" else "DOUBT"
        tf = _font("sans_bold", 30)
        tw = d.textlength(tag, font=tf)
        tx = W / 2 - tw / 2
        d.rounded_rectangle([tx - 20, 1146, tx + tw + 20, 1190], radius=22, fill=hi + (255,))
        d.text((tx, 1152), tag, font=tf, fill=BG_TOP + (255,))
        draw_caption(layer, ln["groups"], lt, hi=hi, y_mid=1280)
        if last:                                             # the follow button with the closing line
            fa = ease((lt - 0.6) / 0.3)
            if fa > 0:
                text = "Follow @fiveminute_ai"
                bw = d.textlength(text, font=_font("sans_bold", 44))
                press = 0.94 if 0 < lt - 2.0 < 0.16 else 1.0
                cxb, cyb = W / 2, 1440
                hw, hh = (bw / 2 + 44) * press, 46 * press
                d.rounded_rectangle([cxb - hw, cyb - hh, cxb + hw, cyb + hh], radius=46, fill=(255, 132, 96, int(255 * fa)))
                d.text((cxb, cyb), text, font=_font("sans_bold", int(44 * press)), fill=INK + (int(255 * fa),), anchor="mm")
        elif source:
            sf = _font("sans", 32)
            st = f"Source: {source}"
            d.text(((W - d.textlength(st, font=sf)) / 2, SOURCE_Y + 20), st, font=sf, fill=MUTED + (255,))

        frame.alpha_composite(layer)
        # the camera eases toward whoever is talking: a slow push-in, pulled a little to their side
        z = 1.03 + 0.02 * min(1.0, lt / 3)
        focus = W / 2 if last else (SPARK_AT[0] if speaking == "spark" else DOUBT_AT[0])
        cxv = W / 2 + (focus - W / 2) * 0.18 * ease(min(1.0, lt / 0.6))
        cw, ch = W / z, H / z
        x0 = min(max(0, cxv - cw / 2), W - cw)
        frame = frame.crop((int(x0), int((H - ch) / 2), int(x0 + cw), int((H + ch) / 2))).resize((W, H), Image.BILINEAR)
        yield frame.convert("RGB").tobytes()


def duo_reel(post: dict, section: dict, n: int, site: dict, out: Path, script: list[tuple[str, str]]) -> Path:
    pl = plan(script)
    seconds = pl["seconds"]
    out.parent.mkdir(parents=True, exist_ok=True)
    music, _ = write_wav(out.with_suffix(".m.wav"), bars=math.ceil(seconds / BAR) + 1, seed=7 + n)
    vo = voice.write_wav(out.with_suffix(".vo.wav"), pl["tracks"]["spark"] + pl["tracks"]["doubt"])
    pops = []
    for k, ln in enumerate(pl["lines"]):
        f = figure(ln["text"]) if ln["who"] == "spark" and k else ""
        if f:
            pops.append(ln["start"] + figure_time(word_times(ln["text"], ln["said"], pl["lead"]), f) - 0.25)
    pops.append(pl["lines"][-1]["start"] + 2.0)
    fx = voice.write_wav(out.with_suffix(".fx.wav"), sfx_track(seconds, [], pops))
    cmd = ["ffmpeg", "-y", "-loglevel", "error",
           "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
           "-i", str(music), "-i", str(vo), "-i", str(fx), "-filter_complex",
           "[2:a]aresample=48000,asplit=2[v][vk];[1:a]aresample=48000,volume=0.45[m];[3:a]aresample=48000[fx];"
           "[m][vk]sidechaincompress=threshold=0.02:ratio=8:attack=20:release=400[md];"
           "[md][v][fx]amix=inputs=3:weights=1 1.6 0.9:normalize=0,loudnorm=I=-14:TP=-1.5:LRA=9[a]",
           "-map", "0:v", "-map", "[a]",
           "-c:v", "libx264", "-preset", "slow", "-crf", "17", "-maxrate", "20M", "-bufsize", "40M",
           "-pix_fmt", "yuv420p", "-profile:v", "high", "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
           "-t", f"{seconds:.2f}", "-movflags", "+faststart", str(out)]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for frame in render_frames(post, section, n, site, pl):
        proc.stdin.write(frame)
    proc.stdin.close()
    if proc.wait() != 0:
        raise RuntimeError("ffmpeg failed to encode a duo reel")
    for p in (music, vo, fx):
        p.unlink(missing_ok=True)
    return out
