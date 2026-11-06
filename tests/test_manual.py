"""Manual days and the knowledge bank (6 Nov 2026)."""
import json
from datetime import datetime, timezone

from fma import bank, manual


def _card(lines, ask="Would you want a data centre in your town?"):
    return {"ask": ask, "duo": {"guest": "rex", "lines": lines}}


def test_duo_length_estimate_matches_the_measured_renders():
    # the 6 Nov Rex script after its cut rendered at 38.6 s
    lines = [{"who": "spark", "text": "Meta says the midterm election results will make data centres much harder to build[S6]."},
             {"who": "guest", "text": "People voting against big power-hungry buildings? Finally, my people."},
             {"who": "spark", "text": "Meta has data centres in 23 states, and five are planned as huge power projects[S6]."},
             {"who": "guest", "text": "Huge and hungry. I remember huge and hungry. It ended badly.", "fx": ["beat"]},
             {"who": "spark", "text": "Meta says towns only want them when they get something back, so it pays its own electricity bill[S6]."},
             {"who": "guest", "text": "Paying your own bills. Even I never managed that.", "fx": ["beat"]}]
    assert abs(manual.duo_seconds(_card(lines)) - 38.6) < 1.5


def test_passed_reel_slots_move_to_the_next_free_slot():
    site = {"schedule": {"daily": "05:45", "reels": ["09:00", "13:00", "19:00"], "stats": "23:30"}}
    q = {"items": [{"id": f"r{k}", "kind": "reel", "status": "approved", "scheduled_at": t} for k, t in
                   enumerate(["2026-11-06T03:30:00+00:00", "2026-11-06T07:30:00+00:00", "2026-11-06T13:30:00+00:00"], 1)]}
    manual.reslot(q, "2026-11-06", site, datetime(2026, 11, 6, 5, 0, tzinfo=timezone.utc))   # 10:30 India time
    times = [it["scheduled_at"] for it in q["items"]]
    assert times == ["2026-11-06T07:30:00+00:00", "2026-11-06T13:30:00+00:00", "2026-11-07T03:30:00+00:00"]
    assert len(set(times)) == 3


def test_bank_keeps_checked_content_once_per_day(tmp_path, monkeypatch):
    monkeypatch.setattr(bank, "BANK", tmp_path / "bank")
    post = {"sections": [{"title": "T", "category": "policy", "paragraphs": ["A fact[S1]."],
                          "card": {"hook": "Hook[S1].", "points": ["p[S1]."], "ask": "Q?", "reel": 7,
                                   "duo": {"guest": "rex", "lines": [{"who": "spark", "text": "Fact[S1]."},
                                                                     {"who": "guest", "text": "Joke."}]}}}]}
    (tmp_path / "2026-11-06.json").write_text(json.dumps(post), encoding="utf-8")
    assert bank.add("2026-11-06", tmp_path) == {"sections.jsonl": 1, "cards.jsonl": 1, "duo_pairs.jsonl": 1}
    bank.add("2026-11-06", tmp_path)                       # twice: still one of each
    assert bank.stats() == {"sections.jsonl": 1, "cards.jsonl": 1, "duo_pairs.jsonl": 1}
    assert bank.joke_pairs("rex") == [("Fact.", "Joke.")]
