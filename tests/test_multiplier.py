"""Every Reel as a multiple of what is normal for its kind (15 Nov 2026, after Caleb Ralston's team practice)."""
from datetime import datetime, timezone

from fma import multiplier

NOW = datetime(2026, 11, 15, tzinfo=timezone.utc)


def row(i, reach, watch, pace="slow", age=300, skip=60, **kw):
    return {"id": f"r{i}", "date": "2026-11-01", "hook": f"hook {i}", "pace": pace, "reach": reach, "watch_s": watch,
            "shares": 1, "saved": 1, "comments": 0, "age_h": age, "skip": skip, "category": "products", **kw}


def test_a_reel_is_compared_with_the_median_of_its_own_kind():
    rows = [row(1, 100, 5.0), row(2, 200, 10.0), row(3, 300, 15.0), row(4, 10, 2.0, pace="no duo"),
            row(5, 30, 6.0, pace="no duo")]
    rep = multiplier.build(rows, NOW)
    assert rep["medians"]["duo"]["reach"] == 200 and rep["medians"]["plain"]["reach"] == 20
    by = {r["id"]: r for r in rep["reels"]}
    assert by["r3"]["x"]["reach"] == 1.5 and by["r3"]["x"]["watch_s"] == 1.5
    assert by["r5"]["x"]["reach"] == 1.5                       # a plain Reel is judged against plain Reels
    assert rep["reels"][0]["overall"] >= rep["reels"][-1]["overall"]


def test_young_reels_are_marked_early_and_the_skip_rate_reads_either_way():
    rep = multiplier.build([row(1, 100, 5.0, age=60, skip=0.6), row(2, 100, 5.0, age=400, skip=40)], NOW)
    by = {r["id"]: r for r in rep["reels"]}
    assert by["r1"]["judged"] == "early" and by["r2"]["judged"] == "final"
    assert by["r2"]["x"]["held"] > by["r1"]["x"]["held"]       # 40% left beats 60% left, however it is written
    assert rep["top_tenth"] is None and rep["judged"] == 1     # far too few to study


def test_the_top_tenth_lists_only_what_all_the_best_share_and_the_rest_mostly_lack():
    rows = [row(i, 100 + i, 5.0, hook_type="number", pain="money") for i in range(18)]
    rows += [row(90, 900, 20.0, hook_type="stakes", pain="money"), row(91, 800, 19.0, hook_type="stakes", pain="money")]
    rep = multiplier.build(rows, NOW)
    t = rep["top_tenth"]
    assert t["reels"] == ["r90", "r91"] and t["all_share"].get("hook_type") == "stakes"
    assert "pain" not in t["all_share"] and "category" not in t["all_share"]      # everyone has those: not a finding
    assert "top tenth" in multiplier.table(rep)


def test_old_rows_fall_out_of_the_window():
    rep = multiplier.build([{**row(1, 100, 5.0), "date": "2026-06-01"}, row(2, 50, 5.0)], NOW)
    assert [r["id"] for r in rep["reels"]] == ["r2"]
