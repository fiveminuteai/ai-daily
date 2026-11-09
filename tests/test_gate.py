from conftest import FakeHttp, FakeResponse

from fma.gate import check_images, check_links, is_duplicate, run_gate, word_count

PIPE = {"words_min": 20, "words_max": 600, "min_stories": 3, "llm_check": True}
REPORT = {"layer1_done": True, "layer2_done": True, "headline_problems": []}


def post(**over):
    p = {"date": "2026-10-27", "headline": "Acme ships Nova-2", "dek": "A short dek [S1].",
         "what_happened": ["One [S1].", "Two [S1].", "Three [S1]."],
         "sections": [{"title": f"Section {n}", "paragraphs": [" ".join(
             f"Acme said point {w} of story {n} matters for readers who follow the news closely [S1]." for w in
             ("one", "two", "three", "four", "five"))]} for n in range(3)],
         "why_it_matters": [{"text": "It matters [S1].", "speculative": False}],
         "sources": [{"id": "S1", "url": "https://ok.example/a"}], "visuals": ["timeline"], "quote": None}
    p.update(over)
    return p


def test_good_post_passes():
    assert run_gate(post(), REPORT, PIPE, [], skip_links=True) == []


def test_word_count_out_of_range_fails():
    fails = run_gate(post(), REPORT, {**PIPE, "words_min": 900}, [], skip_links=True)
    assert any("word count" in f for f in fails)


def test_word_count_ignores_citation_markers():
    assert word_count({"headline": "Two words", "dek": "three words here [S1][S2]."}) == 5


def test_missing_verification_fails():
    fails = run_gate(post(), {**REPORT, "layer2_done": False}, PIPE, [], skip_links=True)
    assert "model fact-check pass not run" in fails
    fails = run_gate(post(), {**REPORT, "layer1_done": False}, PIPE, [], skip_links=True)
    assert "verification pass not run" in fails


def test_structure_checks():
    fails = run_gate(post(what_happened=["Only one [S1]."], sections=[], visuals=[], why_it_matters=[]), REPORT, PIPE, [], skip_links=True)
    joined = " ".join(fails)
    assert "bullets" in joined and "sections" in joined and "no visual" in joined and "why it matters" in joined


def test_hype_and_exclamation_fail():
    p = post(dek="A game-changer for everyone! [S1]")
    fails = run_gate(p, REPORT, PIPE, [], skip_links=True)
    assert any("hype" in f for f in fails) and any("exclamation" in f for f in fails)


def test_citation_without_listed_source_fails():
    fails = run_gate(post(dek="Claim [S7]."), REPORT, PIPE, [], skip_links=True)
    assert any("S7" in f for f in fails)


def test_duplicate_of_recent_post_fails():
    recent = [post(date="2026-10-26")]
    assert is_duplicate(post(), recent) == "2026-10-26"
    fails = run_gate(post(), REPORT, PIPE, recent, skip_links=True)
    assert any("too similar" in f for f in fails)
    other = post(date="2026-10-26", headline="EU fines DataCorp",
                 sections=[{"title": t, "paragraphs": []} for t in ("Fine", "Appeal", "Privacy law")])
    assert is_duplicate(post(), [other]) is None


def test_links_404_fails_but_bot_block_is_reachable():
    http = FakeHttp({"https://ok.example": FakeResponse(200), "https://blocked.example": FakeResponse(403),
                     "https://gone.example": FakeResponse(404)})
    bad = check_links(["https://ok.example/a", "https://blocked.example/b", "https://gone.example/c"], http)
    assert bad == {"https://gone.example/c": "HTTP 404"}
    fails = run_gate(post(sources=[{"id": "S1", "url": "https://gone.example/c"}]), REPORT, PIPE, [], http=http)
    assert any("broken links" in f for f in fails)


def test_check_images(tmp_path):
    (tmp_path / "og").mkdir()
    (tmp_path / "og/a.png").write_bytes(b"png")
    page = '<meta property="og:image" content="https://x.github.io/ai-daily/og/a.png"><img src="/ai-daily/og/missing.png">'
    assert check_images(page, tmp_path, "/ai-daily/") == ["/ai-daily/og/missing.png"]


def test_summary_fallbacks_use_verified_sentences_in_section_order():
    from fma.pipeline import fill_summary
    srcs = [{"id": "S1", "story": 1}, {"id": "S2", "story": 2}, {"id": "S3", "story": 3}]
    v = {"dek": "", "what_happened": ["Story three bullet[S3].", "Story two bullet[S2]."],
         "sections": [{"paragraphs": ["Lead fact one[S1]. More[S1]."]}, {"paragraphs": ["Two[S2]."]},
                      {"paragraphs": ["Three[S3]."]}]}
    out = fill_summary(v, srcs)
    assert out["what_happened"] == ["Lead fact one[S1].", "Story two bullet[S2].", "Story three bullet[S3]."]
    assert out["dek"] == "Lead fact one[S1]."


