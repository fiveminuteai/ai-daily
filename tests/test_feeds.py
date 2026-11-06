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


def test_rate_limit_kinds(monkeypatch):
    """A per-minute 429 waits and retries on the same provider; a per-day 429 hands over at once."""
    import fma.llm as llm

    class R:
        def __init__(self, code, text, headers=None):
            self.status_code, self.text, self.headers, self.ok = code, text, headers or {}, code < 400

        def json(self):
            return {"choices": [{"message": {"content": "{\"ok\": true}"}}]}

    seq = [R(429, '{"error": {"message": "You exceeded your current quota, requests per minute"}}'), R(200, "")]
    monkeypatch.setattr(llm.requests, "post", lambda *a, **k: seq.pop(0))
    monkeypatch.setattr(llm.time, "sleep", lambda s: None)
    p = llm.Provider("g", "https://x/", "m", key_env="PATH")
    assert p.chat("s", "u") == '{"ok": true}' and not p.exhausted

    monkeypatch.setattr(llm.requests, "post", lambda *a, **k: R(429, "Limit reached on tokens per day (TPD)"))
    p2 = llm.Provider("q", "https://x/", "m", key_env="PATH")
    try:
        p2.chat("s", "u")
        raise AssertionError("should have raised")
    except llm.LLMError:
        pass
    assert p2.exhausted


def test_github_issue_link_reads_the_issue_not_the_readme():
    # 4 Nov 2026: a Postman issue reached the writer as Postman's README, so nothing in it could be cited
    from fma.extract import extract_item
    from fma.models import Item
    issue = {"title": "Desktop auto-installs Codex/Claude plugins", "user": {"login": "indicava"},
             "body": "<!-- template -->Opening Postman installed a Claude Code plugin without asking."}
    http = FakeHttp({"https://api.github.com/repos/postmanlabs/app/issues/7": FakeResponse(json_data=issue),
                     "https://raw.githubusercontent.com/": FakeResponse(content=b"# Postman README")})
    it = Item("hn", "github.com", "Postman auto-installs AI plugins", "https://github.com/postmanlabs/app/issues/7", None)
    text = extract_item(it, http)
    assert text.startswith("GitHub issue opened by indicava in postmanlabs/app: Desktop auto-installs")
    assert "installed a Claude Code plugin" in text and "README" not in text and "template" not in text
    assert not any("raw.githubusercontent" in c for c in http.calls)


def test_text_that_is_not_about_the_title_is_caught():
    from fma.extract import about_title
    title = "Postman silently auto-installs AI plugins and attempts to share all API data"
    assert not about_title(title, "Postman is an API platform. File a bug report on our issue tracker. We are hiring!")
    assert about_title(title, "Postman auto-installs plugins for coding agents and attempts to share API data.")
    assert about_title("AI", "anything")           # no content words: nothing to judge, so keep it


class _Flaky:
    """A provider that fails `fails` times with a passing error, then answers; or hits its daily cap."""

    def __init__(self, name, fails=0, daily=False):
        self.name, self.model, self.fails, self.daily, self.exhausted, self.calls = name, "m", fails, daily, False, 0

    def available(self):
        return True

    def chat(self, system, user, temperature=0.3, careful=False, **kw):
        import fma.llm as llm
        self.calls += 1
        if self.daily:
            self.exhausted = True
            raise llm.LLMError(f"{self.name} daily limit reached (HTTP 429)")
        if self.calls <= self.fails:
            raise llm.LLMError(f"{self.name} HTTP 503: high demand")
        return '{"ok": true}'


def test_chain_waits_and_retries_when_every_provider_is_briefly_down(monkeypatch):
    # 4 Nov 2026: Groq was at its daily cap and one Gemini 503 crashed the whole attempt
    import fma.llm as llm
    waits = []
    monkeypatch.setattr(llm.time, "sleep", waits.append)
    groq, gemini = _Flaky("groq", daily=True), _Flaky("gemini", fails=2)
    chain = llm.Chain([groq, gemini])
    assert chain.ask_json("s", "u") == {"ok": True}
    assert waits == [60, 180] and groq.calls == 1          # the capped provider isn't asked again


def test_chain_gives_up_at_once_when_every_provider_is_out_for_the_day(monkeypatch):
    import fma.llm as llm
    waits = []
    monkeypatch.setattr(llm.time, "sleep", waits.append)
    chain = llm.Chain([_Flaky("groq", daily=True), _Flaky("gemini", daily=True)])
    try:
        chain.ask_json("s", "u")
        raise AssertionError("should have raised")
    except llm.LLMError:
        pass
    assert waits == []


def test_fallback_models_are_configured_in_order():
    from fma import config
    from fma.llm import providers_from_config
    names = [f"{p.name}:{p.model}" for p in providers_from_config({**config.site_config(), "cloud_models": True})]
    assert names[:5] == ["groq:openai/gpt-oss-120b", "groq:qwen/qwen3.8-27b", "gemini:gemini-3.8-flash",
                         "gemini:gemini-3.6-flash", "gemini:gemini-3.5-flash"]
