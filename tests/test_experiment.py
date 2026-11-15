"""One test Reel a day, tagged on its card (15 Nov 2026)."""
from fma import config
from fma.experiment import assign


def post(n=4):
    return {"date": "2026-11-16", "sections": [
        {"title": f"s{k}", "card": {"hook": f"Acme did thing {k}[S1].", "points": ["a[S1].", "b[S1]."], "reel": 9 - k}}
        for k in range(n)]}


def test_the_chosen_reel_gets_the_arm_and_the_others_do_not():
    site = {"experiment": {"arm": "short-close", "reel": 4, "until": "2026-12-06"}}
    p = assign(post(), site, 4)
    assert [s["card"].get("arm") for s in p["sections"]] == [None, None, None, "short-close"]


def test_no_test_when_the_slot_is_missing_the_arm_unknown_or_the_date_past():
    for site in ({}, {"experiment": {"arm": "short-close", "reel": 5}}, {"experiment": {"arm": "made-up", "reel": 1}},
                 {"experiment": {"arm": "short-close", "reel": 1, "until": "2026-11-01"}}):
        assert not any(s["card"].get("arm") for s in assign(post(), site, 4)["sections"])


def test_the_short_close_ends_on_the_question_and_the_name():
    from fma.duo_desk import script
    card = {"ask": "Would you pay?", "duo": {"guest": "doubt", "lines": [
        {"who": "spark", "text": "Acme shipped Nova[S1]."}, {"who": "guest", "text": "Bold."}]}}
    _, normal = script(card, "Follow for more.")
    _, short = script({**card, "arm": "short-close"}, "Follow for more.")
    assert len(normal) - len(short) == 2 and short[-1][:2] == ("spark", "Five Minute AI.") and "card" in short[-1]
    assert short[:-1] == normal[:len(short) - 1]                      # the story itself is untouched


def test_the_live_config_names_a_known_arm():
    exp = config.site_config().get("experiment")
    assert exp is None or (exp["arm"] in __import__("fma.experiment", fromlist=["ARMS"]).ARMS and isinstance(exp["reel"], int))
