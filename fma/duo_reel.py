"""The duo Reel (5 Nov 2026): Spark tells the story, a guest pushes back. A back-and-forth holds attention better
than one voice: each question or joke opens a small gap the next line closes.

Rules that keep it honest: every fact is Spark's and comes from the checked post (the card's lines and the
section's sentences); the guest only asks, reacts or jokes, and states no facts.

Guests: Doubt (a sceptical cube, the regular) and Rex (a tired old T. rex in reading glasses, for power, fuel and
emissions stories). Add one to GUESTS with a draw function, a colour, a voice and a mark on the stage.

Staging: both stand on fixed marks and never hop. Whoever talks leans in and brightens, the other dims a little
and listens; the camera eases toward the speaker; numbers rise into a hologram between them; captions take the
speaker's colour under a name tag. The end is a logo card: the clock mark's five-minute slice sweeps round, Spark
says the name, the guest says the slogan."""
from __future__ import annotations

import math
import os
import subprocess
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from . import doubt, rex, spark, voice
from .carousel import CAT_NAMES, publishers
from .music import BAR, BEAT, write_wav
from .pulse_reel import (BG_TOP, INK, MUTED, SOURCE_Y, WASHES, YELLOW, _background, _bokeh, chunks, draw_caption,
                         draw_logo, fig_size, figure, figure_time, hologram, sfx_track,
                         word_times)
from .reel import FPS, H, M, W, ease
from .social import plain
from .visuals import _font

SPARK_AT = (330, 1110, 400)          # centre x, bottom y, size
PANEL_Y = 560                        # the hologram's centre: clear of Spark's head
SPARK_VOICE = os.environ.get("FMA_SPARK_VOICE", "spark-strong")   # 5 Nov 2026, Pavan: strong, opposite the guests
GUESTS = {
    "doubt": {"draw": doubt.draw, "hi": (160, 178, 255), "tag": "DOUBT", "at": (785, 1100, 320), "voice": os.environ.get("FMA_DOUBT_VOICE", "doubt-british")},
    "rex": {"draw": rex.draw, "hi": (152, 216, 140), "tag": "REX", "at": (790, 1120, 400), "voice": os.environ.get("FMA_REX_VOICE", "rex")},
}
# Silence between lines, in seconds. Was 0.55-0.67 s and dragged (5 Nov 2026, Pavan: "speech has gone slow"): a
# conversation answers fast. A "beat" tag adds a comic pause before a punchline instead.
GAP = {"spark": 0.16}
GUEST_GAP = 0.1
BEAT_PAUSE = 0.45
MAX_SECONDS = 45.0
FX = {"card", "beat", "confetti", "drop", "sweat"}


def plan(script: list[tuple], guest: str, visemes: bool = False) -> dict:
    """Speak the script into one track per speaker (each mouth follows its own voice). A line is (who, text, *tags):
    "card" puts it on the closing logo card, "beat" holds a comic pause before it, "confetti" / "drop" / "sweat" are
    the visual gags (a burst, the burst falling flat, a nervous sweat drop on the speaker)."""
    voices = {"spark": SPARK_VOICE, guest: GUESTS[guest]["voice"]}
    lead, t, lines, clips = 0.12, 0.0, [], []
    for entry in script:
        who, text, tags = entry[0], entry[1], set(entry[2:])
        assert tags <= FX, tags
        card = "card" in tags
        if "beat" in tags:
            t += BEAT_PAUSE
        s = voice.say(plain(text), voice=voices[who])
        dur = len(s) / voice.SR
        gap = GAP.get(who, GUEST_GAP)
        lines.append({"who": who, "text": text, "start": t, "said": dur, "end": t + lead + dur + gap, "card": card,
                      "tags": tags})
        clips.append((who, t + lead, s))
        t = lines[-1]["end"]
    seconds = t + 1.4
    if seconds > MAX_SECONDS:            # 5 Nov 2026, Pavan: 40-45 s at most; cut lines, never speed the voice up
        raise ValueError(f"duo script runs {seconds:.1f} s, over the {MAX_SECONDS} s cap: cut a beat")
    tracks = {w: np.zeros(int((seconds + 1) * voice.SR), np.float32) for w in voices}
    for who, at, s in clips:
        i = int(at * voice.SR)
        tracks[who][i:i + len(s)] += s
    peak = max(float(np.abs(tr).max()) for tr in tracks.values()) or 1.0
    for w in tracks:
        tracks[w] = tracks[w] / peak * 0.9
    out = {"lines": lines, "seconds": seconds, "lead": lead, "tracks": tracks, "guest": guest,
           "mouth": {w: voice.envelope(tr, FPS) for w, tr in tracks.items()}}
    if visemes:                          # real mouth shapes per line (fma/lipsync.py, Rhubarb); empty when not installed
        from .lipsync import visemes as shapes
        out["visemes"] = shapes([(who, at, s, plain(ln["text"])) for (who, at, s), ln in zip(clips, lines)], voice.SR)
    return out


