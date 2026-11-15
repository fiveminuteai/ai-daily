"""Captions follow the voice, not a guess (15 Nov 2026: words were timed by their share of the letters)."""
import numpy as np
import pytest

from fma import timing

SR = 24000
TEXT = "Nvidia sold 3,378,378 shares for $250 million[S1]."     # 7 spoken words in our text


def clip(seconds: float) -> np.ndarray:
    return np.zeros(int(seconds * SR), np.float32)


def test_heard_words_set_the_times_and_misheard_ones_sit_between_their_neighbours():
    # the model hears the number and the money differently; the plain words give the anchors
    listen = lambda s, sr: [("Nvidia", 0.10), ("sold", 0.62), ("three", 0.95), ("million", 1.3), ("shares", 2.40),
                            ("for", 2.80), ("two", 3.0), ("hundred", 3.2), ("million.", 3.9)]
    got = timing.word_times(clip(4.4), SR, TEXT, listen=listen)
    words, times = [w for w, _ in got], [t for _, t in got]
    assert words == ["Nvidia", "sold", "3,378,378", "shares", "for", "$250", "million."]
    assert times[0] == 0.10 and times[1] == 0.62 and times[3] == 2.40 and times[4] == 2.80 and times[6] == 3.9
    assert 0.62 < times[2] < 2.40 and 2.80 < times[5] < 3.9          # filled in, in order
    assert times == sorted(times)


def test_too_little_matched_or_times_running_backwards_keeps_the_old_guess():
    assert timing.word_times(clip(4.4), SR, TEXT, listen=lambda s, sr: [("hello", 0.1), ("world", 0.5)]) is None
    back = lambda s, sr: [("Nvidia", 2.0), ("sold", 1.0), ("shares", 0.5), ("for", 0.2), ("million", 0.1)]
    assert timing.word_times(clip(4.4), SR, TEXT, listen=back) is None


def test_a_broken_speech_model_never_costs_a_reel(monkeypatch):
    def boom(s, sr):
        raise RuntimeError("no model")
    monkeypatch.setattr(timing, "_failed", False)
    assert timing.word_times(clip(2.0), SR, TEXT, listen=boom) is None
    assert timing._failed                      # and it is not tried again this run
    monkeypatch.setattr(timing, "_failed", False)
    monkeypatch.setenv("FMA_ALIGN", "0")
    assert not timing.available()


def test_the_duo_plan_uses_real_times_when_it_has_them():
    from fma.duo_reel import line_times
    ln = {"text": "Two words[S1].", "said": 1.0, "words": [("Two", 0.3), ("words.", 0.9)]}
    assert line_times(ln, 0.12) == [("Two", 0.3), ("words.", 0.9)]
    ln.pop("words")
    assert [w for w, _ in line_times(ln, 0.12)] == ["Two", "words."]


@pytest.mark.skipif(not timing.available(), reason="needs faster-whisper")
def test_the_real_model_times_a_real_kokoro_line():
    from fma import voice
    if not voice.available():
        pytest.skip("needs Kokoro")
    text = "Google says the new model is cheaper, and it reads a whole book in one go[S1]."
    s = voice.say("Google says the new model is cheaper, and it reads a whole book in one go.", voice="spark-strong")
    got = timing.word_times(s, voice.SR, text)
    assert got and [w for w, _ in got][0] == "Google" and len(got) == 16
    times = [t for _, t in got]
    assert times == sorted(times) and times[-1] < len(s) / voice.SR
    # the guess and the clock disagree somewhere by more than a tenth of a second: that drift is what this fixes
    from fma.pulse_reel import word_times as guessed
    guess = [t for _, t in guessed(text, len(s) / voice.SR, 0.0)]
    print("max drift", max(abs(a - b) for a, b in zip(times, guess)))
