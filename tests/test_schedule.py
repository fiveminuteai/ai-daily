"""The blog's schedule and lineup caps come from config/site.yaml, where the control app edits them (4 Nov 2026)."""
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from fma import clock
from fma import social_queue as sq
from fma.rank import lineup_caps

ROOT = Path(__file__).resolve().parents[1]
utc = lambda h, m=0, d=4: datetime(2026, 11, d, h, m, tzinfo=timezone.utc)  # noqa: E731


def test_the_defaults_reproduce_the_original_times():
    # exactly the five events the clock ran before the times moved into config
    # plus the late sweep at 22:30 India time (17:00 UTC, 10 Nov 2026) for anything still due
    assert clock.EVENTS == (("00:15", "daily.yml"), ("03:30", "post-scheduled.yml"), ("07:30", "post-scheduled.yml"),
                            ("13:30", "post-scheduled.yml"), ("17:00", "post-scheduled.yml"), ("18:00", "collect-stats.yml"))
    assert clock.events(clock.DEFAULT) == clock.EVENTS


def test_the_live_config_schedule_is_valid_and_read_the_same_by_the_clock_and_yaml():
    # whatever the control app last saved: the clock's own parser and the YAML loader agree, and nothing fell back
    text = (ROOT / "config/site.yaml").read_text(encoding="utf-8")
    raw = __import__("yaml").safe_load(text)["schedule"]
    sched = clock.read_schedule(text)
    assert sched == {"daily": raw["daily"], "reels": tuple(raw["reels"]), "stats": raw["stats"],
                     **({"carousel": raw["carousel"]} if raw.get("carousel") else {})}


def test_an_edited_schedule_moves_the_clock():
    text = 'x: 1\nschedule:\n  daily: "04:30"\n  reels: ["08:00", "20:30"]\n  stats: "22:00"\npipeline:\n  attempts: 2\n'
    sched = clock.read_schedule(text)
    assert sched == {"daily": "04:30", "reels": ("08:00", "20:30"), "stats": "22:00"}
    ev = clock.events(sched)
    assert ev == (("02:30", "post-scheduled.yml"), ("15:00", "post-scheduled.yml"), ("16:30", "collect-stats.yml"),
                  ("17:00", "post-scheduled.yml"), ("23:00", "daily.yml"))                             # 04:30 India time is 23:00 UTC the day before
    assert clock.plan(utc(22, 0), ev=ev) == (60 * 60 + 16, "daily.yml")
    assert clock.plan(utc(2, 0), ev=ev) == (30 * 60 + 16, "post-scheduled.yml")


@pytest.mark.parametrize("cfg, field", [
    ({"daily": "08:30"}, "daily"),                          # after 07:00: the laptop backup would post first
    ({"daily": "5:45"}, "daily"),
    ({"daily": "25:00"}, "daily"),
    ({"reels": ["06:30"]}, "reels"),                        # under 90 minutes after the 05:45 post
    ({"reels": ["09:00", "09:15"]}, "reels"),               # under 30 minutes apart
    ({"reels": ["13:00", "09:00"]}, "reels"),               # out of order
    ({"reels": ["09:00", "11:00", "13:00", "15:00", "17:00", "19:00"]}, "reels"),   # more than 5 (3 until 7 Nov 2026)
    ({"reels": []}, "reels"),
    ({"reels": ["23:30"]}, "reels"),
    ({"stats": "19:00"}, "stats"),
    ({"stats": "nope"}, "stats"),
])
def test_a_bad_value_falls_back_to_the_default_so_the_clock_never_stops(cfg, field):
    got = clock.schedule(cfg)
    assert got[field] == clock.DEFAULT[field]
    assert all(got[k] == clock.DEFAULT[k] for k in clock.DEFAULT)


def test_stats_always_run_after_the_last_reel():
    assert clock.schedule({"reels": ["09:00", "13:00", "23:00"], "stats": "22:00"})["stats"] == "23:30"
    assert clock.schedule({"reels": ["09:00", "22:00"], "stats": "21:00"})["stats"] == "23:30"
    assert clock.schedule({"reels": ["09:00", "20:00"], "stats": "21:00"})["stats"] == "21:00"


def test_missing_schedule_block_means_the_defaults():
    assert clock.read_schedule("paused: false\n") == clock.DEFAULT
    assert clock.schedule(None) == clock.DEFAULT


