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


def test_reels_already_approved_keep_their_look():
    from fma.story_reel import palettes_for
    assert palettes_for([(0, {"category": "impact"})], "2026-11-01") == ["classic"]
    assert palettes_for([(0, {"category": "impact"})], "2026-11-02") == ["dusk"]


def test_reels_go_to_the_strongest_stories_from_2_nov():
    from fma.story_reel import card_stories
    def sec(cat, interest, hook="Acme cut prices[S1].", pubs=("S1",)):
        return {"category": cat, "paragraphs": ["".join(f"x[{p}]" for p in pubs)],
                "card": {"hook": hook, "points": ["a", "b"], "interest": interest}}
    sources = [{"id": "S1", "publisher": "A"}, {"id": "S2", "publisher": "B"}]
    secs = [sec("architecture", 3), sec("products", 2), sec("impact", 5), sec("models", 3, pubs=("S1", "S2")),
            sec("tools", 4)]
    new = card_stories({"date": "2026-11-02", "sections": secs, "sources": sources})
    assert [n for n, _ in new] == [2, 3, 4]          # interest 5, two publishers, interest 4; post order kept
    old = card_stories({"date": "2026-11-01", "sections": secs, "sources": sources})
    assert [n for n, _ in old] == [0, 1, 2]          # approved days never change


def test_voiced_scenes_fit_the_voice_on_the_beat(monkeypatch):
    # 4 Nov 2026: Pavan heard the speed change line to line, because long lines were sped up to fit fixed scenes.
    # Now one pace for every line and the scenes stretch to fit, ending on a beat, never shorter than 2 bars.
    import numpy as np

    from fma import story_reel, voice
    lengths = {"short": 1.0, "long line here": 7.0, "q?": 2.0, voice.OUTRO: 3.0}
    monkeypatch.setattr(voice, "say", lambda text, **kw: np.full(int(lengths.get(text, 4.0) * voice.SR), 0.2,
                                                                   np.float32))
    card = {"hook": "short", "points": ["long line here", "short"], "take": "short", "ask": "q?"}
    plan = story_reel.voice_plan(card, 1)
    assert len(plan["lens"]) == 4
    for k, spoken_s in zip(["hook", "p0", "p1", "take"], plan["lens"]):
        assert spoken_s >= 2 * story_reel.BAR - 1e-9
        assert abs(spoken_s / story_reel.BEAT - round(spoken_s / story_reel.BEAT)) < 1e-6
        assert spoken_s >= plan["said"][k] + 0.3
    assert plan["lens"][1] > 2 * story_reel.BAR             # the long line got a longer scene, not a faster voice
    assert plan["outro_at"] > plan["said"]["ask"]           # the closing line comes after the question
    assert plan["seconds"] > sum(plan["lens"]) + plan["outro_at"] + 3.0
    assert len(plan["mouth"]) and plan["mouth"].max() > 0.5


def test_names_are_respelled_for_the_narrator():
    from fma import voice
    assert voice.spoken("NotebookLM hit $17 billion for K-12[S1].") == "NotebookLM hit 17 billion dollars for K to 12."


def test_pulse_numbers_appear_only_when_spoken():
    # 5 Nov 2026: a count-up showed "$15B" and "$1B" on the way to a $17 billion line; now the real figure appears,
    # whole, when the voice reaches it
    from fma import pulse_reel as pr
    assert pr.figure("Quarterly revenue reached $17 billion, up from $11.5 billion[S6].") == "$17B"
    assert pr.figure("Anthropic now spends 58% of its revenue on compute[S6].") == "58%"
    assert pr.figure("Apple is letting Siri act inside apps[S5].") == ""
    timed = pr.word_times("Quarterly revenue reached $17 billion, up from $11.5 billion.", 4.0, 0.3)
    at = pr.figure_time(timed, "$17B")
    assert [w for w, t in timed if t == at] == ["$17"]
    assert all(t2 > t1 for (_, t1), (_, t2) in zip(timed, timed[1:]))


def test_pulse_captions_come_in_short_chunks():
    from fma import pulse_reel as pr
    groups = pr.chunks(pr.word_times("Should schools be able to keep Search without AI?", 3.0, 0.3))
    assert all(len(g) <= 3 and len(" ".join(w for w, _ in g)) <= 18 for g in groups)
    assert " ".join(w for g in groups for w, _ in g) == "Should schools be able to keep Search without AI?"


def test_decimals_are_read_digit_by_digit():
    # 5 Nov 2026: "$11.5 billion" was heard as "11 billion, 5 billion"
    from fma import voice
    assert voice.spoken("up from $11.5 billion") == "up from 11 point 5 billion dollars"
    assert voice.spoken("paying SpaceX $1.25 billion") == "paying SpaceX 1 point 2 5 billion dollars"
    assert voice.spoken("with $5.0 billion") == "with 5 billion dollars"


def test_hard_names_are_spoken_from_fixed_phonemes(monkeypatch):
    # 5 Nov 2026: "SpaceX" was read as two stressed words ("Space X"), AWS as "awes", Qwen as "queue-wen"
    from fma import voice

    class Tok:
        def phonemize(self, text, lang):
            return f"<{text.strip()}>"

    class Engine:
        tokenizer = Tok()

    monkeypatch.setattr(voice, "_engine", lambda: Engine())
    assert voice.phonemes("paying SpaceX now", "en-us") == "<paying> spˈeɪsɛks <now>"
    assert voice.phonemes("AWS and Qwen.", "en-us") == "ˈeɪ dˈʌbəljˌuː ˈɛs <and> tʃwˈɛn <.>"
    assert voice.phonemes("nothing hard here", "en-us") is None
    assert voice.phonemes("SpaceXR is not SpaceX", "en-us").endswith("spˈeɪsɛks")     # whole words only


def test_doubt_draws_talking_and_listening():
    from fma import doubt
    a = doubt.draw(200, 1.0, 0.8, True)
    b = doubt.draw(200, 1.0, 0.0, False)
    assert a.size == b.size == (200, 200) and a.getbbox() and b.getbbox()
    assert list(a.getdata()) != list(b.getdata())          # talking and listening look different


def test_spark_shapes_follow_the_words():
    from fma import spark
    assert spark.shape_for("Its compute bill hit $10 billion") == "chip"
    assert spark.shape_for("Quarterly revenue reached $17 billion") == "coin"
    assert spark.shape_for("Is the AI boom worth what it costs?") == "bubble"
    assert spark.shape_for("As Anthropic heads for an IPO, margins worsen") == "blob"


def test_counts_keep_their_limits_on_screen():
    # 5 Nov 2026: "at least 35 turbines" must never show as a bare "35"
    from fma.pulse_reel import figure
    assert figure("It alleges xAI ran at least 35 combustion turbines.") == "35+ turbines"
    assert figure("Up to 5,000 users were exposed.") == "up to 5,000 users"
    assert figure("It has 12 data centres.") == "12 data centres"
    assert figure("In 2026 the judge ruled.") == ""


def test_syllables_count_vowel_groups():
    from fma import voice
    assert voice.syllables("spˈeɪsɛks") == 2
    assert voice.syllables("ˈeɪ dˈʌbəljˌuː ˈɛs") == 5