def test_missing_dek_fails_gate():
    assert "no dek" in run_gate(post(dek=""), REPORT, PIPE, [], skip_links=True)


def test_links_timeout_is_not_broken_but_dns_failure_is():
    from requests.exceptions import ConnectionError, ReadTimeout

    class SlowHttp:
        def head(self, u):
            if "dead" in u:
                raise ConnectionError("no such host")
            raise ReadTimeout()
        def get(self, u, **kw):
            if "slowget" in u:
                raise ReadTimeout()
            if "gone" in u:
                return FakeResponse(404)
            return FakeResponse(200)

    bad = check_links(["https://slow.example/a", "https://slowget.example/b", "https://gone.example/c",
                       "https://dead.example/d"], SlowHttp())
    assert bad == {"https://gone.example/c": "HTTP 404", "https://dead.example/d": "ConnectionError"}


def test_mojibake_is_repaired_at_the_source_and_refused_by_the_gate():
    from fma.feeds import fix_mojibake, strip_html
    apos = chr(0x2019)
    junk = apos.encode("utf-8").decode("cp1252")             # the three junk characters a curly apostrophe becomes
    assert strip_html(f"OpenAI{junk}s new model") == f"OpenAI{apos}s new model"
    odd = "caf" + "é".encode("utf-8").decode("cp1252") + " " + chr(0x2014) + " fine"
    assert fix_mojibake(odd) == odd                           # doesn't round-trip cleanly: left alone
    fails = run_gate(post(headline=f"OpenAI{junk}s model"), REPORT, PIPE, [], http=None)
    assert any("garbled" in f for f in fails)


def test_a_stray_exclamation_is_calmed_not_fatal():
    # 6 Nov 2026: one "!" threw away a draft that passed every other check
    from fma.gate import calm, calm_post, unquoted
    assert calm("Google did it! Again!! Now.") == "Google did it. Again. Now."
    assert calm('He said "Order! Order!" and left!') == 'He said "Order! Order!" and left.'
    assert "!" not in unquoted('A quote: "Wow!" stays')
    post = calm_post({"dek": "Big day!", "what_happened": ["One!"], "sections": [{"title": "T!", "paragraphs": ["P!"]}],
                      "why_it_matters": [{"text": "W!"}], "quote": {"text": "Q!"}})
    assert post["dek"] == "Big day." and post["sections"][0]["paragraphs"] == ["P."]
    assert post["quote"]["text"] == "Q!"            # quotes stay verbatim


def test_short_edition_only_for_length_and_shape_failures():
    from fma.gate import soft_only
    assert soft_only(["word count 702 outside 880-1150", "no 'why it matters'"])
    assert not soft_only(["word count 702 outside 880-1150", "hype words: ['revolutionary']"])
    assert not soft_only(["model fact-check pass not run"])
    assert not soft_only([])


def test_headline_rescue_uses_the_checked_lead_title():
    from fma.gate import rescue_headline
    report = {"headline_problems": ["model check: joins two events"]}
    post = rescue_headline({"headline": "Bad", "sections": [{"title": "Lead story title"}]}, report)
    assert post["headline"] == "Lead story title" and not report.get("headline_problems")
    assert report["headline_rescued"]["was"] == "Bad"


def test_a_long_but_checked_draft_is_not_a_lost_day():
    from fma.gate import SHORT_EDITION, soft_only
    assert soft_only(["word count 1213 outside 880-1150"])
    assert SHORT_EDITION["words_max"] >= 1213


# ---- 9 Nov 2026: repeated sentences, dangling openers, thin sections

def _post(paras):
    return {"sections": [{"title": "T", "paragraphs": paras}]}


def test_repeated_sentences_are_removed_and_never_published():
    from fma.gate import dedupe_sentences, quality_problems
    p = _post(["The model is a 27B parameter system[S6]. It uses a 64k context window[S6]. "
               "The model remains a 27B parameter system[S6].", "The model is a 27B parameter system[S6]."])
    assert any("repeated" in x for x in quality_problems(p))
    p, n = dedupe_sentences(p)
    assert n == 2 and p["sections"][0]["paragraphs"] == ["The model is a 27B parameter system[S6]. It uses a 64k context window[S6]."]


def test_dangling_openers_and_thin_sections_fail():
    from fma.gate import quality_problems
    body = " ".join(["Google says users can switch off the AI Coach in the app settings[S5]."] * 1)
    assert any("dangling" in x for x in quality_problems(_post(["They then select Your data[S5]. " + body])))
    assert any("too thin" in x for x in quality_problems(_post(["Google released an update[S5]."])))
