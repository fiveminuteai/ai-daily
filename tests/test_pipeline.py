import json
import re
from xml.etree import ElementTree

import pytest
import yaml
from conftest import NOW, FakeChain, good_draft, replies

from fma import site as site_mod
from fma.pipeline import run_day

OK_CHECK = {"unsupported": []}


@pytest.fixture
def proj(project):
    cfg = yaml.safe_load((project / "config/site.yaml").read_text(encoding="utf-8"))
    cfg["pipeline"].update(words_min=150, words_max=3000)
    (project / "config/site.yaml").write_text(yaml.safe_dump(cfg), encoding="utf-8")
    return project


def run(proj, http, chain, **kw):
    return run_day("2026-10-27", http, chain, now=NOW, root=proj, **kw)


def files(proj):
    """Published state only: diagnostics under logs/ are allowed on a skipped day."""
    return sorted(p.relative_to(proj).as_posix() for d in ("content", "data") for p in (proj / d).rglob("*.json"))


def test_publishes_a_verified_post(proj, fake_web):
    chain = FakeChain(replies(good_draft()))
    r = run(proj, fake_web, chain)
    assert r.status == "published", r.reason
    post = json.loads((proj / "content/posts/2026-10-27.json").read_text(encoding="utf-8"))
    assert post["headline"].startswith("Acme releases Nova-2")
    assert post["byline"] == "Sai Pavan UE"
    assert len(post["what_happened"]) == 3 and len(post["sections"]) == 3
    assert {s["url"] for s in post["sources"]} == {"https://acme.example/nova-2", "https://news.example/eu-datacorp",
                                                   "https://news.example/robots"}
    assert "timeline" in post["visuals"] and "chart" in post["visuals"]
    assert post["verification"]["layer1_done"] and post["verification"]["layer2_done"]
    hist = json.loads((proj / "data/history.json").read_text(encoding="utf-8"))
    assert hist[-1]["date"] == "2026-10-27" and "acme.example/nova-2" in hist[-1]["urls"]
    # the prompt carried the fetched article text, not just headlines; the old story was excluded
    assert chain.prompts[0].startswith("READERS:")                 # the editor pass ran first
    assert "87.5% on the MMLU benchmark" in chain.prompts[1] and "Old story" not in " ".join(chain.prompts)


def test_second_run_same_day_is_skipped(proj, fake_web):
    assert run(proj, fake_web, FakeChain(replies(good_draft()))).status == "published"
    r = run(proj, fake_web, FakeChain(replies(good_draft())))
    assert r.status == "skipped" and "already exists" in r.reason


def test_next_day_does_not_repeat_yesterdays_stories(proj, fake_web):
    assert run(proj, fake_web, FakeChain(replies(good_draft()))).status == "published"
    r = run_day("2026-10-28", fake_web, FakeChain(replies(good_draft())), now=NOW, root=proj)
    assert r.status == "skipped" and "new stories" in r.reason
    assert not (proj / "content/posts/2026-10-28.json").exists()


def test_retry_once_then_publish(proj, fake_web):
    bad = good_draft()
    bad["headline"] = "Globex buys Acme for $40 billion"      # unverifiable headline -> gate fails
    chain = FakeChain(replies(bad) + replies(good_draft()))
    r = run(proj, fake_web, chain)
    assert r.status == "published"
    assert any("rejected" in q and "headline" in q for q in chain.prompts[4:])   # the retry was told why


def test_two_failures_skip_the_day_and_write_nothing(proj, fake_web):
    bad = good_draft()
    bad["sections"] = bad["sections"][:1]
    before = files(proj)
    r = run(proj, fake_web, FakeChain(replies(bad) + replies(bad)))
    assert r.status == "skipped" and "gate failed" in r.reason
    assert files(proj) == before


def test_model_crash_is_a_clean_skip(proj, fake_web):
    before = files(proj)
    r = run(proj, fake_web, FakeChain([RuntimeError("quota")] * 8))
    assert r.status == "skipped" and "quota" in r.reason
    assert files(proj) == before


def test_layer2_flags_drop_sentences(proj, fake_web):
    chain = FakeChain(replies(good_draft()), flags={"C1": "not in source"})
    r = run(proj, fake_web, chain)
    assert r.status == "published"
    assert r.report["layer2_flagged"] == 1
    assert any(e["where"] == "layer2" for e in r.report["entries"])


