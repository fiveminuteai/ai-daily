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
    flagged = [e for e in r.report["entries"] if any(p.startswith("model check:") for p in e["problems"])]
    assert len(flagged) == 1 and flagged[0]["status"] == "dropped"      # the sentence's own entry, not a duplicate
    rep = r.report
    assert rep["ok"] + rep["repaired"] + rep["dropped"] == rep["checked"] == len(rep["entries"])


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
    assert 'class="note"' in home and "Earlier this week" in home and 'data-filter="policy"' in home
    assert 'id="field"' not in home and "glow" not in home          # the plain, human front page
    idx = json.loads((out / "search.json").read_text(encoding="utf-8"))
    assert idx[0]["t"].startswith("Acme releases Nova-2") and "87.5%" in idx[0]["x"] and "[S1]" not in idx[0]["x"]
    assert (out / "search/index.html").exists() and (out / "tags/impact/index.html").exists()
    assert "No. 1 ·" in home                                      # issue number on the dateline
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
    hit = [e for e in rep["entries"] if any("editorial review" in p and "test reason" in p for p in e["problems"])]
    assert len(hit) == 1 and hit[0]["status"] == "dropped"          # the sentence's own entry, not a duplicate
    assert rep["ok"] + rep["repaired"] + rep["dropped"] == rep["checked"]
    assert post["verification"]["dropped"] == rep["dropped"]


def test_headings_get_capital_first_letter_and_short_forms():
    from fma.write import normalise_draft, tidy_heading
    assert tidy_heading("Aws aims for trillion‑dollar revenue") == "AWS aims for trillion‑dollar revenue"
    assert tidy_heading("need real‑time monitoring for AI agents") == "Need real‑time monitoring for AI agents"
    assert tidy_heading("  Eu fines OpenAI over Gpus  ") == "EU fines OpenAI over GPUs"
    assert tidy_heading("iPhone gets Ai features from us partners") == "iPhone gets AI features from us partners"
    d = normalise_draft({"headline": "aws cuts prices", "sections": [{"title": "Nvidia beats the Sec", "paragraphs": ["x"]}]})
    assert d["headline"] == "AWS cuts prices"
    assert d["sections"][0]["title"] == "Nvidia beats the SEC"


def test_headline_rejected_by_model_check_retries_then_skips(proj, fake_web):
    chain = FakeChain(replies(good_draft()) + replies(good_draft()), flag_text={"[headline]": "joins two events"})
    r = run(proj, fake_web, chain)
    assert r.status == "skipped" and "headline not verified" in r.reason and "model check: joins two events" in r.reason
    assert any("rejected" in p and "joins two events" in p for p in chain.prompts)   # the retry was told why
    assert not (proj / "content/posts/2026-10-27.json").exists()


def test_correction_with_suppress_withholds_the_words(proj, fake_web, tmp_path):
    import hashlib

    from fma.pipeline import remove_sentences
    assert run(proj, fake_web, FakeChain(replies(good_draft()))).status == "published"
    removed = remove_sentences(proj, "2026-10-27", ["DataCorp said it would appeal"], "legal request", suppress=True)
    assert len(removed) == 1
    rep_text = (proj / "content/reports/2026-10-27.json").read_text(encoding="utf-8")
    post_text = (proj / "content/posts/2026-10-27.json").read_text(encoding="utf-8")
    assert "appeal" not in rep_text and "appeal" not in post_text
    rep = json.loads(rep_text)
    last = next(e for e in rep["entries"] if any("editorial review" in p for p in e["problems"]))
    assert last["status"] == "dropped" and last["text"] == "[text withheld: legal request]"
    assert last["sha256"] == hashlib.sha256(b"DataCorp said it would appeal the decision.").hexdigest()
    out = site_mod.build(content_dir=proj / "content", out_dir=tmp_path / "public")
    page = next((out / "posts").glob("*/verification/index.html")).read_text(encoding="utf-8")
    assert "[text withheld: legal request]" in page and last["sha256"] in page and "appeal" not in page


def test_verification_page_lists_unused_separately(proj, fake_web, tmp_path):
    assert run(proj, fake_web, FakeChain(replies(good_draft()))).status == "published"
    rp = proj / "content/reports/2026-10-27.json"
    rep = json.loads(rp.read_text(encoding="utf-8"))
    assert rep["ok"] + rep["repaired"] + rep["dropped"] == rep["checked"]
    rep["entries"].append({"where": "what_happened[3]", "text": "A spare bullet nobody sees.", "sources": ["S1"],
                           "status": "unused", "problems": []})
    rp.write_text(json.dumps(rep), encoding="utf-8")
    out = site_mod.build(content_dir=proj / "content", out_dir=tmp_path / "public")
    page = next((out / "posts").glob("*/verification/index.html")).read_text(encoding="utf-8")
    before, after = page.split("Checked but not used", 1)
    assert "A spare bullet nobody sees." in after and "A spare bullet nobody sees." not in before
    assert "Not used" in after