CONFETTI = [(255, 214, 90), (255, 132, 96), (64, 214, 196), (148, 110, 255), (250, 250, 255)]


def confetti(layer: Image.Image, since: float, flop: float | None, seed: int) -> None:
    """A burst of confetti from the top; once the letdown line starts (`flop` s ago) it drops to the floor and fades,
    which is the joke."""
    rnd = np.random.default_rng(seed + 11)
    d = ImageDraw.Draw(layer)
    n = 120
    ang = rnd.uniform(-math.pi * 0.92, -math.pi * 0.08, n)           # a popper: fired upward, fanning out
    speed = rnd.uniform(900, 2100, n)
    vx, vy = np.cos(ang) * speed, np.sin(ang) * speed
    spin, cols = rnd.uniform(0, 6.3, n), rnd.integers(0, len(CONFETTI), n)
    drag, fall = 3.2, rnd.uniform(110, 210, n)                      # air drag, then a slow flutter down
    for k in range(n):
        t = since
        e = (1 - math.exp(-drag * t)) / drag
        x = W / 2 + vx[k] * e + 40 * math.sin(t * 3 + spin[k])
        y = 900 + vy[k] * e + fall[k] * t
        a = min(1.0, since / 0.08)
        if flop is not None:                       # the party is cancelled: everything falls, fast, then fades
            y += 900 * flop * flop
            a *= max(0.0, 1 - flop / 0.9)
        if a <= 0 or y > H:
            continue
        w = 6 + 16 * abs(math.sin(t * 5 + spin[k]))                  # flipping as it flutters
        d.rectangle([x - w / 2, y - 8, x + w / 2, y + 8], fill=CONFETTI[cols[k]] + (int(255 * a),))


def sweat_drop(layer: Image.Image, x: float, y: float, since: float) -> None:
    """A cartoon sweat drop sliding down beside a nervous face."""
    d = ImageDraw.Draw(layer)
    y += 40 * min(1.0, since / 0.8)
    a = int(255 * min(1.0, since / 0.15))
    d.polygon([(x, y - 34), (x - 16, y), (x + 16, y)], fill=(130, 200, 255, a))
    d.ellipse([x - 16, y - 16, x + 16, y + 16], fill=(130, 200, 255, a))
    d.ellipse([x - 7, y - 8, x, y - 1], fill=(240, 250, 255, a))


def sticker(layer: Image.Image, text: str, cx: float, cy: float, since: float) -> None:
    """A tilted sticker slapped onto the card, with a little overshoot: the punchline after the slogan."""
    k = min(1.0, since / 0.25)
    scale = 1.0 + 0.25 * math.sin(math.pi * k) if k < 1 else 1.0
    f = _font("serif", int(84 * scale))
    tmp = Image.new("RGBA", (520, 200), (0, 0, 0, 0))
    td = ImageDraw.Draw(tmp)
    tw = td.textlength(text, font=f)
    td.rounded_rectangle([260 - tw / 2 - 28, 100 - 58, 260 + tw / 2 + 28, 100 + 58], radius=18, fill=(255, 132, 96, 255))
    td.text((260, 100), text, font=f, fill=(255, 255, 255, 255), anchor="mm")
    tmp = tmp.rotate(-9, resample=Image.BICUBIC)
    if since > 0:
        layer.alpha_composite(tmp, (int(cx - 260), int(cy - 100)))


