"""The daily live health check (fma/health.py): each check, fed the shapes real days produce."""
from datetime import datetime, timezone

from fma.health import Report, check_media, check_post, check_queue

NOW = datetime(2026, 11, 11, 12, 0, tzinfo=timezone.utc)      # 17:30 IST


def post(n=5, words=950, duos=(0, 1, 2), **kw):
    secs = [{"title": f"S{k}", "card": {"hook": "h", **({"duo": {"lines": []}} if k in duos else {})}}
            for k in range(n)]
    return {"slug": "s", "sections": secs, "word_count": words, **kw}


def levels(r, area=None):
    return [(i["level"], i["msg"]) for i in r.items if area is None or i["area"] == area]


def test_short_day_and_missing_post_are_reported():
    r = Report("d"); check_post(r, post(3, 564, edition="short"), {"attempts": [{"fails": ["word count 860"]}]})
    assert levels(r)[0][0] == "WARN" and "3 stories" in levels(r)[0][1] and "860" in levels(r)[0][1]
    r = Report("d"); check_post(r, None, {"reason": "gate failed"})
    assert levels(r)[0] == ("FAIL", "no post for d (gate failed)")


def test_a_plain_reel_for_a_card_with_a_duo_fails():
    """11 Nov 2026: the founders card had no duo at render time; had it had one, a plain Reel is a FAIL."""
    media = {"slug": "s", "voice": True, "slides": ["1.png"], "reels": [
        {"file": "reels/01.mp4", "story": 0, "duo": "doubt", "seconds": 34.0, "audio": True, "cover": True},
        {"file": "reels/02.mp4", "story": 1, "duo": None, "plain_because": "duo render failed: cap", "seconds": 30.0,
         "audio": True, "cover": True},
        {"file": "reels/03.mp4", "story": 3, "duo": None, "plain_because": "card has no duo", "seconds": 50.2,
         "audio": False, "cover": False}]}
    r = Report("d"); check_media(r, media, post())
    got = levels(r)
    assert ("OK", "reels/01.mp4: duo with doubt") in got
    assert any(lv == "FAIL" and "02.mp4" in m and "cap" in m for lv, m in got)
    assert any(lv == "WARN" and "03.mp4: plain Reel" in m for lv, m in got)
    assert any(lv == "FAIL" and "50.2 s" in m for lv, m in got) and any("no audio" in m for _, m in got)


def test_unvoiced_render_and_missing_manifest_fail():
    r = Report("d"); check_media(r, None, post())
    assert r.failed
    r = Report("d"); check_media(r, {"voice": False, "slides": [], "reels": []}, post())
    assert sum(lv == "FAIL" for lv, _ in levels(r)) == 2


def test_overdue_and_unlinked_items_fail_but_a_late_cron_is_tolerated():
    q = {"items": [
        {"id": "r1", "kind": "reel", "posting": "api", "status": "posted", "posted_url": "u", "youtube_url": "y",
         "scheduled_at": "2026-11-11T03:30:00+00:00"},
        {"id": "r2", "kind": "reel", "posting": "api", "status": "approved", "scheduled_at": "2026-11-11T07:30:00+00:00"},
        {"id": "r3", "kind": "reel", "posting": "api", "status": "approved", "scheduled_at": "2026-11-11T11:40:00+00:00"},
        {"id": "c", "kind": "carousel", "posting": "api", "status": "posted", "scheduled_at": "2026-11-11T05:30:00+00:00"},
        {"id": "li", "kind": "text", "posting": "manual", "status": "pending"}]}
    r = Report("d"); check_queue(r, q, NOW, {"reels": [{}, {}, {}]})
    fails = [m for lv, m in levels(r) if lv == "FAIL"]
    assert any(m.startswith("r2:") and "13:00 IST" in m for m in fails)        # 4.5 h overdue
    assert not any(m.startswith("r3:") for m in fails)                         # 20 min: GitHub cron is late
    assert any(m.startswith("c:") and "no link" in m for m in fails)
    assert not any(m.startswith("li:") for _, m in levels(r))                  # LinkedIn is by hand


def test_queue_and_render_must_agree_on_the_number_of_reels():
    q = {"items": [{"id": "r1", "kind": "reel", "status": "pending"}]}
    r = Report("d"); check_queue(r, q, NOW, {"reels": [{}, {}]})
    assert any("1 Reels queued but 2 rendered" in m for _, m in levels(r))


def test_hand_posted_platforms_get_an_evening_reminder():
    from datetime import datetime, timezone
    q = {"items": [{"id": "2026-11-11-linkedin", "kind": "text", "posting": "manual", "status": "pending"},
                   {"id": "2026-11-11-x", "kind": "post", "posting": "paid", "status": "posted", "posted_url": "u"}]}
    r = Report("d"); check_queue(r, q, datetime(2026, 11, 11, 15, 0, tzinfo=timezone.utc))    # 20:30 IST
    msgs = [m for lv, m in levels(r) if lv == "WARN"]
    assert any(m.startswith("2026-11-11-linkedin") for m in msgs) and not any("-x:" in m for m in msgs)
    r = Report("d"); check_queue(r, q, datetime(2026, 11, 11, 9, 0, tzinfo=timezone.utc))     # 14:30 IST: not yet
    assert not any("by hand" in m for _, m in levels(r))


def test_dead_feeds_are_reported_before_they_thin_the_post():
    src = lambda ok, n: {"status": "ok" if ok else "error", "items": n}     # noqa: E731
    run = {"stages": {"collect": {"sources": {"a": src(True, 5), "b": src(True, 0), "c": src(False, 0),
                                              "d": src(False, 0), "off": {"status": "disabled", "items": 0}}}}}
    r = Report("d"); check_post(r, post(), run)
    assert any(lv == "FAIL" and "only 1 of 4" in m for lv, m in levels(r, "feeds"))
    run["stages"]["collect"]["sources"].update(b=src(True, 3), c=src(True, 2), d=src(True, 9))
    r = Report("d"); check_post(r, post(), run)
    assert levels(r, "feeds") == [("OK", "all 4 sources gave stories")]
