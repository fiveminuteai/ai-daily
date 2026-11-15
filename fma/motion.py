"""How much a rendered Reel moves, measured from the file (15 Nov 2026).

Why: our plain Reels were 38-54% still frames and the duo ones 1-3%, and plain Reels are the ones viewers leave
(the learning loop's one solid finding). Until now nothing measured it. The filter is the one in
echris6/motion-video-kit (MIT): frames at 10 a second, each compared with the one before; a mean luma difference
under STILL counts as a still sample. The bars were set on our own Reels of 15 Nov (duo 1-3% still, plain 38-54%),
not copied from anyone: a duo Reel passes easily and a plain one does not, which is the point.

    python -m fma.motion file.mp4 [...]        prints one line per file
"""
from __future__ import annotations

import re
import shutil
import subprocess
import sys
from pathlib import Path

STILL = 0.35          # mean luma difference (0-255) under which a sample counts as "nothing moved"
CHANGE = 8.0          # a difference this large is a cut, a card or a punch-in: a "visual change"
RATE = 10             # samples a second
OPENING = 3.0         # seconds: where 60% of our viewers leave

_YAVG = re.compile(r"YAVG=([0-9.]+)")


def differences(path: Path, timeout: int = 180) -> list[float] | None:
    """Mean luma difference between consecutive samples, RATE a second; None when ffmpeg is missing or fails."""
    if not shutil.which("ffmpeg"):
        return None
    vf = (f"fps={RATE},scale=320:-1,format=gray,tblend=all_mode=difference,signalstats,"
          "metadata=print:key=lavfi.signalstats.YAVG")
    try:
        run = subprocess.run(["ffmpeg", "-hide_banner", "-nostdin", "-i", str(path), "-vf", vf, "-an", "-f", "null", "-"],
                             capture_output=True, text=True, timeout=timeout, encoding="utf-8", errors="replace")
    except (OSError, subprocess.TimeoutExpired):
        return None
    out = [float(x) for x in _YAVG.findall(run.stderr + run.stdout)]
    return out[1:] if len(out) > 1 else None      # the first sample is compared with nothing


def summarise(diffs: list[float]) -> dict:
    """still: share of samples where nothing moved; still_open: the same for the first OPENING seconds;
    longest_still: the longest unbroken still stretch, seconds; change_gap: mean seconds between visual changes
    (None with fewer than two); changes: how many."""
    n = len(diffs)
    still = [d < STILL for d in diffs]
    opening = still[:int(OPENING * RATE)]
    longest = run = 0
    for s in still:
        run = run + 1 if s else 0
        longest = max(longest, run)
    changes = [i for i, d in enumerate(diffs) if d >= CHANGE and (i == 0 or diffs[i - 1] < CHANGE)]
    gap = (changes[-1] - changes[0]) / RATE / (len(changes) - 1) if len(changes) > 1 else None
    return {"still": round(sum(still) / n, 3), "still_open": round(sum(opening) / max(1, len(opening)), 3),
            "longest_still": round(longest / RATE, 1), "changes": len(changes),
            "change_gap": round(gap, 1) if gap is not None else None}


def measure(path: Path) -> dict | None:
    d = differences(path)
    return summarise(d) if d else None


# The bars. A duo Reel has two talking characters, so it should almost never be still; a plain Reel is cards and may
# hold a card while it is read, but not for half its length.
STILL_MAX = {"duo": 0.10, "plain": 0.30}
STILL_OPEN_MAX = 0.20          # the first 3 seconds, any Reel
LONGEST_STILL_MAX = 2.5        # seconds


def problems(m: dict, duo: bool) -> list[str]:
    out = []
    kind = "duo" if duo else "plain"
    if m["still_open"] > STILL_OPEN_MAX:
        out.append(f"the first {OPENING:.0f} s are {m['still_open']:.0%} still (at most {STILL_OPEN_MAX:.0%})")
    if m["still"] > STILL_MAX[kind]:
        out.append(f"{m['still']:.0%} of the Reel is still (a {kind} Reel: at most {STILL_MAX[kind]:.0%})")
    if m["longest_still"] > LONGEST_STILL_MAX:
        out.append(f"nothing moves for {m['longest_still']} s in a row (at most {LONGEST_STILL_MAX} s)")
    return out


if __name__ == "__main__":
    for f in sys.argv[1:]:
        m = measure(Path(f))
        print(f, m, "|", "; ".join(problems(m, duo=False)) if m else "not measured")
