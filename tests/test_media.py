import json
import shutil

import numpy as np
import pytest
from PIL import Image

from fma import config
from fma.carousel import carousel, key_figure, one_line, plan, short_figure
from fma.music import BAR, SR, compose

POST = json.loads((config.CONTENT_DIR / "posts/2026-10-30.json").read_text(encoding="utf-8"))
SITE = {"name": "Five Minute AI", "base_url": "https://fiveminuteai.net/"}


def test_key_figure_picks_the_biggest_money_or_scale_and_skips_dates():
    assert key_figure("Thrive paid $10 per share, or about $7.6 billion, on 29 October 2026.") == "$7.6 billion"
    assert key_figure("A 1-trillion-parameter model released in 2026.") == "1 trillion"
    assert key_figure("Launched on 29 October 2026 for all users.") == ""
    assert short_figure("$7.6 billion") == "$7.6B" and short_figure("40%") == "40%"


def test_each_story_gets_a_layout_and_the_chart_and_quote_are_used_once():
    kinds = [x["kind"] for x in plan(POST)]
    assert len(kinds) == len(POST["sections"])
    assert kinds.count("chart") <= 1 and kinds.count("quote") <= 1
    assert set(kinds) <= {"chart", "quote", "number", "statement"}
    assert all(len(one_line(s).split()) > 3 for s in POST["sections"])


def test_carousel_renders_a_cover_every_story_and_a_closer(tmp_path):
    paths = carousel(tmp_path, POST, SITE, "Friday 30 October 2026")
    assert len(paths) == len(POST["sections"]) + 2
    assert all(Image.open(p).size == (1080, 1350) for p in paths)


def test_music_is_the_right_length_and_never_clips():
    audio, beats = compose(bars=3)
    assert audio.shape[1] == 2 and audio.shape[0] >= int(3 * BAR * SR)
    assert np.abs(audio).max() <= 10 ** (-1 / 20) + 1e-6          # limiter ceiling: -1 dBFS
    assert len(beats) == 12 and beats[1] - beats[0] == pytest.approx(60 / 100)


def test_reel_frames_are_full_size(tmp_path):
    from fma.reel import H, W, render_frames
    frames = list(render_frames(POST, SITE, "30 Oct 2026", 0.2))
    assert len(frames) == 6 and all(len(f) == W * H * 3 for f in frames)


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg not installed")
def test_build_with_media_links_the_reel_and_slides(tmp_path, monkeypatch):
    from fma import site as site_mod

    def fake_reel(post, site, label, out):            # the real encode takes a minute; the wiring is what matters
        out.write_bytes(b"mp4")
        return out
    monkeypatch.setattr("fma.reel.reel", fake_reel)

    def fake_story_reel(post, section, n, site, out, palette=None):
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(b"mp4")
        return out
    monkeypatch.setattr("fma.story_reel.story_reel", fake_story_reel)
    out = site_mod.build(out_dir=tmp_path / "public", media_on=True)
    page = (out / "share/index.html").read_text(encoding="utf-8")
    assert "carousel.zip" in page and "reel.mp4" in page
    from fma.story_reel import card_stories
    newest = json.loads(sorted((site_mod.config.CONTENT_DIR / "posts").glob("*.json"))[-1].read_text(encoding="utf-8"))
    for k in range(len(card_stories(newest))):                 # one Story Reel per carded story, linked on the page
        assert f"reels/{k + 1:02d}.mp4" in page
    latest = sorted(p.name for p in (out / "share").iterdir() if p.is_dir())[-1]
    assert (out / f"share/{latest}/carousel/01.jpg").exists() and (out / f"share/{latest}/carousel.zip").exists()


def test_every_doodle_cue_has_a_drawing_and_every_drawing_renders_in_every_look():
    from PIL import ImageDraw

    from fma import sketch
    assert not [n for n, _ in sketch.CUES if n not in sketch.LIBRARY]
    layer = Image.new("RGBA", (400, 400), (0, 0, 0, 0))
    ld = ImageDraw.Draw(layer)
    for name in sketch.LIBRARY:
        for mode in ("pen", "chalk", "cutout", "comic"):
            sketch.draw(ld, name, (20, 20, 300), 3.0, (30, 35, 60, 235), (38, 150, 140, 255), mode=mode)
    assert sketch.pick("A hacked Claude Code update reached up to 5,000 developers") == "padlock"   # not "up" -> chart
    assert sketch.pick("Amazon cut 14,000 jobs") == "briefcase"


def test_each_reel_of_the_day_gets_its_own_colour_set_and_changes_get_a_badge():
    from fma.story_reel import change_in, palettes_for
    pals = palettes_for([(0, {"category": "impact"}), (1, {"category": "products"}), (2, {"category": "impact"})])
    assert pals[0] == "dusk" and pals[1] == "cream" and len(set(pals)) == 3          # home set first, never repeated
    assert change_in("Its valuation fell from $1.4 trillion to $1.25 trillion.") == ("$1.4T", "$1.25T")
    assert change_in("It costs $5 a month.") is None
