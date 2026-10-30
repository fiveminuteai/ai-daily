"""An original music bed for the daily Reel, synthesised from code: a warm, upbeat lo-fi house loop at 100 BPM.

No samples and no third-party recordings, so there is nothing to license and no copyright claim can hit the Reel.
Built like a small studio mix: band-limited oscillators, filtered pads, sidechain ducking under the kick, a stereo
convolution reverb, bus saturation and a peak limiter. Loudness is set to Instagram's -14 LUFS when the Reel is
encoded (see reel.py)."""
from __future__ import annotations

import wave
from pathlib import Path

import numpy as np
from scipy.signal import butter, fftconvolve, sosfilt

SR = 48000
BPM = 100
BEAT = 60 / BPM
BAR = 4 * BEAT

# Fmaj7 - Em7 - Dm9 - Cmaj7 (a warm, hopeful loop), voiced around middle C
CHORDS = [[53, 57, 60, 64], [52, 55, 59, 62], [50, 53, 57, 60, 64], [48, 52, 55, 59]]
BASS = [41, 40, 38, 36]


def _hz(m: float) -> float:
    return 440.0 * 2 ** ((m - 69) / 12)


def _t(n: int) -> np.ndarray:
    return np.arange(n) / SR


def _saw(f: float, n: int, phase: float = 0.0) -> np.ndarray:
    """Band-limited sawtooth (additive, harmonics below 9 kHz), so the highs stay smooth instead of fizzy."""
    t = _t(n)
    out = np.zeros(n)
    for k in range(1, int(9000 / f) + 1):
        out += np.sin(2 * np.pi * k * f * t + k * phase) / k
    return out * 0.55


def _lp(x: np.ndarray, hz: float, order: int = 4) -> np.ndarray:
    return sosfilt(butter(order, hz, "low", fs=SR, output="sos"), x)


def _hp(x: np.ndarray, hz: float, order: int = 2) -> np.ndarray:
    return sosfilt(butter(order, hz, "high", fs=SR, output="sos"), x)


def _bp(x: np.ndarray, lo: float, hi: float) -> np.ndarray:
    return sosfilt(butter(2, [lo, hi], "band", fs=SR, output="sos"), x)


def _adsr(n: int, a: float, d: float, s: float, r: float) -> np.ndarray:
    t = _t(n)
    dur = n / SR
    env = np.where(t < a, t / max(a, 1e-4), s + (1 - s) * np.exp(-(t - a) / max(d, 1e-4)))
    rel = np.clip((dur - t) / max(r, 1e-4), 0, 1)
    return env * rel


class Mix:
    def __init__(self, seconds: float):
        self.n = int(seconds * SR)
        self.buses = {k: np.zeros((self.n, 2)) for k in ("drums", "bass", "music", "fx")}

    def add(self, bus: str, sig: np.ndarray, start: float, pan: float = 0.0, gain: float = 1.0):
        i = int(start * SR)
        if i >= self.n or i < 0:
            return
        sig = sig[: self.n - i] * gain
        if sig.ndim == 1:
            left, right = np.cos((pan + 1) * np.pi / 4), np.sin((pan + 1) * np.pi / 4)
            sig = np.stack([sig * left, sig * right], axis=1) * 2 ** 0.5
        self.buses[bus][i:i + len(sig)] += sig


def _reverb_ir(seconds: float = 2.2, seed: int = 3) -> np.ndarray:
    """A stereo room: decaying noise, darker as it fades, with a short pre-delay."""
    rng = np.random.default_rng(seed)
    n = int(seconds * SR)
    t = _t(n)
    ir = rng.standard_normal((n, 2)) * np.exp(-t / (seconds / 6.5))[:, None]
    ir[:, 0] = _lp(ir[:, 0], 6500, 2)
    ir[:, 1] = _lp(ir[:, 1], 6000, 2)
    pre = np.zeros((int(0.018 * SR), 2))
    return np.vstack([pre, ir]) / np.sqrt((ir ** 2).sum() / 2)


