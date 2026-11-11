"""The eval suite itself must pass before anything ships (fma/evals.py), and a failing suite must hold the loop."""
import json
from datetime import datetime, timedelta, timezone

from fma import evals, learn


def test_every_eval_suite_meets_its_bar():
    out = evals.run()
    failing = [(x["suite"], x["rate"], x["bar"], x["misses"][:2]) for x in out["suites"] if not x["ok"]]
    assert not failing, failing
    assert {x["suite"] for x in out["suites"]} == set(evals.BARS) and all(x["n"] > 0 for x in out["suites"])


def test_a_failing_eval_suite_holds_every_self_change(tmp_path):
    now = datetime(2026, 11, 30, tzinfo=timezone.utc)
    (tmp_path / "data").mkdir()
    before = {"category_bonus": {"policy": 0.5}, "bonus_changed": (now - timedelta(days=30)).isoformat(),
              "lessons": [{"lesson": "x", "evidence": ["slot = 13:00: n 7, effect 0.03"], "added": now.isoformat()}]}
    (tmp_path / "data/learned.json").write_text(json.dumps(before), encoding="utf-8")
    out = learn.update(tmp_path, now=now, allow_changes=False)
    assert out["category_bonus"] == {"policy": 0.5} and len(out["lessons"]) == 1 and "held" in out
    assert not (tmp_path / learn.CHANGES).exists()
