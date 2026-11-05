"""The Reels' narrator: Kokoro-82M (Apache-2.0) through kokoro-onnx (MIT), run offline. One voice at one speed for
every line (4 Nov 2026, Pavan: the sample's speed "isn't consistent" because long lines were sped up to fit their
scene; now the scenes stretch to fit the voice instead).

The model files (kokoro-v1.0.onnx, voices-v1.0.bin, ~330 MB) live in FMA_KOKORO_DIR, default .cache/kokoro.
Without them, or without kokoro-onnx installed, `available()` is False and Reels render without a voice.
Synthetic voice: every voiced Reel carries Meta's AI label and "Voice: AI" in its caption."""
from __future__ import annotations

import os
import re
from pathlib import Path

import numpy as np

SR = 24000
VOICE = "bm_george"            # British male (Pavan's pick, 4 Nov 2026); Kokoro has no Indian English voice
SPEED = 1.0
OUTRO = "Tell us in the comments below and follow us for such updates."    # Pavan's words, 4 Nov 2026

# How names should be read. Kokoro reads most brand names well; these it spells or stresses wrongly.
PRONOUNCE = {
    r"\bGPT-(\d)": r"G P T \1",
    r"\bK-12\b": "K to 12",
    r"\bS-1\b": "S 1",
    r"\$(\d+(?:\.\d+)?)\s?(billion|million|trillion)\b": r"\1 \2 dollars",
    # decimals digit by digit (5 Nov 2026: "$11.5 billion" was heard as "11 billion, 5 billion"); x.0 drops the 0
    r"(\d+)\.0\b": r"\1",
    r"(\d+)\.(\d+)": lambda m: f"{m.group(1)} point {' '.join(m.group(2))}",
}

# Names whose sound no spelling gets right are given as phonemes (IPA, as Kokoro's own tokenizer writes them).
# Found 5 Nov 2026 by phonemising every name in config/sources.yaml: "SpaceX" came out as two stressed words
# ("Space X", Pavan heard it), AWS as "awes", xAI as "ex-uh-eye" (a lone "A" is read as the article), Qwen as
# "queue-wen". A name not listed here is left to Kokoro, which reads the rest of the list well.
PHONEMES = {
    "SpaceX": "spˈeɪsɛks",
    "AWS": "ˈeɪ dˈʌbəljˌuː ˈɛs",
    "xAI": "ˈɛks ˈeɪ ˈaɪ",
    "Qwen": "tʃwˈɛn",
    "Huawei": "wˈɑːweɪ",
}
_NAME_RE = re.compile(r"\b(" + "|".join(map(re.escape, PHONEMES)) + r")\b")


def phonemes(text: str, lang: str) -> str | None:
    """The line as phonemes with the fixed names spliced in, or None when it has none of them."""
    parts = _NAME_RE.split(text)
    if len(parts) == 1:
        return None
    tok = _engine().tokenizer
    return " ".join(PHONEMES[p] if p in PHONEMES else tok.phonemize(p, lang) for p in parts if p.strip()).strip()

_ENGINE = None


def model_dir() -> Path:
    return Path(os.environ.get("FMA_KOKORO_DIR") or Path(__file__).resolve().parent.parent / ".cache" / "kokoro")


def available() -> bool:
    try:
        import kokoro_onnx  # noqa: F401
    except ImportError:
        return False
    d = model_dir()
    return (d / "kokoro-v1.0.onnx").exists() and (d / "voices-v1.0.bin").exists()


def _engine():
    global _ENGINE
    if _ENGINE is None:
        from kokoro_onnx import Kokoro
        d = model_dir()
        _ENGINE = Kokoro(str(d / "kokoro-v1.0.onnx"), str(d / "voices-v1.0.bin"))
    return _ENGINE


def spoken(text: str) -> str:
    """The text as the narrator should read it: names respelled, citation marks gone."""
    out = re.sub(r"\[S\d+\]", "", text)
    for pat, rep in PRONOUNCE.items():
        out = re.sub(pat, rep, out)
    return re.sub(r"\s+", " ", out).strip()


def trim(s: np.ndarray, floor: float = 0.01, pad: float = 0.04) -> np.ndarray:
    """Cut leading and trailing silence, keeping a few milliseconds so words don't start clipped."""
    loud = np.flatnonzero(np.abs(s) > floor)
    if not len(loud):
        return s
    a, b = max(0, loud[0] - int(pad * SR)), min(len(s), loud[-1] + int(pad * SR))
    return s[a:b]


