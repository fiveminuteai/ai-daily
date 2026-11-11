"""The run summary the control dashboard reads: every stage's status, time and key numbers."""
import json

import pytest
import yaml
from conftest import NOW, FakeChain, good_draft, replies

from fma import __main__ as cli
from fma.pipeline import Result, run_day


@pytest.fixture
def proj(project):
    cfg = yaml.safe_load((project / "config/site.yaml").read_text(encoding="utf-8"))
    cfg["pipeline"].update(words_min=150, words_max=3000)
    (project / "config/site.yaml").write_text(yaml.safe_dump(cfg), encoding="utf-8")
    return project


def run(proj, http, chain, **kw):
    return run_day("2026-10-27", http, chain, now=NOW, root=proj, **kw)


def test_published_day_commits_a_summary_with_every_stage(proj, fake_web):
    r = run(proj, fake_web, FakeChain(replies(good_draft())))
    assert r.status == "published"
    saved = json.loads((proj / "data/runs/2026-10-27.json").read_text(encoding="utf-8"))
    assert saved == json.loads((proj / "logs/run-2026-10-27.json").read_text(encoding="utf-8")) == r.summary
    assert saved["status"] == "published" and saved["slug"] == r.slug and saved["seconds"] >= 0
    st = saved["stages"]
    assert list(st) == ["collect", "rank", "extract", "publish"]
    assert all(s["status"] == "ok" for s in st.values())
    # per-source fetch numbers add up to the items fetched
    assert sum(s["items"] for s in st["collect"]["sources"].values()) == st["collect"]["items"] > 0
    assert all(s["status"] in {"ok", "error", "disabled"} for s in st["collect"]["sources"].values())
    # the picked stories are explained with their scores; the lineup is the picked part of the top list
    lineup = st["rank"]["lineup"]
    assert len(lineup) == 3 and all(s["picked"] and "score" in s and s["url"] for s in lineup)
    assert {s["title"] for s in st["rank"]["top"] if s["picked"]} == {s["title"] for s in lineup}
    assert st["publish"]["word_count"] == r.post["word_count"]
    # one attempt, both verification layers, and the layer 2 counts match the published post
    (att,) = saved["attempts"]
    assert att["fails"] == [] and att["layer1"]["checked"] > 0
    assert att["layer2"] == {k: r.post["verification"][k] for k in ("checked", "ok", "repaired", "dropped")}
    assert set(att["seconds"]) == {"write", "reel_desk", "layer1", "layer2", "gate"}


def test_skipped_day_summary_stays_in_logs(proj, fake_web):
    bad = good_draft()
    bad["sections"] = bad["sections"][:1]
    r = run(proj, fake_web, FakeChain(replies(bad) + replies(bad)))
    assert r.status == "skipped"
    assert not (proj / "data/runs").exists()
    saved = json.loads((proj / "logs/run-2026-10-27.json").read_text(encoding="utf-8"))
    assert saved["status"] == "skipped" and "gate failed" in saved["reason"]
    assert [a["n"] for a in saved["attempts"]] == [1, 2] and all(a["fails"] for a in saved["attempts"])
    assert "publish" not in saved["stages"]


def test_crashed_attempt_is_recorded(proj, fake_web):
    r = run(proj, fake_web, FakeChain([RuntimeError("quota")] * 8))
    assert r.status == "skipped"
    assert any("quota" in f for a in r.summary["attempts"] for f in a["fails"])


def test_early_skip_has_no_stages(proj, fake_web):
    r = run(proj, fake_web, None)
    assert r.summary["status"] == "skipped" and r.summary["stages"] == {} and "no model provider" in r.summary["reason"]


def test_cli_prints_one_summary_line(monkeypatch, capsys):
    summary = {"date": "2026-10-27", "status": "skipped", "reason": "paused in config/site.yaml", "stages": {}}
    monkeypatch.setattr(cli, "run_day", lambda *a, **k: Result("skipped", summary["reason"], summary=summary))
    monkeypatch.setattr(cli, "providers_from_config", lambda *a, **k: [])
    assert cli.main(["daily", "--date", "2026-10-27"]) == 0
    lines = [ln for ln in capsys.readouterr().out.splitlines() if ln.startswith("FMA_RUN_SUMMARY ")]
    assert len(lines) == 1 and json.loads(lines[0].split(" ", 1)[1]) == summary


def test_short_edition_publishes_the_fullest_attempt_not_the_last(proj, fake_web, monkeypatch):
    """11 Nov 2026: attempt 1 (5 stories) missed the length rule by 20 words; the retry came back with 3 stories
    and was the one published. Both now wait, and the fuller one goes out."""
    import fma.pipeline as pl
    cfg = yaml.safe_load((proj / "config/site.yaml").read_text(encoding="utf-8"))
    cfg["pipeline"].update(words_min=2500, words_max=3000)       # every attempt fails on length alone
    (proj / "config/site.yaml").write_text(yaml.safe_dump(cfg), encoding="utf-8")
    monkeypatch.setattr(pl, "SHORT_EDITION", {"words_min": 100, "words_max": 3000, "require_why": False})
    thin = good_draft()
    thin["sections"] = thin["sections"][:2]
    r = run(proj, fake_web, FakeChain(replies(good_draft()) + replies(thin)))
    assert r.status == "published", r.reason
    assert len(r.post["sections"]) == 3 and r.post["edition"] == "short"
    assert r.summary["published_attempt"] == 1 and all(a["fails"] for a in r.summary["attempts"])


def test_fullest_prefers_more_stories_then_words_then_the_earlier_attempt():
    from fma.pipeline import fullest
    a, b, c = ({"sections": [1, 2, 3], "word_count": 500}, {}, 1), ({"sections": [1, 2], "word_count": 900}, {}, 2), \
        ({"sections": [1, 2, 3], "word_count": 500}, {}, 3)
    assert fullest([b, a])[2] == 1 and fullest([a, c])[2] == 1


def test_no_time_for_another_attempt_publishes_the_short_edition_now(proj, fake_web, monkeypatch):
    """7, 9 and 11 Nov 2026: the job timeout killed attempt 2 and the short edition attempt 1 had passed with it."""
    import fma.pipeline as pl
    cfg = yaml.safe_load((proj / "config/site.yaml").read_text(encoding="utf-8"))
    cfg["pipeline"].update(words_min=2500, words_max=3000)
    (proj / "config/site.yaml").write_text(yaml.safe_dump(cfg), encoding="utf-8")
    monkeypatch.setattr(pl, "SHORT_EDITION", {"words_min": 100, "words_max": 3000, "require_why": False})
    chain = FakeChain(replies(good_draft()) + replies(good_draft()))
    chain.time_left = lambda: 0.0           # the budget is spent after attempt 1
    r = run(proj, fake_web, chain)
    assert r.status == "published" and r.post["edition"] == "short"
    assert [a["n"] for a in r.summary["attempts"]] == [1] and r.summary["published_attempt"] == 1
    assert (proj / "data/collect/2026-10-27/sources.json").exists()     # saved before any writing


def test_chain_refuses_new_calls_past_its_deadline():
    import time as _t
    import pytest as _p
    from fma.llm import Chain, LLMError
    c = Chain([])
    c.deadline = _t.monotonic() - 1
    with _p.raises(LLMError, match="out of time"):
        c.ask_json("s", "u")
