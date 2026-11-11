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


def test_closing_order_tries_the_pick_then_shorter_closings():
    order = duo_desk.closing_order(7)
    assert order[0] == 7 % len(duo_desk.SIGN_OFFS) and sorted(order) == list(range(len(duo_desk.SIGN_OFFS)))
    lengths = [len(duo_desk.SIGN_OFFS[i][0] + duo_desk.SIGN_OFFS[i][1]) for i in order[1:]]
    assert lengths == sorted(lengths)


# ---- banter (8 Nov 2026): Spark's comebacks, the guest's topper and callback, worn-out lines

def banter_opt():
    return {"comeback": "Rex, you're not even on fire.", "topper": "Not yet. Give it a minute.",
            "callback": "Moving turbines. Still faster than my paperwork."}


def test_banter_puts_the_comeback_after_the_first_reaction_and_ends_on_the_callback():
    d = duo_desk.add_banter(good(), banter_opt())
    assert [ln["who"] for ln in d["lines"]] == ["spark", "guest", "spark", "guest", "spark", "guest", "spark", "guest"]
    assert d["lines"][2]["kind"] == "comeback" and d["lines"][3]["fx"] == ["beat"]
    assert d["lines"][-1]["text"].startswith("Moving turbines") and d["lines"][-1]["fx"] == ["beat"]
    assert duo_desk.problems(d) == []


def test_a_comeback_states_no_facts():
    d = duo_desk.add_banter(good(), {**banter_opt(), "comeback": "That was 35 turbines, Rex[S1]."})
    bad = " ".join(duo_desk.problems(d))
    assert "comeback may not say numbers" in bad and "citations" in bad
    d = duo_desk.add_banter(good(), {**banter_opt(), "comeback": "Tell it to Memphis, Rex."})
    assert any("may not name" in p for p in duo_desk.problems(d))


def test_the_guest_calls_itself_a_box_once_at_most():
    d = duo_desk.add_banter(good(), {**banter_opt(), "callback": "And I'm a fossil. Still faster."})
    assert any("more than once" in p for p in duo_desk.problems(d))      # line 2 already says "I'm a fossil"


def test_worn_out_phrases():
    stale = {"i'm a box"}
    assert duo_desk.is_stale("Even I plan ahead. I'm a box.", stale)
    assert not duo_desk.is_stale("Even I plan ahead.", stale)


def test_only_fact_lines_are_fact_checked():
    d = duo_desk.add_banter(good(), banter_opt())
    facts = [ln for ln in d["lines"] if duo_desk.is_fact(ln)]
    assert len(facts) == 3 and all("[S1]" in ln["text"] for ln in facts)


class Chain:
    def __init__(self, reply):
        self.reply = reply

    def ask_json(self, *a, **kw):
        return self.reply


def test_banter_step_keeps_a_passing_option_and_drops_a_rule_breaker(monkeypatch):
    monkeypatch.setattr(duo_desk, "stale_phrases", lambda guest, *a, **k: set())
    bad = {**banter_opt(), "comeback": "It was 35 of them[S1]."}
    out = duo_desk.banter_step(Chain({"options": [bad, banter_opt()]}), good())
    assert out and out["lines"][2]["text"] == "Rex, you're not even on fire."
    assert duo_desk.banter_step(Chain({"options": [bad]}), good()) is None


def test_a_comeback_cannot_answer_a_line_not_said_yet(monkeypatch):
    monkeypatch.setattr(duo_desk, "stale_phrases", lambda guest, *a, **k: set())
    early = {**banter_opt(), "comeback": "Clean air rules? You love those.", "topper": "Love is a strong word."}
    assert duo_desk.banter_step(Chain({"options": [early]}), good()) is None      # clean air comes in line 3


# ---- decency (9 Nov 2026): "healthy, not mean, not violent"

def test_indecent_jokes_fail_on_any_story():
    d = duo_desk.add_banter(good(), {**banter_opt(), "comeback": "At least the spy got laid."})
    assert any("not decent" in p for p in duo_desk.problems(d))
    d = good()
    d["lines"][3]["text"] = "Somebody shoot the turbines."
    assert any("not decent" in p for p in duo_desk.problems(d))


