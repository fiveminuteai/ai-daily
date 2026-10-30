from fma.site import render_text, split_headline

NUM = {"S1": 1, "S2": 2}


def test_citations_shown_once_per_run_of_same_source():
    html = str(render_text("One fact[S1]. Two fact[S1]. Other[S2].", NUM))
    assert html.count('href="#src-S1"') == 1 and html.count('href="#src-S2"') == 1
    assert "[S" not in html


def test_citation_links_can_point_to_another_page():
    assert 'href="posts/x/#src-S1"' in str(render_text("Fact[S1].", NUM, "posts/x/"))


def test_text_is_escaped():
    assert "&lt;script&gt;" in str(render_text("<script>x</script>[S1].", NUM))


def test_split_headline():
    assert split_headline("Acme releases Nova-2 as the EU fines DataCorp") == ("Acme releases Nova-2", "as the EU fines DataCorp")
    assert split_headline("Anthropic files to go public, OpenAI ships GPT-6.1") == ("Anthropic files to go public,", "OpenAI ships GPT-6.1")
    assert split_headline("Short one") == ("Short one", "")
    assert split_headline("Anthropic files S-1 revealing $3.1 billion monthly compute spend") == (
        "Anthropic files S-1 revealing $3.1 billion monthly compute spend", "")


def test_feed_time_source_day_and_tag_slugs():
    from fma.site import _utc, local_day
    from fma.write import normalise_draft
    assert _utc("2026-10-30T04:30:21+00:00").hour == 4
    assert (_utc("2026-10-30").hour, _utc("2026-10-30").minute) == (0, 15)
    assert local_day("2026-10-29T21:40:00+00:00", "Asia/Kolkata") == "2026-10-30"     # 03:10 next day in India
    assert local_day("2026-10-29T10:00:00+00:00", "Asia/Kolkata") == "2026-10-29"
    tags = normalise_draft({"tags": ["AI Models", "ai-models", "++", "Open Weight", "Google"]})["tags"]
    assert tags == ["ai-models", "open-weight", "google"]


def test_feed_has_a_browser_stylesheet_that_renders(tmp_path):
    from lxml import etree
    from fma import site as site_mod
    out = site_mod.build(out_dir=tmp_path / "public")
    feed = (out / "feed.xml").read_text(encoding="utf-8")
    assert '<?xml-stylesheet type="text/xsl" href="/assets/feed.xsl"?>' in feed.splitlines()[1]
    page = str(etree.XSLT(etree.parse(str(out / "assets/feed.xsl")))(etree.parse(str(out / "feed.xml"))))
    assert "This is the RSS feed" in page and "feed.xml" in page
