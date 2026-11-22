"""The daily carousel made with the Reels' rules (fma/carousel_reel.py, 22 Nov 2026)."""
import json
from pathlib import Path

import pytest

from fma import carousel_reel as cr

ROOT = Path(__file__).resolve().parent.parent


def post_of(date):
    return json.loads((ROOT / f"content/posts/{date}.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("date", ["2026-11-21", "2026-11-22"])
def test_no_line_appears_on_two_slides_and_the_cover_is_short(date):
    from fma.gate import dedupe_stories
    post, _ = dedupe_stories(post_of(date))
    slides = cr.build_slides(post, {"base_url": "https://fiveminuteai.net/"}, "Saturday 21 November 2026")
    assert slides[0]["kind"] == "cover" and slides[-1]["kind"] == "close"
    assert len(slides) == len(post["sections"]) + 2
    assert len(slides[0]["title"].split()) <= cr.SHORT_WORDS
    said = [x for s in slides[:-1] for x in [s["title"], *s["points"], s["bubble"] or ""] if x]
    assert len(said) == len(set(said))                                   # nothing said twice, word for word
    for k, s in enumerate(slides[1:-1]):                                 # nor a point restating its own title
        assert not any(cr.repeats(p, [s["title"]]) for p in s["points"])
    assert slides[1]["title"] != slides[0]["title"]                      # the lead's slide doesn't repeat the cover
    assert slides[-1]["title"].endswith("?")
    text = json.dumps(post, ensure_ascii=False).replace("‑", "-")
    for s in slides[1:-1]:                                               # every word comes from the checked post
        assert all(p.rstrip(".")[:40].replace("‑", "-") in text for p in s["points"])


def test_a_repeat_is_most_of_the_same_words():
    assert cr.repeats("Nvidia stops selling H200 chips in China.", ["Nvidia stops selling H200 chips in China"])
    assert not cr.repeats("The board blamed a pattern of lying.", ["Nvidia stops selling H200 chips in China"])


def test_the_key_number_is_money_scale_or_a_share():
    assert cr.key_number("Anthropic IPO", ["It expects roughly $900 billion in compute costs."]) == "$900B"
    assert cr.key_number("Released in 2026", ["It has 3 modes."]) == ""


def test_when_remotion_fails_the_plain_slides_still_go_out(tmp_path, monkeypatch):
    from fma import carousel
    monkeypatch.setattr(cr, "render", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("no browser")))
    paths = carousel.carousel(tmp_path, post_of("2026-11-21"), {"base_url": "https://fiveminuteai.net/", "name": "Five Minute AI"},
                              "Saturday 21 November 2026")
    assert len(paths) == len(post_of("2026-11-21")["sections"]) + 2 and all(p.exists() for p in paths)