def test_a_cron_backup_before_the_configured_time_skips(monkeypatch, tmp_path):
    late = clock.schedule({"daily": "06:30"})
    assert clock.daily_not_yet(utc(0, 15), late) is True       # the 05:45 cron, post set for 06:30
    assert clock.daily_not_yet(utc(1, 0), late) is False       # 06:30 India time
    assert clock.daily_not_yet(utc(0, 15), clock.DEFAULT) is False

    import fma.__main__ as entry
    out = tmp_path / "out.txt"
    monkeypatch.setenv("GITHUB_EVENT_NAME", "schedule")
    monkeypatch.setenv("GITHUB_OUTPUT", str(out))
    monkeypatch.setattr(clock, "daily_not_yet", lambda now, sched: True)
    monkeypatch.setattr(entry, "run_day", lambda *a, **k: pytest.fail("a backup run before the time must not write"))
    assert entry.main(["daily"]) == 0
    assert "published=false" in out.read_text(encoding="utf-8")
    # a dispatched run (the clock, Rerun in the control app) is never held back
    monkeypatch.setenv("GITHUB_EVENT_NAME", "workflow_dispatch")
    called = []
    monkeypatch.setattr(entry, "run_day", lambda *a, **k: called.append(1) or pytest.skip("reached run_day"))
    with pytest.raises(pytest.skip.Exception):
        entry.main(["daily"])
    assert called


# ---------------------------------------------------------------- Reel slots

CARD = {"hook": "Acme cut prices[S1].", "points": ["A[S1].", "B[S1]."], "take": "Check[S1].", "take_kind": "do"}
POST = {"date": "2026-11-05", "slug": "2026-11-05-acme", "headline": "Acme ships Nova-2",
        "what_happened": ["Acme released Nova-2 today[S1].", "It costs $5 a month[S1].", "Rivals cut prices[S1]."],
        "sections": [{"title": t, "category": "products", "paragraphs": ["x[S1]"], "card": {**CARD, "hook": f"{t} cut prices[S1]."}}
                     for t in ("Acme", "Beta", "Gamma")],
        "sources": [{"id": "S1", "url": "https://a.example/1", "title": "A", "publisher": "A"}]}
SITE = {"base_url": "https://fiveminuteai.net/", "name": "Five Minute AI", "auto_post_reels": True}


def reels(q):
    return {i["id"]: i["scheduled_at"] for i in q["items"] if i["platform"] == "instagram_reel"}


def test_reels_use_the_configured_slots():
    q = sq.build_queue(POST, {**SITE, "schedule": {"daily": "05:45", "reels": ["10:00", "18:30"]}})
    assert reels(q) == {"2026-11-05-reel-1": "2026-11-05T04:30:00+00:00", "2026-11-05-reel-2": "2026-11-05T13:00:00+00:00"}
    assert sq.reel_slots(SITE) == sq.REEL_SLOTS                        # no schedule block: the original times


def test_a_new_schedule_never_moves_or_drops_reels_already_queued():
    before = sq.build_queue(POST, SITE)                                 # three Reels at 09:00, 13:00, 19:00
    assert len(reels(before)) == 3
    before["items"][-1]["status"] = "posted"
    after = sq.build_queue(POST, {**SITE, "schedule": {"reels": ["11:00"]}}, existing=before)
    assert reels(after) == reels(before)                                # same three, same times
    assert next(i for i in after["items"] if i["id"] == before["items"][-1]["id"])["status"] == "posted"


# ---------------------------------------------------------------- lineup caps

def test_lineup_caps_come_from_config_within_bounds():
    assert lineup_caps({}) == {"max_per_category": 2, "max_per_source": 1}
    assert lineup_caps({"max_per_category": 3, "max_per_source": 2}) == {"max_per_category": 3, "max_per_source": 2}
    for bad in (0, 9, "2", 2.5, True, None):
        assert lineup_caps({"max_per_category": bad, "max_per_source": bad}) == {"max_per_category": 2, "max_per_source": 1}
    real = __import__("yaml").safe_load((ROOT / "config/site.yaml").read_text(encoding="utf-8"))["pipeline"]
    assert lineup_caps(real) == {"max_per_category": real["max_per_category"], "max_per_source": real["max_per_source"]}


def test_learning_rows_are_labelled_with_the_time_they_were_scheduled():
    from fma.learn import FEATURES, _ist_hhmm
    assert _ist_hhmm("2026-11-05T04:30:00+00:00") == "10:00"
    assert _ist_hhmm(None) is None
    assert FEATURES["slot"]({"slot": 1, "time": "10:00"}) == "10:00"
    assert FEATURES["slot"]({"slot": 2}) == "13:00"                     # rows from before the times moved
    _ = json                                                            # (json kept for fixtures above)
