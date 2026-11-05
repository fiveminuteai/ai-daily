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


PACE = 160                     # kept for callers that pass pace=None to turn pacing off
RATE = 4.3                     # syllables per second, held for every line (Kokoro reads short lines faster on its
                               # own: 144 to 209 wpm line to line at one speed setting, 4 Nov 2026)


# Character voices: a blend of Kokoro voices (the mean of their style vectors) and a pitch lift, so the
# presenter sounds like itself and not like a stock narrator (5 Nov 2026, Pavan: "a male voice for spark doesn't
# fit"). The pitch lift is a resample, so speech is generated slower by the same factor to keep the pace.
CHARACTERS = {
    "spark-bright": {"blend": ["af_nova", "af_sky"], "pitch": 1.08, "lang": "en-us"},
    "spark-neutral": {"blend": ["am_puck", "af_river"], "pitch": 1.06, "lang": "en-us"},
    "spark-cheeky": {"blend": ["bf_lily", "af_jessica"], "pitch": 1.10, "lang": "en-gb"},
    # Soothing Spark candidates (5 Nov 2026, Pavan: "I need something soothing"): warm voices, almost no pitch lift,
    # a calmer rate
    "spark-calm": {"blend": ["af_heart", "af_river"], "pitch": 1.02, "lang": "en-us", "rate": 3.9},
    "spark-warm": {"blend": ["af_heart", "am_puck"], "pitch": 1.03, "lang": "en-us", "rate": 3.9},
    "spark-soft": {"blend": ["bf_emma", "af_river"], "pitch": 1.0, "lang": "en-gb", "rate": 4.8},
    # Doubt, the duo's sceptic: lower and drier than Spark, so the two never sound alike; it comes in quick
    "doubt": {"blend": ["bm_lewis", "am_onyx"], "pitch": 0.97, "lang": "en-gb", "rate": 4.8},
    # Rex, a guest: a tired old dinosaur, deep and slow, for stories about fossil fuels, power and emissions
    "rex": {"blend": ["am_fenrir", "bm_george"], "pitch": 0.88, "lang": "en-gb", "rate": 4.6},
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


VOWELS = re.compile(r"[aeiouyɑɐɒæɔəɘɚɛɜɝɞɤɨɪɯɵøœɶʉʊʌʏᵻ]+")


def syllables(ph: str) -> int:
    """Syllables in a phoneme string: one per vowel group (a diphthong like eɪ is one group)."""
    return max(1, len(VOWELS.findall(ph)))


def squeeze(s: np.ndarray, max_pause: float = 0.32, floor: float = 0.012) -> np.ndarray:
    """Shorten any pause inside a line to at most `max_pause` s: Kokoro leaves 0.5-0.9 s at a full stop, which made
    "Wait. Isn't..." drag and the pace jump around (5 Nov 2026)."""
    hop = SR // 100
    n = len(s) // hop
    if n < 3:
        return s
    quiet = np.sqrt(np.mean(s[: n * hop].reshape(n, hop) ** 2, axis=1)) < floor
    keep, run = [], 0
    limit = int(max_pause * 100)
    for k in range(n):
        run = run + 1 if quiet[k] else 0
        if run <= limit:
            keep.append(k)
    out = np.concatenate([s[k * hop:(k + 1) * hop] for k in keep] + [s[n * hop:]])
    return out.astype(np.float32)


def say(text: str, voice: str | None = None, speed: float = SPEED, pace: float | None = PACE) -> np.ndarray:
    """One line, spoken. With `pace`, the line is measured and spoken again at the speed that lands it on the
    character's rate (within 0.8x to 1.2x, so no line sounds stretched).

    The rate is syllables per second, counted from Kokoro's own phonemes (5 Nov 2026, Pavan: "speech rate isn't
    consistent", and "tell us..." came out slower: counting words treats "$17 billion dollars" like "it was")."""
    words = spoken(text)
    voice = voice or VOICE
    c = CHARACTERS.get(voice, {})
    pitch, lang = c.get("pitch", 1.0), c.get("lang", "en-gb")
    rate = c.get("rate", RATE)
    style = _style(voice)
    ph = phonemes(words, lang)
    n_syl = syllables(ph or _engine().tokenizer.phonemize(words, lang))

    def make(sp: float) -> np.ndarray:
        if ph:
            s, sr = _engine().create(ph, voice=style, speed=sp / pitch, lang=lang, is_phonemes=True)
        else:
            s, sr = _engine().create(words, voice=style, speed=sp / pitch, lang=lang)
        assert sr == SR, sr
        return squeeze(pitch_up(trim(np.asarray(s, np.float32)), pitch))

    s, sp = make(speed), speed
    best = s
    for _ in range(6 if pace else 0):          # speed doesn't map 1:1 to rate: correct until within 2.5%
        now = n_syl / max(0.3, len(s) / SR)
        if abs(now - rate) / rate <= 0.025:
            return s
        if abs(n_syl / max(0.3, len(s) / SR) - rate) < abs(n_syl / max(0.3, len(best) / SR) - rate):
            best = s
        sp = float(np.clip(sp * rate / now, 0.75, 1.25))
        s = make(sp)
    return s if abs(n_syl / max(0.3, len(s) / SR) - rate) < abs(n_syl / max(0.3, len(best) / SR) - rate) else best


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
