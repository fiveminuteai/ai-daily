import json

import pytest

from fma import social_queue as sq
from fma.social import share_texts

SITE = {"base_url": "https://fiveminuteai.net/", "name": "Five Minute AI"}
POST = {"date": "2026-10-31", "slug": "2026-10-31-acme", "headline": "Acme ships Nova‑2",
        "what_happened": ["Acme released Nova‑2 today[S1].", "It costs $5 a month[S2].", "Rivals cut prices[S3]."]}


@pytest.fixture
def root(tmp_path):
    (tmp_path / "content/posts").mkdir(parents=True)
    (tmp_path / "content/posts/2026-10-31.json").write_text(json.dumps(POST), encoding="utf-8")
    return tmp_path


def test_queue_holds_one_pending_item_per_platform_from_share_texts():
    q = sq.build_queue(POST, SITE)
    texts = share_texts(POST, SITE)
    assert [i["platform"] for i in q["items"]] == ["instagram", "x", "linkedin"]
    for i in q["items"]:
        assert i["status"] == "pending" and i["text"] == texts[i["platform"]] and i["id"] == f"2026-10-31-{i['platform']}"
    assert q["items"][0]["media"] == ["https://fiveminuteai.net/share/2026-10-31/instagram.png"]
    assert q["items"][1]["chars"] <= 280
    assert [i["posting"] for i in q["items"]] == ["api", "paid", "manual"]


def test_rebuild_keeps_decisions(root):
    path = sq.write_queue(root, "2026-10-31", SITE)
    q = json.loads(path.read_text(encoding="utf-8"))
    q["items"][2].update(status="skipped", edited_text="mine")
    path.write_text(json.dumps(q), encoding="utf-8")
    again = json.loads(sq.write_queue(root, "2026-10-31", SITE).read_text(encoding="utf-8"))
    assert again["items"][2]["status"] == "skipped" and again["items"][2]["edited_text"] == "mine"
    assert again["items"][0]["status"] == "pending"


def test_plan_action_uses_edited_text_and_refuses_bad_input(root):
    sq.write_queue(root, "2026-10-31", SITE)
    plan = sq.plan_action(root, "2026-10-31-linkedin", "approve", "Edited words")
    assert plan["text"] == "Edited words" and "manual" in plan["would"]
    assert sq.plan_action(root, "2026-10-31-x", "skip")["would"].startswith("mark skipped")
    with pytest.raises(ValueError, match="over 280"):
        sq.plan_action(root, "2026-10-31-x", "approve", "x" * 300)
    for bad in (("2026-10-31-tiktok", "approve"), ("2026-10-31-x", "delete"), ("2026-11-01-x", "approve")):
        with pytest.raises(ValueError):
            sq.plan_action(root, *bad)


def test_cli_dry_run_only(root, monkeypatch, capsys):
    monkeypatch.setattr(sq.config, "ROOT", root)
    monkeypatch.setattr(sq.config, "site_config", lambda: SITE)
    sq.write_queue(root, "2026-10-31", SITE)
    assert sq.main(["act", "2026-10-31-instagram", "--action", "approve", "--dry-run"]) == 0
    assert "DRY RUN, nothing posted" in capsys.readouterr().out
    assert sq.main(["act", "2026-10-31-instagram", "--action", "approve"]) == 1      # live posting refused
    assert "not built yet" in capsys.readouterr().out
