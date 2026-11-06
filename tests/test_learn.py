import json
from datetime import datetime, timedelta, timezone

from fma import learn

NOW = datetime(2026, 11, 30, 18, 0, tzinfo=timezone.utc)


def row(n, cat, watch, reach):
    return {"id": f"r{n}", "date": "2026-11-10", "slot": n % 3 + 1, "category": cat, "hook_number": n % 2 == 0,
            "hook_words": 9 + n % 4, "desk": 7, "hook": f"hook {n}", "reach": reach, "watch_s": watch, "shares": 0,
            "saved": 0, "comments": 0, "age_h": 72}


def rows_with(gap, n_each):
    rows = [row(k, "policy", 3.0 + gap + (k % 3) * 0.1, 60) for k in range(n_each)]
    rows += [row(100 + k, "tools", 3.0 + (k % 3) * 0.1, 40) for k in range(n_each)]
    learn._score(rows)
    return rows


def test_few_reels_change_nothing_however_big_the_gap():
    table = learn.effects(rows_with(gap=3.0, n_each=4))         # 4 Reels a side: below MIN_N
    assert not any(e["confident"] for e in table)
    assert learn.category_bonus(table, {}) == {}


def test_a_clear_gap_with_enough_reels_moves_the_lean_one_small_step_at_a_time():
    table = learn.effects(rows_with(gap=1.0, n_each=12))
    pol = next(e for e in table if e["feature"] == "category" and e["value"] == "policy")
    assert pol["confident"] and pol["effect"] > 0
    first = learn.category_bonus(table, {})
    assert first["policy"] == learn.STEP and first["tools"] == -learn.STEP           # one step, not the full target
    bonus = first
    for _ in range(20):
        bonus = learn.category_bonus(table, bonus)
    assert abs(bonus["policy"]) <= learn.MAX_BONUS                                    # bounded
    assert learn.category_bonus([], {"policy": 0.5}) == {"policy": 0.25}              # without evidence it decays


def test_shrinkage_pulls_small_groups_towards_zero():
    rows = rows_with(gap=1.0, n_each=12) + [row(999, "research", 9.0, 500)]
    learn._score(rows)
    table = learn.effects(rows)
    one = next(e for e in table if e["value"] == "research")
    assert one["n"] == 1 and not one["confident"] and abs(one["effect"]) < abs(one["mean"])


def test_lessons_citing_numbers_we_do_not_have_are_dropped():
    rows = rows_with(gap=1.0, n_each=12)
    table = learn.effects(rows)
    pol = next(e for e in table if e["feature"] == "category" and e["value"] == "policy")
    reply = {"lessons": [
        {"lesson": "Lead with the legal fight.", "evidence": [f"n {pol['n']}, effect {pol['effect']}"]},
        {"lesson": "Reels with faces get 340% more reach.", "evidence": ["340%"]},
        {"lesson": "No evidence given."}]}
    kept = learn.check_lessons(reply, rows, table)
    assert [k["lesson"] for k in kept] == ["Lead with the legal fight."]


def test_update_reads_our_files_and_counts_only_mature_reels(tmp_path):
    (tmp_path / "data/stats").mkdir(parents=True)
    (tmp_path / "data/social").mkdir(parents=True)
    (tmp_path / "content/posts").mkdir(parents=True)
    post = {"sections": [{"category": "policy", "card": {"hook": "A judge lets villagers sue Acme[S1].", "reel": 8}}]}
    (tmp_path / "content/posts/2026-11-10.json").write_text(json.dumps(post), encoding="utf-8")
    items = [{"id": f"2026-11-10-reel-{k}", "platform": "instagram_reel", "status": "posted", "story": 0,
              "media_id": f"M{k}", "hook": "A judge lets villagers sue Acme."} for k in (1, 2)]
    (tmp_path / "data/social/2026-11-10.json").write_text(json.dumps({"items": items}), encoding="utf-8")
    posts = [{"id": "M1", "timestamp": "2026-11-10T03:30:00+0000", "reach": 80, "avg_watch_s": 4.0},
             {"id": "M2", "timestamp": "2026-11-12T03:30:00+0000", "reach": 10, "avg_watch_s": 1.0}]   # too young
    (tmp_path / "data/stats/2026-11-12.json").write_text(json.dumps(
        {"collected_at": "2026-11-12T18:00:00+00:00", "instagram": {"posts": posts}}), encoding="utf-8")
    out = learn.update(tmp_path, now=NOW)
    assert out["reels_counted"] == 1 and out["lessons"] == [] and "category_bonus" not in out
    saved = json.loads((tmp_path / "data/learning/reels.json").read_text(encoding="utf-8"))
    assert saved["reels"][0]["category"] == "policy" and saved["reels"][0]["desk"] == 8


def test_learned_lessons_reach_the_producer_and_the_lean_is_frozen_into_the_card(tmp_path, monkeypatch):
    from conftest import FakeChain

    from fma import reel_desk
    monkeypatch.setattr("fma.learn.learned_settings", lambda root=None: {
        "category_bonus": {"policy": 0.5}, "lessons": [{"lesson": "Lead with the fight.", "evidence": ["n 12"]}]})
    seen = []

    class Chain(FakeChain):
        def ask_json(self, system, user, temperature=0.3, careful=False, **kw):
            seen.append(user)
            return {"score": {"stakes": 3, "names": 2, "surprise": 1}, "hook": "Acme is sued[S1].",
                    "points": ["a[S1].", "b[S1].", "c[S1]."], "take": "t[S1].", "angle": "x"}
    draft = {"sections": [{"title": "Suit", "category": "policy", "paragraphs": ["Acme is sued[S1]."]}]}
    out = reel_desk.produce(Chain([]), draft, [{"id": "S1", "publisher": "A", "title": "T"}])
    assert "LESSONS FROM OUR OWN REEL RESULTS" in seen[0] and "Lead with the fight. (n 12)" in seen[0]
    assert out["sections"][0]["card"]["bonus"] == 0.5