def render_frames(post: dict, section: dict, n: int, site: dict, pl: dict):
    lines, lead, guest = pl["lines"], pl["lead"], pl["guest"]
    g = GUESTS[guest]
    for ln in lines:
        timed = word_times(ln["text"], ln["said"], lead)
        ln["groups"] = chunks(timed)
        ln["fig"] = figure(ln["text"]) if ln["who"] == "spark" and not ln["card"] else ""
        ln["fig_at"] = figure_time(timed, ln["fig"]) if ln["fig"] else 0
        ln["shape"] = spark.shape_for(plain(ln["text"])) if ln["who"] == "spark" and not ln["card"] else "blob"
    dots = _bokeh(n + 3)
    source = publishers(post, section)
    label = CAT_NAMES.get(section.get("category", ""), "").upper()
    total = int(pl["seconds"] * FPS)
    shown = {"text": lines[0]["fig"], "at": -9.0, "off": None}   # the hook's number is the cover: on from frame one
    spark_shape = ["blob", lines[0]["shape"], -9.0]
    card_from = next((ln["start"] for ln in lines if ln["card"]), None)
    end_q = max(k for k, ln in enumerate(lines) if not ln["card"])   # the last spoken line before the card

    for fi in range(total):
        tt = fi / FPS
        i = max([k for k, ln in enumerate(lines) if ln["start"] <= tt] or [0])
        ln = lines[i]
        lt = tt - ln["start"]
        speaking = ln["who"]
        on_card = card_from is not None and tt >= card_from
        cp = ease((tt - card_from) / 0.6) if on_card else 0.0       # 0 -> 1 as the card arrives
        frame = _background(tt, dots, WASHES[(i - 1) % 4], WASHES[i % 4], ease(lt / 0.6) if i else 1.0)
        layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(layer)
        head_a = int(255 * (1 - cp))
        if head_a:
            d.text((M, 300), site["name"].upper(), font=_font("sans_bold", 32), fill=YELLOW + (head_a,))
            lf = _font("sans_bold", 30)
            lw = d.textlength(label, font=lf)
            d.rounded_rectangle([W - M - lw - 116, 290, W - M - 60, 344], radius=27, outline=INK + (int(head_a * 0.8),),
                                width=3)
            d.text((W - M - lw - 88, 299), label, font=lf, fill=INK + (int(head_a * 0.9),))
            d.rounded_rectangle([M, 372, W - M - 60, 380], radius=4, fill=INK + (int(head_a * 0.25),))
            d.rounded_rectangle([M, 372, M + (W - 2 * M - 60) * min(1, tt / (card_from or pl["seconds"])), 380],
                                radius=4, fill=INK + (int(head_a * 0.92),))

        # the number Spark is talking about rises into the hologram as it says it; it powers off when Spark moves on
        # to a line without one (an old number under a new fact misleads); while the guest reacts, it stays up
        if not on_card:
            if ln["fig"] and i and lt >= ln["fig_at"] - 0.25 and shown["text"] != ln["fig"]:
                shown.update(text=ln["fig"], at=tt, off=None)
            if shown["text"] and speaking == "spark" and not ln["fig"] and shown["off"] is None and i:
                shown["off"] = tt
        elif shown["text"] and shown["off"] is None:
            shown["off"] = tt
        fade = 1.0 if shown["off"] is None else max(0.0, 1 - (tt - shown["off"]) / 0.3)
        if fade == 0.0:
            shown.update(text="", off=None)
        if shown["text"]:
            p = (tt - shown["at"]) / 0.6
            top = fig_size(d, shown["text"], 200, 680)
            big = _font("serif", top)
            tw = d.textlength(shown["text"], font=big)
            hologram(layer, W / 2, PANEL_Y, tw, min(p, fade), tt, 680)
            q = min(1.0, p / 0.5)
            if p > 0:
                fsz = int(top * (1.0 if q >= 1 else 0.6 + 0.4 * q + 0.12 * math.sin(math.pi * q)))
                f2 = _font("serif", fsz)
                d.text(((W - d.textlength(shown["text"], font=f2)) / 2, PANEL_Y - fsz * 0.52), shown["text"], font=f2,
                       fill=YELLOW + (int(255 * min(1, q * 2) * fade),), stroke_width=6,
                       stroke_fill=BG_TOP + (int(255 * fade),))

        # the logo card: the mark sweeps its five-minute slice, the name, then the slogan as the guest says it
        if on_card:
            draw_logo(layer, W / 2, 640, 150 * (0.7 + 0.3 * cp), ease((tt - card_from - 0.2) / 0.8), cp)
            nf = _font("serif", 92)
            name = site["name"]
            d.text((W / 2, 880 + (1 - cp) * 30), name, font=nf, fill=INK + (int(255 * cp),), anchor="mm")
            slo = next((x for x in lines if x["card"] and x["who"] != "spark"), None)
            if slo:
                sp = ease((tt - slo["start"] - 0.15) / 0.3)
                if sp > 0:
                    text = plain(slo["text"])
                    sf = _font("serif", int(62 * (0.85 + 0.15 * sp)))
                    tw = d.textlength(text, font=sf)
                    d.rounded_rectangle([W / 2 - tw / 2 - 26, 958, W / 2 + tw / 2 + 26, 1052], radius=30,
                                        fill=YELLOW + (int(255 * sp),))
                    d.text((W / 2, 1004), text, font=sf, fill=BG_TOP + (int(255 * sp),), anchor="mm")
                after = [x for x in lines if x["card"] and x["start"] > slo["start"]]
                if after and tt >= after[0]["start"]:
                    sticker(layer, plain(after[0]["text"]), W / 2 + 20, 1150, tt - after[0]["start"])

        # Spark's shape follows its own lines and holds while the guest talks
        if speaking == "spark" and ln["shape"] != spark_shape[1]:
            spark_shape[:] = [spark_shape[1], ln["shape"], tt]
        morph = ease((tt - spark_shape[2] - 0.1) / 0.4)

        for who in ((guest, "spark") if speaking == "spark" else ("spark", guest)):   # the speaker on top
            talking = who == speaking
            m = pl["mouth"][who]
            mth = float(m[min(len(m) - 1, fi)]) if len(m) else 0.0
            cx, base, size = SPARK_AT if who == "spark" else g["at"]
            if cp:                                           # on the card both glide down a little, facing you
                base = base + 230 * cp
                size = size * (1 - 0.3 * cp)
            k = ease(min(1.0, lt / 0.3))
            s = int(size * (1.0 + 0.06 * k if talking else 1.0 - 0.04 * k))
            facing = on_card or i >= end_q
            if who == "spark":
                asked = not talking and ln["text"].rstrip().endswith("?")
                im = spark.draw(s, tt, mth, "ask" if asked else "talk", beat=BEAT, seed=n,
                                look=(0.0, 0.5) if facing else (0.9, 0.0),
                                shape=spark_shape[1], shape_from=spark_shape[0], morph=morph)
            else:
                im = g["draw"](s, tt, mth, talking, seed=n, look=(0.0, 0.4) if facing else (-0.9, 0.1))
            if not talking:                                  # the listener steps back a little
                im.putalpha(im.getchannel("A").point(lambda v: v * 205 // 255))
            layer.alpha_composite(im, (int(cx - im.width / 2), int(base - im.height)))

        # the gags: confetti bursts on a celebration, falls flat on the letdown; a sweat drop on a nervous line
        party = next((x for x in lines if "confetti" in x["tags"]), None)
        if party and tt >= party["start"]:
            flop = next((x for x in lines if "drop" in x["tags"] and x["start"] > party["start"]), None)
            confetti(layer, tt - party["start"], (tt - flop["start"]) if flop and tt >= flop["start"] else None, n)
        if "sweat" in ln["tags"]:
            cx, base, size = SPARK_AT if speaking == "spark" else g["at"]
            if cp:
                base, size = base + 230 * cp, size * (1 - 0.3 * cp)
            sweat_drop(layer, cx + size * 0.36, base - size * 0.78, lt)

        # caption: the speaker's name, then their words lit as they say them (not on the card: the card says it)
        hi = YELLOW if speaking == "spark" else g["hi"]
        if not on_card:
            tag = "SPARK" if speaking == "spark" else g["tag"]
            tf = _font("sans_bold", 30)
            tw = d.textlength(tag, font=tf)
            tx = W / 2 - tw / 2
            d.rounded_rectangle([tx - 20, 1146, tx + tw + 20, 1190], radius=22, fill=hi + (255,))
            d.text((tx, 1152), tag, font=tf, fill=BG_TOP + (255,))
            draw_caption(layer, ln["groups"], lt, hi=hi, y_mid=1280)
            if source:
                sf = _font("sans", 32)
                st = f"Source: {source}"
                d.text(((W - d.textlength(st, font=sf)) / 2, SOURCE_Y + 20), st, font=sf, fill=MUTED + (255,))
        else:
            ff = _font("sans_bold", 40)
            d.text((W / 2, 1490), "Follow @fiveminute_ai", font=ff, fill=INK + (int(230 * cp),), anchor="mm")

        frame.alpha_composite(layer)
        # the camera eases toward whoever is talking: a slow push-in, pulled a little to their side
        z = 1.03 + 0.02 * min(1.0, lt / 3)
        focus = W / 2 if (on_card or i >= end_q) else (SPARK_AT[0] if speaking == "spark" else g["at"][0])
        cxv = W / 2 + (focus - W / 2) * 0.18 * ease(min(1.0, lt / 0.6))
        cw, ch = W / z, H / z
        x0 = min(max(0, cxv - cw / 2), W - cw)
        frame = frame.crop((int(x0), int((H - ch) / 2), int(x0 + cw), int((H + ch) / 2))).resize((W, H), Image.BILINEAR)
        yield frame.convert("RGB").tobytes()


REELS = Path(__file__).resolve().parent.parent / "reels"      # the Remotion project (6 Nov 2026)
SFX = Path(__file__).resolve().parent / "sfx"                # cartoon sounds made with ZzFX (reels/tools/make_sfx.mjs)


def _sfx(name: str) -> np.ndarray:
    import wave
    with wave.open(str(SFX / f"{name}.wav")) as w:
        x = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768
        rate = w.getframerate()
    n = int(len(x) * voice.SR / rate)                        # to the voice track's rate
    return np.interp(np.linspace(0, len(x) - 1, n), np.arange(len(x)), x).astype(np.float32)


def gag_sounds(track: np.ndarray, pl: dict, level: float = 0.5) -> np.ndarray:
    """The gags get their sounds (6 Nov 2026): a party pop and sparkle on the confetti line, a sad slide when it
    falls flat, a gulp with the sweat drop, a slap when the sticker lands on the logo card."""
    if not SFX.exists():
        return track
    lines = pl["lines"]
    hits = []
    for k, ln in enumerate(lines):
        tags = ln["tags"]
        if "confetti" in tags:
            hits += [(ln["start"] + 0.05, "party_pop"), (ln["start"] + 0.15, "sparkle")]
        if "drop" in tags:
            hits.append((ln["start"] + 0.1, "sad_slide"))
        if "sweat" in tags:
            hits.append((ln["start"] + 0.35, "gulp"))
        if ln["card"] and ln["who"] == "spark" and any(x["card"] and x["who"] != "spark" for x in lines[:k]):
            hits.append((ln["start"], "slap"))
    out = track.copy()
    for at, name in hits:
        try:
            clip = _sfx(name) * level
        except (OSError, EOFError):
            continue
        i = max(0, int(at * voice.SR))
        j = min(len(out), i + len(clip))
        out[i:j] += clip[: j - i]
    return out


def remotion_ready() -> bool:
    import shutil
    return bool(shutil.which("npx")) and (REELS / "node_modules" / "@remotion" / "cli").exists()


def timeline(post: dict, section: dict, pl: dict) -> dict:
    """What the Remotion drawing needs, from the same plan the audio was made from: lines with their word timings
    and caption groups, the number to show, and each speaker's mouth openness per frame."""
    lines = []
    for ln in pl["lines"]:
        timed = word_times(ln["text"], ln["said"], pl["lead"])
        fig = figure(ln["text"]) if ln["who"] == "spark" and not ln["card"] else ""
        lines.append({"who": ln["who"], "text": plain(ln["text"]), "start": ln["start"], "end": ln["end"],
                      "card": ln["card"], "tags": sorted(ln["tags"]),
                      "groups": [[{"w": w, "t": round(t, 3)} for w, t in g] for g in chunks(timed)],
                      "fig": fig, "figAt": round(figure_time(timed, fig), 3) if fig else None})
    return {"fps": FPS, "seconds": round(pl["seconds"], 3), "guest": pl["guest"], "source": publishers(post, section),
            "label": CAT_NAMES.get(section.get("category", ""), "").upper(), "site": "FIVE MINUTE AI", "lines": lines,
            "mouth": {w: [round(float(x), 3) for x in m] for w, m in pl["mouth"].items()},
            "visemes": pl.get("visemes") or {}}


def remotion_render(post: dict, section: dict, pl: dict, audio: Path, out: Path) -> Path:
    """Draw the Reel with Remotion (reels/) over the finished soundtrack. Raises on any failure: the caller falls back
    to the Python drawing, so a Reel is never lost to the new renderer."""
    import json
    import shutil
    import uuid
    job = REELS / "public" / "jobs" / uuid.uuid4().hex[:10]
    job.mkdir(parents=True)
    try:
        shutil.copy(audio, job / "audio.wav")
        props = {"timeline": timeline(post, section, pl), "audio": f"jobs/{job.name}/audio.wav"}
        (job / "props.json").write_text(json.dumps(props, ensure_ascii=False), encoding="utf-8")
        npx = shutil.which("npx")
        r = subprocess.run([npx, "remotion", "render", "src/index.ts", "DuoReel", str(out.resolve()),
                            f"--props={job / 'props.json'}", "--codec=h264", "--crf=18", "--log=error"],
                           cwd=REELS, capture_output=True, text=True, timeout=1200)
        if r.returncode != 0 or not out.exists():
            raise RuntimeError(f"remotion render failed: {(r.stderr or r.stdout)[-800:]}")
        return out
    finally:
        shutil.rmtree(job, ignore_errors=True)


def duo_reel(post: dict, section: dict, n: int, site: dict, out: Path, script: list[tuple], guest: str = "doubt",
             renderer: str = "auto") -> Path:
    """renderer: "auto" (Remotion when installed, else Python), "remotion" (fail if it fails) or "python"."""
    pl = plan(script, guest, visemes=renderer in ("auto", "remotion") and remotion_ready())
    seconds = pl["seconds"]
    out.parent.mkdir(parents=True, exist_ok=True)
    music, _ = write_wav(out.with_suffix(".m.wav"), bars=math.ceil(seconds / BAR) + 1, seed=7 + n)
    vo = voice.write_wav(out.with_suffix(".vo.wav"), sum(pl["tracks"].values()))
    pops = []
    for k, ln in enumerate(pl["lines"]):
        f = figure(ln["text"]) if ln["who"] == "spark" and k and not ln["card"] else ""
        if f:
            pops.append(ln["start"] + figure_time(word_times(ln["text"], ln["said"], pl["lead"]), f) - 0.25)
    card = next((ln for ln in pl["lines"] if ln["card"]), None)
    cuts = [card["start"]] if card else []                    # a whoosh as the logo card comes in
    if card:
        pops.append(card["start"] + 1.0)                      # a pop as the slice completes
    fx = voice.write_wav(out.with_suffix(".fx.wav"), gag_sounds(sfx_track(seconds, cuts, pops), pl))
    mix = ("[2:a]aresample=48000,asplit=2[v][vk];[1:a]aresample=48000,volume=0.42[m];[3:a]aresample=48000[fx];"
           "[m][vk]sidechaincompress=threshold=0.02:ratio=8:attack=20:release=400[md];"
           "[md][v][fx]amix=inputs=3:weights=1 1.6 0.9:normalize=0,loudnorm=I=-14:TP=-1.5:LRA=9[a]")
    if renderer in ("auto", "remotion") and remotion_ready():
        # Remotion draws over the finished soundtrack (6 Nov 2026: about 6x faster than the Python drawing, and
        # smoother); any failure falls back to the Python drawing below
        sound = out.with_suffix(".mix.wav")
        try:
            r = subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo",
                                "-i", str(music), "-i", str(vo), "-i", str(fx), "-filter_complex", mix, "-map", "[a]",
                                "-t", f"{seconds:.2f}", "-ar", "48000", str(sound)], capture_output=True, text=True)
            if r.returncode != 0:
                raise RuntimeError(r.stderr[-400:])
            remotion_render(post, section, pl, sound, out)
            for p in (music, vo, fx, sound):
                p.unlink(missing_ok=True)
            return out
        except Exception as exc:  # noqa: BLE001
            if renderer == "remotion":
                raise
            import logging
            logging.getLogger(__name__).warning("Remotion render failed, drawing in Python: %s", str(exc)[:300])
            sound.unlink(missing_ok=True)
    cmd = ["ffmpeg", "-y", "-loglevel", "error",
           "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
           "-i", str(music), "-i", str(vo), "-i", str(fx), "-filter_complex",
           "[2:a]aresample=48000,asplit=2[v][vk];[1:a]aresample=48000,volume=0.42[m];[3:a]aresample=48000[fx];"
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
