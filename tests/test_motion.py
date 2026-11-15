"""A Reel that stands still is measured and reported (15 Nov 2026: plain Reels were 38-54% still frames)."""
import shutil
import subprocess

import pytest

from fma import motion
from fma.health import Report, check_media


def test_summary_counts_still_samples_the_opening_and_changes():
    # 5 s: the first 2 s still, then moving, one cut at 3.0 s and one at 4.5 s
    d = [0.0] * 20 + [2.0] * 10 + [30.0] + [2.0] * 14 + [30.0] + [2.0] * 4
    m = motion.summarise(d)
    assert m["still"] == 0.4 and m["still_open"] == round(20 / 30, 3)
    assert m["longest_still"] == 2.0 and m["changes"] == 2 and m["change_gap"] == 1.5


def test_bars_are_stricter_for_a_duo_and_name_the_opening():
    still_plain = {"still": 0.25, "still_open": 0.5, "longest_still": 1.0, "changes": 4, "change_gap": 8.0}
    assert any("first 3 s" in p for p in motion.problems(still_plain, duo=False))
    assert any("duo Reel" in p for p in motion.problems({**still_plain, "still_open": 0.0}, duo=True))
    assert motion.problems({**still_plain, "still_open": 0.0}, duo=False) == []
    assert motion.problems({"still": 0.02, "still_open": 0.0, "longest_still": 0.1, "changes": 9, "change_gap": 3.6},
                           duo=True) == []


def test_the_health_check_fails_a_still_duo_and_warns_on_a_still_plain_reel():
    still = {"still": 0.5, "still_open": 0.5, "longest_still": 3.0, "changes": 3, "change_gap": 9.0}
    post = {"slug": "s", "sections": [{"card": {"duo": {"lines": []}}}, {"card": {}}]}
    media = {"slug": "s", "voice": True, "slides": ["a"], "reels": [
        {"file": "reels/01.mp4", "duo": "doubt", "story": 0, "seconds": 36, "audio": True, "cover": True, "motion": still},
        {"file": "reels/02.mp4", "duo": None, "story": 1, "seconds": 36, "audio": True, "cover": True, "motion": still}]}
    r = Report("2026-11-15")
    check_media(r, media, post)
    fails = [i["msg"] for i in r.items if i["level"] == "FAIL"]
    warns = [i["msg"] for i in r.items if i["level"] == "WARN"]
    assert any("reels/01.mp4" in d and "still" in d for d in fails)
    assert any("reels/02.mp4" in d and "still" in d for d in warns) and not any("reels/02.mp4" in d for d in fails)


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="needs ffmpeg")
def test_a_real_still_video_and_a_moving_one_are_told_apart(tmp_path):
    still, moving = tmp_path / "still.mp4", tmp_path / "moving.mp4"
    for src, out in (("color=c=navy:s=320x568:d=4", still), ("testsrc2=s=320x568:d=4", moving)):
        subprocess.run(["ffmpeg", "-loglevel", "error", "-f", "lavfi", "-i", src, "-r", "30", "-pix_fmt", "yuv420p",
                        str(out)], check=True, stdin=subprocess.DEVNULL)
    a, b = motion.measure(still), motion.measure(moving)
    assert a["still"] > 0.95 and b["still"] < 0.05
    assert motion.problems(a, duo=False) and not motion.problems(b, duo=True)