def test_a_sensitive_story_keeps_jokes_off_private_life_and_has_no_comebacks():
    d = good()
    d["lines"][1]["text"] = "Romantic, but bad security."
    assert not any("private life" in p for p in duo_desk.problems(d))           # an ordinary story
    d["sensitive"] = True
    assert any("private life" in p for p in duo_desk.problems(d))
    talk = duo_desk.add_banter(good(), banter_opt())
    talk["sensitive"] = True
    assert any("no comebacks" in p for p in duo_desk.problems(talk))


def test_sensitive_stories_are_recognised():
    assert duo_desk.is_sensitive({"title": "CEO admits affair with suspected spy", "paragraphs": []})
    assert not duo_desk.is_sensitive({"title": "OpenAI raises $11 billion", "paragraphs": ["It raised money."]})
    assert duo_desk.is_sensitive({"title": "Nvidia board probes CEO's link to suspected spy",
                                  "paragraphs": ["He admitted to an affair with a former executive[S1]."]})


def test_every_published_joke_still_passes_the_filter():
    import json
    from pathlib import Path
    rows = [json.loads(x) for x in Path("data/bank/duo_pairs.jsonl").read_text(encoding="utf-8").splitlines() if x]
    assert all(not duo_desk.joke_problems(r["joke"]) for r in rows)


def test_dates_and_model_names_are_not_moved_numbers():
    src = "In an October 16 edit to its blog, Google changed the page. Claude Fable 5.2 and Mythos 5.2 solved two problems."
    assert duo_desk.binding_problems(["Google changed its blog on October 16 blog post[S1]."], src) == []
    assert duo_desk.binding_problems(["Claude Fable 5.2 solved two open problems[S1]."], src) == []
    # a real moved number is still caught
    src2 = "Meta has data centres in 23 states."
    assert duo_desk.binding_problems(["Meta has 23 data centres[S1]."], src2)


def test_a_duo_falls_back_to_the_checked_card_when_the_facts_step_gives_up():
    card = {"hook": "Google says connected Gmail files can reach human reviewers[S4].",
            "points": ["Testers found Gemini pulls files in the background, without any tags[S4].",
                       "Google's own advice is not to connect apps holding confidential files[S4].",
                       "Results vary each run, the testers found[S4]."]}
    lines = duo_desk.card_facts(card)
    assert lines and len(lines) == 3 and all("[S4]" in t for t in lines)
    assert duo_desk.card_facts({"hook": "Too short[S1].", "points": []}) is None


def test_duo_facts_are_fact_checked_before_the_jokes_are_written():
    """11 Nov 2026: a duo line said "a massive $1.4 trillion" for a source that never says it; layer 1 then dropped
    the whole duo after it was written. The writer now checks its facts first and falls back to the card's lines."""
    from fma.duo_desk import card_facts, prechecked
    from fma.verify import Verifier, cites
    src = [{"id": "S1", "title": "All seven Anthropic founders will each cash out about $250M in IPO", "url": "u",
            "text": "Each of the seven co-founders plans to sell 3,378,378 shares. At the midrange of $74, each founder "
                    "would receive just shy of $250 million. Collectively, the founders will control 51.1% of the votes."}]
    v = Verifier(src)
    check = lambda t: v.sentence(t, "duo pre-check", ["S1"])
    bad = ["Anthropic's IPO could value the company at a massive $1.4 trillion[S1].",
           "Each of the seven co-founders plans to sell 3,378,378 shares[S1].",
           "The founders will control 51.1% of the votes[S1]."]
    assert prechecked(bad, check) is None                      # two good lines are not a duo
    card = {"hook": "Anthropic founders will each get nearly $250 million[S1].",
            "points": ["Each of the seven co-founders plans to sell 3,378,378 shares[S1].",
                       "The founders will control 51.1% of the votes[S1]."]}
    lines = prechecked(bad, check) or prechecked(card_facts(card), check)
    assert lines and len(lines) == 3 and all(cites(t) for t in lines)
    assert prechecked(bad, None) == bad                        # no checker: unchanged (tests, local runs)
