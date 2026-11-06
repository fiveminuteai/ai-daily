"""Mouth shapes from the voice (6 Nov 2026), with Rhubarb Lip Sync (github.com/DanielSWolf/rhubarb-lip-sync, MIT):
for each spoken line it returns timed mouth shapes, the classic cartoon set:
A closed (m, b, p) · B slightly open (most consonants) · C open (e) · D wide open (a) · E rounded (o) · F puckered
(u, w) · G teeth on lip (f, v) · H tongue up (l) · X rest.
The Reel's mouths take these shapes instead of only opening wider with loudness. If Rhubarb is not installed the
Reel uses the loudness mouth, so nothing depends on it."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent


def binary() -> str | None:
    env = os.environ.get("FMA_RHUBARB")
    if env and Path(env).exists():
        return env
    for p in sorted((ROOT / ".tools").glob("Rhubarb-Lip-Sync-*/rhubarb*")):
        if p.suffix in ("", ".exe"):
            return str(p)
    return shutil.which("rhubarb")


def cues(clip: np.ndarray, text: str, sr: int) -> list[list]:
    """[[start, end, shape], ...] for one spoken line (seconds from the start of the clip)."""
    from .voice import write_wav
    exe = binary()
    if not exe:
        return []
    with tempfile.TemporaryDirectory() as tmp:
        wav, txt, out = Path(tmp) / "l.wav", Path(tmp) / "l.txt", Path(tmp) / "l.json"
        write_wav(wav, clip)
        txt.write_text(text, encoding="utf-8")
        r = subprocess.run([exe, "-f", "json", "-d", str(txt), "--extendedShapes", "GHX", "-q", str(wav), "-o", str(out)],
                           capture_output=True, text=True, timeout=300)
        if r.returncode != 0 or not out.exists():
            return []
        return [[round(c["start"], 3), round(c["end"], 3), c["value"]] for c in json.loads(out.read_text())["mouthCues"]]


def visemes(clips: list[tuple[str, float, np.ndarray, str]], sr: int) -> dict[str, list[list]]:
    """Each speaker's mouth shapes across the whole Reel, from (who, start time, clip, text) per line; lines run in
    parallel."""
    if not binary() or not clips:
        return {}
    with ThreadPoolExecutor(max_workers=min(8, os.cpu_count() or 4)) as pool:
        per = list(pool.map(lambda c: cues(c[2], c[3], sr), clips))
    out: dict[str, list[list]] = {}
    for (who, at, _s, _t), cs in zip(clips, per):
        out.setdefault(who, []).extend([[round(at + a, 3), round(at + b, 3), v] for a, b, v in cs])
    return out