PACE = 160                     # words per minute, held for every line: Kokoro reads short lines faster on its own
                               # (sample 2, 4 Nov 2026: 144 to 209 wpm line to line at one speed setting)


# Character voices: a blend of Kokoro voices (the mean of their style vectors) and a pitch lift, so the
# presenter sounds like itself and not like a stock narrator (5 Nov 2026, Pavan: "a male voice for spark doesn't
# fit"). The pitch lift is a resample, so speech is generated slower by the same factor to keep the pace.
CHARACTERS = {
    "spark-bright": {"blend": ["af_nova", "af_sky"], "pitch": 1.08, "lang": "en-us"},
    "spark-neutral": {"blend": ["am_puck", "af_river"], "pitch": 1.06, "lang": "en-us"},
    "spark-cheeky": {"blend": ["bf_lily", "af_jessica"], "pitch": 1.10, "lang": "en-gb"},
    # Doubt, the duo's sceptic: lower and drier than Spark, so the two never sound alike
    "doubt": {"blend": ["bm_lewis", "am_onyx"], "pitch": 0.97, "lang": "en-gb"},
}


def _style(voice: str):
    """A Kokoro voice name, "a+b" for an even blend, or a CHARACTERS key."""
    c = CHARACTERS.get(voice)
    names = c["blend"] if c else voice.split("+")
    if len(names) == 1:
        return names[0]
    return np.mean([_engine().get_voice_style(n) for n in names], axis=0)


def pitch_up(s: np.ndarray, factor: float) -> np.ndarray:
    """Raise pitch (and speed) by `factor` with a plain resample: fine for a small lift on a cartoon voice."""
    if abs(factor - 1) < 1e-3:
        return s
    n = int(len(s) / factor)
    return np.interp(np.linspace(0, len(s) - 1, n), np.arange(len(s)), s).astype(np.float32)


def say(text: str, voice: str | None = None, speed: float = SPEED, pace: float | None = PACE) -> np.ndarray:
    """One line, spoken. With `pace`, the line is measured and spoken again at the speed that lands it on that pace
    (within 0.8x to 1.2x, so no line sounds stretched)."""
    words = spoken(text)
    voice = voice or VOICE
    c = CHARACTERS.get(voice, {})
    pitch, lang = c.get("pitch", 1.0), c.get("lang", "en-gb")
    style = _style(voice)
    ph = phonemes(words, lang)

    def make(sp: float) -> np.ndarray:
        if ph:
            s, sr = _engine().create(ph, voice=style, speed=sp / pitch, lang=lang, is_phonemes=True)
        else:
            s, sr = _engine().create(words, voice=style, speed=sp / pitch, lang=lang)
        assert sr == SR, sr
        return pitch_up(trim(np.asarray(s, np.float32)), pitch)

    s, sp = make(speed), speed
    for _ in range(2 if pace else 0):          # speed doesn't map 1:1 to pace, so correct twice
        wpm = len(words.split()) / max(0.3, len(s) / SR) * 60
        fix = float(np.clip(sp * pace / wpm, 0.8, 1.2))
        if abs(fix - sp) <= 0.02:
            break
        s, sp = make(fix), fix
    return s


def envelope(track: np.ndarray, fps: int) -> np.ndarray:
    """Mouth opening per video frame, 0..1, from the voice's loudness: what the presenter's lips follow."""
    hop = SR // fps
    n = len(track) // hop
    rms = np.sqrt(np.mean(track[: n * hop].reshape(n, hop) ** 2, axis=1)) if n else np.zeros(0)
    peak = np.percentile(rms[rms > 0.005], 90) if np.any(rms > 0.005) else 1.0
    env = np.clip((rms - 0.012) / max(1e-6, peak - 0.012), 0, 1)
    out = np.copy(env)
    for i in range(1, len(out)):              # lips open fast and close a little slower, like a real mouth
        out[i] = max(env[i], out[i - 1] * 0.55)
    return out


def write_wav(path: Path, track: np.ndarray) -> Path:
    import wave
    pcm = (np.clip(track, -1, 1) * 32767).astype(np.int16)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())
    return path
