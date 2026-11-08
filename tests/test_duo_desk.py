"""The duo desk (5 Nov 2026): the guest states no facts, plain words, length budget, all-or-nothing checks."""
from fma import duo_desk


def good():
    return {"guest": "rex", "lines": [
        {"who": "spark", "text": "xAI is accused of running at least 35 turbines without the permission it needed[S1]."},
        {"who": "guest", "text": "Turbines? The ones that burn fuel? I'm a fossil. I take that personally."},
        {"who": "spark", "text": "A group says it broke clean air rules, and it took xAI to court over it[S1]."},
        {"who": "guest", "text": "Clean air. I remember clean air.", "fx": ["beat"]},
        {"who": "spark", "text": "xAI said the turbines can move, so the rules don't apply to them at all[S1]."},
        {"who": "guest", "text": "They can move? I've seen glaciers move faster.", "fx": ["beat"]},
    ]}


def test_a_good_script_passes():
    assert duo_desk.problems(good()) == []


def test_the_guest_states_no_facts():
    d = good()
    d["lines"][1]["text"] = "Thirty-five turbines? In Memphis?"
    bad = " ".join(duo_desk.problems(d))
    assert "numbers" in bad and "Memphis" in bad
    d = good()
    d["lines"][3]["text"] = "Clean air rules matter[S1]."
    assert any("citations" in p for p in duo_desk.problems(d))


def test_hard_words_and_missing_citations_are_caught():
    d = good()
    d["lines"][0]["text"] = "xAI allegedly ran turbines and said they were exempt."
    bad = " ".join(duo_desk.problems(d))
    assert "hard words" in bad and "citation" in bad


def test_length_and_shape():
    d = good()
    d["lines"] = d["lines"][:4]
    assert any("lines" in p for p in duo_desk.problems(d))
    d = good()
    d["lines"].append({"who": "spark", "text": "And that is that[S1]."})
    assert "end on a guest punchline" in duo_desk.problems(d)


def test_script_adds_question_outro_and_sign_off():
    card = {"ask": "Should AI data centres face tougher rules?", "duo": good()}
    guest, lines = duo_desk.script(card, "Tell us in the comments.")
    assert guest == "rex"
    assert lines[0][0] == "spark" and lines[1][0] == "rex"
    assert lines[-4] == ("spark", "Should AI data centres face tougher rules? Tell us in the comments.")
    assert lines[-3] == ("spark", "Five Minute AI.", "card")
    assert lines[-2] == ("rex", "Smarter than your group chat.", "card")
    assert lines[-1] == ("spark", "Low bar.", "card", "beat")


def test_sign_off_rotates_and_never_repeats_back_to_back():
    picks = [duo_desk.sign_off(day * 5 + k)[1][1] for day in (739000, 739001) for k in range(5)]
    assert all(a != b for a, b in zip(picks, picks[1:]))
    assert len(set(picks)) == len(duo_desk.SIGN_OFFS)


def test_old_days_keep_their_reels():
    from fma import site
    sec = {"card": {"duo": good()}}
    assert not site.duo_ok({"date": "2026-11-05"}, sec)


def test_remotion_timeline_and_fallback(monkeypatch, tmp_path):
    """Remotion draws from a timeline built from the audio plan; when it fails, the Python drawing is used."""
    from fma import duo_reel
    pl = {"lines": [{"who": "spark", "text": "Revenue hit $17 billion[S1].", "start": 0.0, "end": 3.0, "said": 2.5,
                     "card": False, "tags": set()},
                    {"who": "doubt", "text": "Party!", "start": 3.0, "end": 4.0, "said": 0.6, "card": False,
                     "tags": {"confetti"}}],
          "seconds": 5.0, "lead": 0.12, "guest": "doubt", "mouth": {"spark": [0.1, 0.5], "doubt": [0.0, 0.2]}}
    tl = duo_reel.timeline({"sources": []}, {"category": "products", "paragraphs": []}, pl)
    assert tl["lines"][0]["fig"] == "$17B" and tl["lines"][0]["groups"] and tl["lines"][1]["tags"] == ["confetti"]
    assert "[S1]" not in tl["lines"][0]["text"] and tl["label"] == "PRODUCTS"
    assert tl['mouth']['spark'] == [0.1, 0.5] and tl['seconds'] == 5.0


def test_number_binding_flags_moves_not_rewordings():
    # 8 Nov 2026: "$1.25 trillion", a year and "50 working" were false alarms that cost two Reels their duo scripts
    from fma.duo_desk import binding_problems as b
    assert b(["Meta has 23 data centres[S6]."], "Meta has data centers in 23 states, she said.")
    assert not b(["OpenAI is valued at $1.25 trillion[S2]."], "OpenAI is valued at $1.25 trillion and raised more.")
    assert not b(["In 2026 the claim emerged[S1]."], "A 2026 report made the claim.")
    assert not b(["About 50 people were working on it[S1]."], "About 50 focused on frontier research.")


def test_metr_is_said_meter():
    from fma.voice import spoken
    assert spoken("METR's authors say") == "Meter's authors say"


def test_solo_report_signs_off_with_the_name_only():
    """8 Nov 2026: a straight report has Spark alone, no guest lines and no gag in the sign-off."""
    card = {"ask": "Should chip makers check their buyers more closely[S2]?",
            "duo": {"guest": "solo", "lines": [{"who": "spark", "text": "A memo claims X[S2]."}]}}
    guest, lines = duo_desk.script(card, "Tell us below.")
    assert guest == "solo"
    assert [ln[0] for ln in lines] == ["spark"] * 3
    assert lines[-1] == ("spark", "Five Minute AI.", "card")