def test_paused_and_no_provider(proj, fake_web):
    assert "no model provider" in run(proj, fake_web, None).reason
    cfg = yaml.safe_load((proj / "config/site.yaml").read_text(encoding="utf-8"))
    cfg["paused"] = True
    (proj / "config/site.yaml").write_text(yaml.safe_dump(cfg), encoding="utf-8")
    assert run(proj, fake_web, FakeChain([])).reason.startswith("paused")


def test_broken_image_blocks_publish(proj, fake_web, monkeypatch):
    def broken_build(content_dir, out_dir):
        out = site_mod.build(content_dir=content_dir, out_dir=out_dir)
        for png in (out / "og").glob("2026-*.png"):
            png.unlink()
        return out
    r = run(proj, fake_web, FakeChain(replies(good_draft())), build_fn=broken_build)
    assert r.status == "skipped" and "broken images" in r.reason
    assert not (proj / "content/posts/2026-10-27.json").exists()


def test_site_build_renders_everything(proj, fake_web, tmp_path):
    assert run(proj, fake_web, FakeChain(replies(good_draft()))).status == "published"
    out = site_mod.build(content_dir=proj / "content", out_dir=tmp_path / "public")
    post_dirs = list((out / "posts").iterdir())
    assert len(post_dirs) == 1
    page = (post_dirs[0] / "index.html").read_text(encoding="utf-8")
    assert '<sup class="cite"><a href="#src-S1"' in page and 'id="src-S1"' in page
    assert "[S1]" not in page                                   # markers never leak into the page
    assert "<svg class=\"viz\"" in page and "Our read · analysis, not reported fact" in page
    assert "By <strong>Sai Pavan UE</strong>" in page
    assert 'property="og:image" content="https://fiveminuteai.net/og/' in page
    outside = re.findall(r'<script[^>]+src="(https?://[^"]+)"', page)
    assert all(u == "https://gc.zgo.at/count.js" for u in outside)   # the only outside script is the cookie-free visit counter
    assert (out / "og" / f"{post_dirs[0].name}.png").stat().st_size > 5000
    for p in ["index.html", "archive/index.html", "tags/index.html", "tags/models/index.html", "about/index.html",
              "404.html", "sitemap.xml", "robots.txt", f"posts/{post_dirs[0].name}/verification/index.html"]:
        assert (out / p).exists(), p
    assert "The 30-second version" in page and 'data-topic="models"' in page
    assert "\u00c2" not in page
    home = (out / "index.html").read_text(encoding="utf-8")
    assert 'id="field"' in home and "This week in AI" in home and 'data-filter="policy"' in home
    assert '<span class="glow">' in home
    idx = json.loads((out / "search.json").read_text(encoding="utf-8"))
    assert idx[0]["t"].startswith("Acme releases Nova-2") and "87.5%" in idx[0]["x"] and "[S1]" not in idx[0]["x"]
    assert (out / "search/index.html").exists() and (out / "tags/impact/index.html").exists()
    assert (out / "assets/fonts/BricolageGrotesque-Bold.ttf").exists()
    feed = ElementTree.parse(out / "feed.xml").getroot()
    item = feed.find("channel/item")
    assert item.find("title").text.startswith("Acme releases Nova-2")
    assert item.find("link").text.endswith(f"fiveminuteai.net/posts/{post_dirs[0].name}/")
    encoded = item.find("{http://purl.org/rss/1.0/modules/content/}encoded").text
    assert "87.5% on the MMLU benchmark" in encoded and encoded.count("<li>") >= 3


def test_editorial_correction_removes_and_logs(proj, fake_web):
    from fma.pipeline import remove_sentences
    assert run(proj, fake_web, FakeChain(replies(good_draft()))).status == "published"
    removed = remove_sentences(proj, "2026-10-27", ["DataCorp said it would appeal"], "test reason")
    assert len(removed) == 1
    post = json.loads((proj / "content/posts/2026-10-27.json").read_text(encoding="utf-8"))
    assert "appeal" not in json.dumps(post["sections"])
    rep = json.loads((proj / "content/reports/2026-10-27.json").read_text(encoding="utf-8"))
    assert rep["entries"][-1]["where"] == "editorial review" and "test reason" in rep["entries"][-1]["problems"][0]