def compose(bars: int = 8, seed: int = 7) -> tuple[np.ndarray, list[float]]:
    """Return (stereo float array, beat times in seconds). Bar 1 is an intro, the last bar an outro."""
    rng = np.random.default_rng(seed)
    seconds = bars * BAR + 1.5                       # room for the reverb tail
    mx = Mix(seconds)
    kicks: list[float] = []
    for b in range(bars):
        t0 = b * BAR
        ch, bs = CHORDS[b % 4], BASS[b % 4]
        intro, outro = b == 0, b == bars - 1
        full = not intro and not outro

        # pad: detuned saws, low-passed, slow swell
        n = int(BAR * 1.08 * SR)
        pad = sum(_saw(_hz(m) * d, n, phase=rng.uniform(0, 6)) for m in ch for d in (0.996, 1.004))
        pad = _lp(pad, 900 if intro else 1600, 2) * _adsr(n, 0.25, 1.0, 0.85, 0.35) / len(ch)
        mx.add("music", pad, t0, pan=-0.35, gain=0.20)
        mx.add("music", np.roll(pad, 300), t0, pan=0.35, gain=0.20)

        # plucked arpeggio, sixteenth-note feel with a little swing
        pattern = [0, 2, 1, 3, 2, 1, 3, 2]
        for k, idx in enumerate(pattern):
            note = ch[idx % len(ch)] + 12 + (12 if k in (3, 7) else 0)
            start = t0 + k * BEAT / 2 + (0.035 if k % 2 else 0.0)
            n = int(BEAT * 0.8 * SR)
            f = _hz(note)
            tt = _t(n)
            pl = np.sin(2 * np.pi * f * tt) + 0.35 * np.sin(4 * np.pi * f * tt) + 0.12 * np.sin(6 * np.pi * f * tt)
            pl = _lp(pl * _adsr(n, 0.003, 0.18, 0.0, 0.05), 3800 if full else 1800, 2)
            mx.add("music", pl, start, pan=(-0.4, 0.4)[k % 2], gain=0.16 * (0.75 + 0.25 * rng.random()))

        if not outro:
            # sub bass with a soft pluck on beats 1, 2.5 and 3
            for start, length in ((0, 1.4), (1.5, 0.45), (2, 1.8)):
                n = int(BEAT * length * SR)
                tt = _t(n)
                f = _hz(bs)
                sub = np.sin(2 * np.pi * f * tt) + 0.25 * np.sin(4 * np.pi * f * tt)
                mx.add("bass", sub * _adsr(n, 0.006, 0.4, 0.6, 0.06), t0 + start * BEAT, gain=0.42 if full else 0.25)

        if full:
            for k in range(4):
                beat = t0 + k * BEAT
                kicks.append(beat)
                # kick: pitch-swept sine with a short click
                n = int(0.42 * SR)
                tt = _t(n)
                f = 46 + 110 * np.exp(-tt / 0.028)
                kick = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-tt / 0.16)
                kick[: int(0.004 * SR)] += _lp(rng.standard_normal(int(0.004 * SR)), 5000, 2) * 0.12
                mx.add("drums", np.tanh(kick * 1.6), beat, gain=0.62)
                # clap on 2 and 4: three quick noise bursts through a band-pass
                if k in (1, 3):
                    n = int(0.25 * SR)
                    burst = np.zeros(n)
                    for off in (0, 0.009, 0.018):
                        i = int(off * SR)
                        m = n - i
                        burst[i:] += rng.standard_normal(m) * np.exp(-_t(m) / (0.012 if off < 0.018 else 0.07))
                    mx.add("drums", _bp(burst, 900, 5200), beat, pan=0.05, gain=0.26)
                # closed hats on the off-beats, softer ghost hats between
                for h, g in ((0.5, 0.075), (0.25, 0.03), (0.75, 0.03)):
                    n = int(0.06 * SR)
                    hat = _lp(_hp(rng.standard_normal(n), 7000), 12500) * np.exp(-_t(n) / 0.014)
                    mx.add("drums", hat, beat + h * BEAT + (0.02 if h != 0.5 else 0), pan=0.3, gain=g)

        if intro:
            # rising filtered noise into the drop
            n = int(BAR * SR)
            tt = _t(n)
            # band-passed noise whose band climbs through the bar: a soft "whoosh" rather than hiss
            noise = rng.standard_normal(n)
            riser = np.zeros(n)
            steps = 12
            for k in range(steps):
                a, z = k * n // steps, (k + 1) * n // steps
                lo = 400 * 2 ** (k * 3.5 / steps)
                riser[a:z] = _bp(noise, lo, lo * 2.2)[a:z]
            mx.add("fx", riser * (tt / BAR) ** 2.0, t0, gain=0.05)
        if b == 1:
            # soft impact on the drop
            n = int(1.6 * SR)
            tt = _t(n)
            boom = np.sin(2 * np.pi * 38 * tt) * np.exp(-tt / 0.5) + _lp(rng.standard_normal(n), 400) * np.exp(-tt / 0.3) * 0.3
            mx.add("fx", boom, t0, gain=0.35)

    # sidechain: duck the music and bass under each kick so the groove breathes
    duck = np.ones(mx.n)
    for k in kicks:
        i = int(k * SR)
        m = min(int(BEAT * SR), mx.n - i)
        tt = _t(m)
        duck[i:i + m] = np.minimum(duck[i:i + m], 1 - 0.55 * np.exp(-tt / 0.11))
    mx.buses["music"] *= duck[:, None]
    mx.buses["bass"] *= (0.4 + 0.6 * duck)[:, None]

    ir = _reverb_ir()
    wet_src = mx.buses["music"] * 0.5 + mx.buses["drums"] * 0.08 + mx.buses["fx"] * 0.4
    wet = np.stack([fftconvolve(wet_src[:, c], ir[:, c])[: mx.n] for c in (0, 1)], axis=1)
    mix = mx.buses["drums"] + mx.buses["bass"] + mx.buses["music"] + mx.buses["fx"] + wet * 0.28
    mix[:, 0] = _hp(mix[:, 0], 28)                   # clear out sub-rumble below what phones can play
    mix[:, 1] = _hp(mix[:, 1], 28)

    # gentle fade-in and a long fade into the reverb tail
    t = _t(mx.n)
    end = bars * BAR
    fade = np.clip(np.minimum(t / 0.3, (end + 1.2 - t) / 2.6), 0, 1)
    mix *= fade[:, None]
    # bus glue: soft saturation, then a simple look-ahead peak limiter to -1 dBFS
    mix = np.tanh(mix * 1.15) / np.tanh(1.15)
    ceiling = 10 ** (-1 / 20)
    peak = np.abs(mix).max() or 1
    mix = mix * min(1.0, ceiling / peak) if peak < 1.3 else mix / peak * ceiling
    beats = [b * BEAT for b in range(bars * 4)]
    return mix.astype(np.float32), beats


def write_wav(path: Path, bars: int = 8) -> tuple[Path, list[float]]:
    audio, beats = compose(bars)
    data = (np.clip(audio, -1, 1) * 32767).astype(np.int16)
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(data.tobytes())
    return path, beats
