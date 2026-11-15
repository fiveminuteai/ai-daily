"""When each word of a spoken line is really said (15 Nov 2026).

Until now captions were timed by guesswork: each word got a share of the line's length by its letters
(fma/pulse_reel.word_times), so the highlighted word drifted from the voice. Here the finished clip is listened to
by a small speech model (faster-whisper, MIT, base.en on the CPU) and its word times are matched back to the script
we already know. The model is only a clock: what is shown is always our own checked text, never what it heard.

It is optional. Without the package, or on any failure, `word_times` returns None and the caller keeps the old
letter-share timing, so a Reel is never lost to it.

Why this and not Kokoro's own timings: fma/voice.py trims and squeezes the audio after it is made, so times taken
at synthesis would be wrong by the time the clip is used.
"""
from __future__ import annotations

import difflib
import logging
import os
import re

import numpy as np

log = logging.getLogger(__name__)

MODEL = os.environ.get("FMA_ALIGN_MODEL", "base.en")
_model = None
_failed = False


def _norm(w: str) -> str:
    return re.sub(r"[^a-z0-9]", "", w.lower())


def available() -> bool:
    if os.environ.get("FMA_ALIGN", "1") == "0" or _failed:
        return False
    import importlib.util
    return importlib.util.find_spec("faster_whisper") is not None


def heard(samples: np.ndarray, sr: int) -> list[tuple[str, float]]:
    """(word, start in seconds) as the speech model hears the clip. Raises if the model can't be loaded or run."""
    global _model
    if _model is None:
        from faster_whisper import WhisperModel
        _model = WhisperModel(MODEL, device="cpu", compute_type="int8")
    audio = np.asarray(samples, dtype=np.float32)
    if sr != 16000:                                   # the model wants 16 kHz; linear resampling is enough for a clock
        n = int(len(audio) * 16000 / sr)
        audio = np.interp(np.linspace(0, len(audio) - 1, n), np.arange(len(audio)), audio).astype(np.float32)
    segments, _info = _model.transcribe(audio, language="en", word_timestamps=True, beam_size=1,
                                        condition_on_previous_text=False, vad_filter=False)
    return [(w.word.strip(), float(w.start)) for seg in segments for w in (seg.words or [])]


def match(script: list[str], heard_words: list[tuple[str, float]], said: float,
          guess: list[float]) -> list[float] | None:
    """A start time for every script word. Words the model heard the same way take its time; the others (numbers
    read out, names it misheard) are placed between their matched neighbours in proportion to the old guess.
    None when too little matched to trust: under half the words, or times that run backwards."""
    a, b = [_norm(w) for w in script], [_norm(w) for w, _ in heard_words]
    times: list[float | None] = [None] * len(script)
    for blk in difflib.SequenceMatcher(None, a, b, autojunk=False).get_matching_blocks():
        for k in range(blk.size):
            if a[blk.a + k]:
                times[blk.a + k] = heard_words[blk.b + k][1]
    known = [(i, t) for i, t in enumerate(times) if t is not None]
    if len(known) < max(2, len(script) / 2):
        return None
    if any(t2 < t1 for (_, t1), (_, t2) in zip(known, known[1:])) or known[-1][1] > said + 0.5:
        return None
    # fill the gaps: between two anchors, keep the guess's proportions
    anchors = [(-1, 0.0, 0.0)] + [(i, t, guess[i]) for i, t in known] + [(len(script), said, said)]
    out = list(times)
    for (i0, t0, g0), (i1, t1, g1) in zip(anchors, anchors[1:]):
        for i in range(i0 + 1, i1):
            share = (guess[i] - g0) / (g1 - g0) if g1 > g0 else (i - i0) / (i1 - i0)
            out[i] = t0 + (t1 - t0) * min(1.0, max(0.0, share))
    return [float(t) for t in out]


def word_times(samples: np.ndarray, sr: int, text: str, listen=None) -> list[tuple[str, float]] | None:
    """(word, seconds from the start of the clip) for each word of `text`, or None to keep the letter-share guess.
    `listen` replaces the speech model in tests."""
    global _failed
    from .pulse_reel import word_times as guessed
    from .social import plain
    said = len(samples) / sr
    base = guessed(text, said, 0.0)
    words = [w for w, _ in base]
    if not words or (listen is None and not available()):
        return None
    try:
        got = (listen or heard)(samples, sr)
    except Exception as exc:  # noqa: BLE001 - the clock is an extra; without it captions use the guess
        _failed = True
        log.warning("word timing is off for this run, captions use the letter-share guess: %s", str(exc)[:200])
        return None
    times = match(words, got, said, [t for _, t in base])
    if times is None:
        log.info("word timing: too little matched for %r, using the guess", plain(text)[:60])
        return None
    return list(zip(words, times))
