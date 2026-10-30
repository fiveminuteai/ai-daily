from PIL import Image

from fma.social import instagram_card, plain, share_texts, x_length

SITE = {"base_url": "https://fiveminuteai.net/", "name": "Five Minute AI"}


def post(headline="Acme ships Nova‑2", bullets=None):
    return {"slug": "2026-10-31-acme", "headline": headline,
            "what_happened": bullets or ["Acme released Nova‑2 today[S1].", "It costs $5 a month[S2][S1].",
                                         "Rivals cut prices[S3]."]}


def test_plain_drops_markers_and_odd_characters():
    assert plain("A 1‑trillion model[S1][S2] , cheap now [S3].") == "A 1-trillion model, cheap now."


def test_share_texts_use_only_the_post_and_link_to_it():
    t = share_texts(post(), SITE)
    url = "https://fiveminuteai.net/posts/2026-10-31-acme/"
    for k in ("x", "linkedin", "instagram"):
        assert "[S" not in t[k] and "‑" not in t[k] and "Acme ships Nova-2" in t[k]
    assert url in t["x"] and url in t["linkedin"]
    assert url not in t["instagram"] and "link in bio" in t["instagram"]      # captions don't make links clickable
    assert "• It costs $5 a month." in t["linkedin"]


def test_x_post_fits_and_drops_bullets_that_do_not():
    t = share_texts(post(bullets=["word " * 40 + "[S1]."] * 3), SITE)
    assert x_length(t["x"]) <= 280
    assert t["x"].startswith("Acme ships Nova-2") and t["x"].endswith("posts/2026-10-31-acme/")
    assert x_length("see https://example.com/" + "a" * 200) == 4 + 23


def test_instagram_card_fits_a_long_post(tmp_path):
    long = post(headline="An unusually long headline that goes on and on about several companies and their plans " * 2,
                bullets=["A long bullet with plenty of words in it that has to wrap over several lines here[S1]. " * 3] * 3)
    out = tmp_path / "card.png"
    instagram_card(out, long, "Five Minute AI", "Saturday 31 October 2026", ["models", "policy"])
    assert Image.open(out).size == (1080, 1350)


def test_build_writes_an_unlisted_share_kit_and_social_links(tmp_path):
    from fma import site as site_mod
    out = site_mod.build(out_dir=tmp_path / "public")
    page = (out / "share/index.html").read_text(encoding="utf-8")
    assert '<meta name="robots" content="noindex">' in page and "kit-instagram" in page and "kit-x" in page
    latest = sorted(p.name for p in (out / "share").iterdir() if p.is_dir())[-1]
    assert Image.open(out / f"share/{latest}/instagram.png").size == (1080, 1350)
    assert "share/" not in (out / "sitemap.xml").read_text(encoding="utf-8")
    assert "Disallow: /share/" in (out / "robots.txt").read_text(encoding="utf-8")
    home = (out / "index.html").read_text(encoding="utf-8")
    assert 'href="https://x.com/fiveminute_ai"' in home and "noindex" not in home
    head = home.split("</header>")[0]
    assert head.count('rel="me noopener"') == 3 and 'aria-label="Five Minute AI on Instagram"' in head   # top right
    assert home.split("<footer")[1].count('rel="me noopener"') == 3                                      # and bottom
    assert "@fiveminute_ai" in (out / "about/index.html").read_text(encoding="utf-8")
