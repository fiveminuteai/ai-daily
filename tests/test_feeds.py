from datetime import timedelta

from conftest import NOW, FakeHttp, FakeResponse, rss

from fma.feeds import fetch_all, fetch_hf_papers, fetch_hn, is_ai_related, parse_date, parse_feed

ATOM = b"""<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom"><title>t</title>
<entry><title>Atom entry</title><link rel="alternate" href="https://a.example/1"/><updated>2026-10-26T10:00:00Z</updated>
<summary>Hello &lt;b&gt;world&lt;/b&gt;</summary></entry></feed>"""


def test_parse_rss_strips_html_and_reads_dates():
    rows = parse_feed(rss([("A &amp; B", "https://x.example/a", NOW, "<b>bold</b> text")]))
    assert rows[0]["title"] == "A & B"
    assert rows[0]["summary"] == "bold text"
    assert rows[0]["published"] == NOW


def test_parse_atom():
    rows = parse_feed(ATOM)
    assert rows == [{"title": "Atom entry", "url": "https://a.example/1",
                     "published": parse_date("2026-10-26T10:00:00Z"), "summary": "Hello world"}]


def test_parse_feed_survives_garbage():
    assert parse_feed(b"<rss><channel><item><title>no link</title></item>") == []


def test_ai_filter_is_whole_word():
    terms = ["AI", "LLM", "machine learning"]
    assert is_ai_related("New AI chip", terms)
    assert is_ai_related("Machine learning at scale", terms)
    assert not is_ai_related("He said it was fine", terms)       # 'said' contains 'ai'
    assert not is_ai_related("Rain in Spain", terms)


def test_one_broken_source_does_not_stop_the_run():
    feed = rss([("AI model ships", "https://ok.example/1", NOW, "x")])
    http = FakeHttp({"https://ok.example/feed": FakeResponse(200, feed), "https://down.example": FakeResponse(503)})
    cfg = {"ai_terms": ["AI"], "sources": [
        {"id": "ok", "name": "OK", "kind": "rss", "url": "https://ok.example/feed"},
        {"id": "down", "name": "Down", "kind": "rss", "url": "https://down.example/feed"},
        {"id": "off", "name": "Off", "kind": "rss", "url": "https://off.example", "enabled": False}]}
    items, stats = fetch_all(cfg, http, now=NOW)
    assert [i.title for i in items] == ["AI model ships"]
    assert stats["ok"] == "ok:1" and stats["down"].startswith("error") and stats["off"] == "disabled"


def test_hn_and_hf_papers_parsers():
    hn = FakeResponse(200, json_data={"hits": [{"title": "Show HN: tiny LLM", "url": "https://t.example", "points": 420,
                                                "objectID": "9", "created_at_i": int(NOW.timestamp())}]})
    items = fetch_hn({"id": "hn", "name": "Hacker News", "url": "https://hn"}, FakeHttp({"https://hn": hn}))
    assert items[0].points == 420 and items[0].comments_url.endswith("id=9") and items[0].published == NOW

    hf = FakeResponse(200, json_data=[{"publishedAt": (NOW - timedelta(hours=2)).isoformat(),
                                       "paper": {"id": "2610.01234", "title": "A Paper", "summary": "Abs.", "upvotes": 33}}])
    items = fetch_hf_papers({"id": "hf-papers", "name": "HF", "url": "https://hf"}, FakeHttp({"https://hf": hf}))
    assert items[0].url == "https://arxiv.org/abs/2610.01234" and items[0].points == 33


def test_hn_credits_the_linked_site():
    hn = FakeResponse(200, json_data={"hits": [{"title": "Police use AI", "url": "https://www.gizmodo.com/x", "points": 9,
                                                "objectID": "1", "created_at_i": int(NOW.timestamp())},
                                               {"title": "Ask HN: thing", "url": None, "points": 9, "objectID": "2",
                                                "created_at_i": int(NOW.timestamp())}]})
    items = fetch_hn({"id": "hn", "name": "Hacker News", "url": "https://hn"}, FakeHttp({"https://hn": hn}))
    assert items[0].source_name == "gizmodo.com (via Hacker News)" and items[1].source_name == "Hacker News"
