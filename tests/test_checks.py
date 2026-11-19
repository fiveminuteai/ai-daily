"""Checks (fma/checks.py, 20 Nov 2026): a one-off piece gets its page, its slides, and its own carousel in the queue."""
import json
from datetime import datetime, timezone

import pytest

from fma import checks
from fma import social_queue as sq

SITE = {"base_url": "https://fiveminuteai.net/", "name": "Five Minute AI", "instagram_id": "1784"}
POST = {"date": "2026-10-31", "slug": "2026-10-31-acme", "headline": "Acme ships Nova-2",
        "what_happened": ["Acme released Nova-2 today[S1].", "It costs $5 a month[S2].", "Rivals cut prices[S3]."]}
CHECK = {"slug": "plugins-we-checked", "date": "2026-10-31", "checked": "30 October 2026", "post_at": "14:30",
         "headline": "We checked the plugins", "dek": "Five things matter more.",
         "blocks": [{"p": "**GSD is archived** on GitHub [S1]."}, {"ul": ["Licence?"]}],
         "sources": [{"id": "S1", "label": "GitHub API", "url": "https://github.com/x/y"}],
         "slides": [{"kind": "cover", "text": "We checked the plugins."},
                    {"kind": "line", "label": "GSD", "text": "GSD is archived.", "source": "GitHub"},
                    {"kind": "checks", "text": "Before you install:", "items": ["Archived?", "Licence?"]}],
         "caption": "We read their GitHub pages. Which one do you use?"}


@pytest.fixture
def root(tmp_path, monkeypatch):
    (tmp_path / "content/posts").mkdir(parents=True)
    (tmp_path / "content/checks").mkdir(parents=True)
    (tmp_path / "content/posts/2026-10-31.json").write_text(json.dumps(POST), encoding="utf-8")
    (tmp_path / "content/checks/plugins.json").write_text(json.dumps(CHECK), encoding="utf-8")
    monkeypatch.setattr(sq.config, "CONTENT_DIR", tmp_path / "content")
    return tmp_path


def test_a_half_written_check_or_a_citation_with_no_source_is_refused(tmp_path):
    (tmp_path / "checks").mkdir()
    (tmp_path / "checks/a.json").write_text(json.dumps({**CHECK, "caption": ""}), encoding="utf-8")
    with pytest.raises(ValueError, match="missing caption"):
        checks.load_checks(tmp_path)
    (tmp_path / "checks/a.json").write_text(json.dumps({**CHECK, "blocks": [{"p": "A claim [S2]."}]}), encoding="utf-8")
    with pytest.raises(ValueError, match="cites S2"):
        checks.load_checks(tmp_path)


def test_inline_marks_are_escaped_first():
    out = str(checks.inline("**Bold** <b>x</b> `npx a` here [S1]."))
    assert "<strong>Bold</strong>" in out and "&lt;b&gt;" in out and "<code>npx a</code>" in out
    assert 'href="#S1"' in out and checks.plain("**A** `b` c [S1].") == "A b c."


def test_the_slides_are_drawn_one_per_line(root, tmp_path):
    paths = checks.slides(tmp_path / "out", CHECK, SITE)
    assert [p.name for p in paths] == ["01.jpg", "02.jpg", "03.jpg"]
    from PIL import Image
    assert all(Image.open(p).size == (1080, 1350) for p in paths)


def test_the_queue_carries_the_check_as_its_own_approved_carousel(root):
    q = json.loads(sq.write_queue(root, "2026-10-31", SITE).read_text(encoding="utf-8"))
    it = next(i for i in q["items"] if i["id"] == "2026-10-31-check-plugins-we-checked")
    assert it["status"] == "approved" and it["slides"] and it["platform"] == "instagram"
    assert it["media"] == [f"https://fiveminuteai.net/checks/plugins-we-checked/0{k}.jpg" for k in (1, 2, 3)]
    assert it["scheduled_at"] == "2026-10-31T09:00:00+00:00"                         # 14:30 India time
    other = sq.build_queue({**POST, "date": "2026-11-01"}, SITE)
    assert not any("-check-" in i["id"] for i in other["items"])                      # only on its own date


def test_due_posts_the_checks_own_slides_once_its_time_comes(root):
    from test_social_queue import FakeGraph
    sq.write_queue(root, "2026-10-31", SITE)
    g = FakeGraph()
    before = datetime(2026, 10, 31, 8, 0, tzinfo=timezone.utc)
    assert not any("check" in ln for ln in sq.due(root, SITE, g, "T", now=before))
    out = sq.due(root, SITE, g, "T", now=datetime(2026, 10, 31, 9, 5, tzinfo=timezone.utc))
    assert any("check-plugins-we-checked posted" in ln and "3 slides" in ln for ln in out)
    imgs = [d.get("image_url") for m, _u, d in g.calls if m == "POST" and d and d.get("is_carousel_item")]
    assert imgs == [f"https://fiveminuteai.net/checks/plugins-we-checked/0{k}.jpg" for k in (1, 2, 3)]
    again = sq.due(root, SITE, FakeGraph(), "T", now=datetime(2026, 10, 31, 10, 0, tzinfo=timezone.utc))
    assert not any("check" in ln for ln in again)                                     # posted once


def test_the_site_gives_the_check_a_page_with_its_sources(root, monkeypatch):
    import shutil

    from fma import config, site
    for f in (root / "content/posts").glob("*.json"):
        f.unlink()
    shutil.copy(config.ROOT / "content/posts/2026-11-19.json", root / "content/posts/")   # a real, complete post
    out = site.build(root / "content", root / "public", base_url="https://fiveminuteai.net/")
    page = (out / "checks/plugins-we-checked/index.html").read_text(encoding="utf-8")
    assert "We checked the plugins" in page and 'id="S1"' in page and "<strong>GSD is archived</strong>" in page
    assert (out / "checks/plugins-we-checked/03.jpg").exists()
    assert "checks/plugins-we-checked/" in (out / "sitemap.xml").read_text(encoding="utf-8")
