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


def test_cli_dry_run_changes_nothing(root, monkeypatch, capsys):
    monkeypatch.setattr(sq.config, "ROOT", root)
    monkeypatch.setattr(sq.config, "site_config", lambda: SITE)
    sq.write_queue(root, "2026-10-31", SITE)
    assert sq.main(["act", "2026-10-31-instagram", "--action", "approve", "--dry-run"]) == 0
    assert "DRY RUN, nothing posted" in capsys.readouterr().out
    assert json.loads(sq.queue_path(root, "2026-10-31").read_text(encoding="utf-8"))["items"][0]["status"] == "pending"


# ---------------------------------------------------------------- live actions (fake Instagram)

SHARE = "https://fiveminuteai.net/share/2026-10-31/"
GRAPH = "https://graph.facebook.com/v26.0"
LIVE_SITE = {**SITE, "instagram_id": "1784"}


class FakeGraph:
    """The share page plus Meta's Graph API, recording every request."""

    def __init__(self, slides=3, publish_status=200):
        self.calls, self.slides, self.publish_status, self.n = [], slides, publish_status, 0

    def get(self, url, params=None, **kw):
        from conftest import FakeResponse
        self.calls.append(("GET", url, params))
        if url == SHARE:
            imgs = "".join(f'<img src="/share/2026-10-31/carousel/{i:02d}.jpg">' for i in range(1, self.slides + 1))
            return FakeResponse(200, imgs + '<img src="/share/2026-10-30/carousel/09.jpg">')
        if url == f"{GRAPH}/C1":
            return FakeResponse(200, json_data={"status_code": "FINISHED"})
        if url == f"{GRAPH}/M1":
            return FakeResponse(200, json_data={"permalink": "https://www.instagram.com/p/abc/"})
        return FakeResponse(404, b"")

    def post(self, url, data=None, **kw):
        from conftest import FakeResponse
        self.calls.append(("POST", url, data))
        if url.endswith("/media_publish"):
            if self.publish_status >= 400:
                return FakeResponse(self.publish_status, json_data={"error": {"message": "bad token abc", "code": 190}})
            return FakeResponse(200, json_data={"id": "M1"})
        self.n += 1
        return FakeResponse(200, json_data={"id": "C1" if data.get("media_type") == "CAROUSEL" else f"S{self.n}"})


def item(root, platform):
    q = json.loads(sq.queue_path(root, "2026-10-31").read_text(encoding="utf-8"))
    return next(i for i in q["items"] if i["platform"] == platform)


def test_approve_posts_the_carousel_and_records_the_link(root):
    sq.write_queue(root, "2026-10-31", LIVE_SITE)
    g = FakeGraph(slides=3)
    out = sq.act(root, "2026-10-31-instagram", "approve", "My caption #ai", LIVE_SITE, g, "SECRET-T0K")
    assert "posted to Instagram" in out and "3 slides" in out
    posts = [c for c in g.calls if c[0] == "POST"]
    assert [d.get("image_url") for _, _, d in posts[:3]] == [f"{SHARE}carousel/0{i}.jpg" for i in (1, 2, 3)]
    assert all(d["is_carousel_item"] == "true" for _, _, d in posts[:3])
    assert posts[3][2]["children"] == "S1,S2,S3" and posts[3][2]["caption"] == "My caption #ai"
    assert posts[4][1] == f"{GRAPH}/1784/media_publish" and posts[4][2]["creation_id"] == "C1"
    assert all("SECRET-T0K" not in url for _, url, _ in g.calls)                  # the token never goes in a URL here
    it = item(root, "instagram")
    assert it["status"] == "posted" and it["posted_url"] == "https://www.instagram.com/p/abc/" and it["media_id"] == "M1"
    assert it["edited_text"] == "My caption #ai"
    with pytest.raises(ValueError, match="already posted"):                 # no double post
        sq.act(root, "2026-10-31-instagram", "approve", None, LIVE_SITE, FakeGraph(), "SECRET-T0K")


def test_failed_post_is_recorded_without_the_token_or_metas_text(root):
    from fma.instagram import PublishError
    sq.write_queue(root, "2026-10-31", LIVE_SITE)
    with pytest.raises(PublishError):
        sq.act(root, "2026-10-31-instagram", "approve", None, LIVE_SITE, FakeGraph(publish_status=400), "SECRET-T0K")
    it = item(root, "instagram")
    assert it["status"] == "failed" and it["error"] == "publish: HTTP 400 (Meta error 190)"
    assert "SECRET-T0K" not in json.dumps(it) and "bad token" not in json.dumps(it)
    with pytest.raises(PublishError, match="no carousel slides"):
        sq.act(root, "2026-10-31-instagram", "approve", None, LIVE_SITE, FakeGraph(slides=0), "SECRET-T0K")


def test_skip_linkedin_and_x_never_touch_instagram(root):
    sq.write_queue(root, "2026-10-31", LIVE_SITE)
    g = FakeGraph()
    assert "skipped" in sq.act(root, "2026-10-31-instagram", "skip", None, LIVE_SITE, g, "SECRET-T0K")
    assert "by hand" in sq.act(root, "2026-10-31-linkedin", "approve", "Mine", LIVE_SITE, g, "SECRET-T0K")
    with pytest.raises(ValueError, match="not switched on"):
        sq.act(root, "2026-10-31-x", "approve", None, LIVE_SITE, g, "SECRET-T0K")
    assert g.calls == []
    assert item(root, "instagram")["status"] == "skipped" and item(root, "linkedin")["status"] == "approved"
    assert item(root, "x")["status"] == "pending"


def test_caption_and_slide_limits():
    from fma.instagram import PublishError, publish_carousel
    imgs = [f"{SHARE}carousel/0{i}.jpg" for i in (1, 2)]
    for bad_imgs, bad_cap, msg in ((imgs[:1], "ok", "2 to"), (imgs, "x" * 2201, "over"), (imgs, "#a " * 31, "hashtags"),
                                   ([u.replace(".jpg", ".png") for u in imgs], "ok", "JPEG")):
        with pytest.raises(PublishError, match=msg):
            publish_carousel(FakeGraph(), "1784", "SECRET-T0K", bad_imgs, bad_cap)
