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
    assert lines[-2] == ("rex", "Still not taking your job.", "card")
    assert lines[-1] == ("spark", "Yet.", "card", "beat", "sweat")


def test_old_days_keep_their_reels():
    from fma import site
    sec = {"card": {"duo": good()}}
    assert not site.duo_ok({"date": "2026-11-05"}, sec)
