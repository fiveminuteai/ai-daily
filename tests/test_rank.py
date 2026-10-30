from datetime import timedelta

from conftest import NOW

from fma.models import Item, Story
from fma.rank import already_covered, cluster, history_entry, norm_url, pick_lineup, rank, score_story

PIPE = {"lookback_hours": 40, "dedupe_days": 14, "similar_title_days": 3}
CFG = {"category_hints": {"policy": ["IPO", "S-1"], "models": ["model"]}}


def item(title, url, src="news", hours=3, weight=1.0, outlet="", strict=False, cat="products", points=0, primary=False):
    return Item(source_id=src, source_name=src.title(), title=title, url=url, published=NOW - timedelta(hours=hours),
                weight=weight, outlet=outlet, strict_match=strict, category=cat, points=points, primary=primary)


def test_same_event_differently_worded_is_one_story():
    items = [item("Anthropic files S-1 for IPO", "https://a/1", "hn"),
             item("Five details from Anthropic's IPO filing", "https://b/2", "techcrunch"),
             item("Anthropic's IPO prospectus is missing key figures", "https://c/3", "wired"),
             item("Robots fold laundry", "https://d/4", "verge")]
    stories = cluster(items)
    sizes = sorted(len(s.items) for s in stories)
    assert sizes == [1, 3]


def test_paper_feeds_only_match_on_near_identical_titles():
    items = [item("Working with academic communities to build scientific understanding", "https://openai/x", "openai"),
             item("Scientific discovery agents for academic communities", "https://arxiv.org/abs/1", "arxiv-ai",
                  outlet="arXiv", strict=True, cat="research")]
    assert len(cluster(items)) == 2


def test_cross_listed_paper_merges_by_url_and_counts_as_one_outlet():
    items = [item("Paper X", "https://arxiv.org/abs/2610.1v1", "arxiv-ai", outlet="arXiv", strict=True),
             item("Paper X", "http://arxiv.org/abs/2610.1", "arxiv-cl", outlet="arXiv", strict=True)]
    st = cluster(items)
    assert len(st) == 1 and st[0].publishers == {"arXiv"}


def test_score_rewards_coverage_recency_and_attention():
    lone = Story([item("Lone story", "https://x/1")])
    wide = Story([item("Big story", "https://x/2", "a"), item("Big story", "https://x/3", "b"), item("Big story", "https://x/4", "c")])
    old = Story([item("Old story", "https://x/5", hours=36)])
    hot = Story([item("HN story", "https://x/6", "hn", points=900)])
    assert score_story(wide, NOW) > score_story(lone, NOW) > score_story(old, NOW)
    assert score_story(hot, NOW) > score_story(lone, NOW)


def test_rank_drops_items_outside_lookback():
    stories = rank([item("Fresh", "https://x/1"), item("Stale", "https://x/2", hours=80)], CFG, PIPE, [], NOW, "2026-10-27")
    assert [s.title for s in stories] == ["Fresh"]


def test_dedupe_by_url_and_by_yesterdays_similar_title():
    hist = [history_entry("2026-10-26", "s", [Story([item("Acme launches Nova-2 model", "https://acme/nova")])])]
    same_url = Story([item("Totally different title", "https://acme/nova/")])
    similar = Story([item("Acme launches Nova-2 model today", "https://other/x")])
    fresh = Story([item("EU passes chip law", "https://eu/law")])
    assert already_covered(same_url, hist, "2026-10-27", 14, 3)
    assert already_covered(similar, hist, "2026-10-27", 14, 3)
    assert not already_covered(fresh, hist, "2026-10-27", 14, 3)
    # a similar title more than 3 days ago is allowed again; the same URL within 14 days is not
    assert not already_covered(similar, hist, "2026-10-31", 14, 3)
    assert already_covered(same_url, hist, "2026-11-08", 14, 3)
    assert not already_covered(same_url, hist, "2026-11-10", 14, 3)


def test_history_never_includes_today_itself():
    hist = [history_entry("2026-10-27", "s", [Story([item("A", "https://a")])])]
    assert not already_covered(Story([item("A", "https://a")]), hist, "2026-10-27", 14, 3)


def test_lineup_caps_category_and_single_source_and_adds_research():
    def st(title, src, cat, score):
        s = Story([item(title, f"https://{src}/{title}", src, cat=cat, primary=src == "openai")], score=score, category=cat)
        return s
    stories = [st("OpenAI one", "openai", "models", 9), st("OpenAI two", "openai", "products", 8),
               st("Model A", "verge", "models", 7), st("Model B", "wired", "models", 6),
               st("Policy C", "ars", "policy", 5), st("Tool D", "hn", "tools", 4), st("Impact E", "mit", "impact", 3),
               st("Paper F", "arxiv", "research", 1)]
    names = [s.title for s in pick_lineup(stories, n=5)]
    assert "OpenAI two" not in names            # one story per single-source blog
    assert "Model B" not in names               # max two per category
    assert "Paper F" in names                   # research gets a slot
    assert len(names) == 5


def test_lineup_skips_second_angle_on_same_event():
    a = Story([item("Anthropic IPO filing details", "https://a/1", "tc")], score=5, category="policy")
    b = Story([item("Anthropic IPO filing strategy", "https://b/1", "wired")], score=4, category="impact")
    c = Story([item("Robots fold shirts", "https://c/1", "verge")], score=3, category="research")
    assert [s.title for s in pick_lineup([a, b, c], n=3)] == ["Anthropic IPO filing details", "Robots fold shirts"]


def test_norm_url():
    assert norm_url("https://www.Example.com/a/?utm=1#x") == "example.com/a"
    assert norm_url("https://arxiv.org/pdf/2610.01234v2") == "arxiv.org/abs/2610.01234"


def test_lead_switches_to_readable_article_when_lab_page_is_empty():
    lab = item("Genie 4: world simulation", "https://deepmind/genie", "deepmind", primary=True, weight=1.5)
    news = item("Google's Genie 4 world model adds audio", "https://tc/genie", "techcrunch")
    st = Story([lab, news])
    assert st.lead is lab                               # before any text is fetched, the lab's own post leads
    lab.text, news.text = "Genie 4", "Full article text. " * 60
    assert st.lead is news                              # the lab page came back nearly empty
    lab.text = "Full lab announcement. " * 60
    assert st.lead is lab                               # with readable text, the primary source leads again


def test_outlet_read_through_two_feeds_counts_once_and_brain_implants_pass_the_ai_filter():
    from fma import config
    from fma.feeds import is_ai_related
    url = "https://techcrunch.com/2026/10/30/neuralink-telepathy/"
    a = Item(source_id="techcrunch", source_name="TechCrunch", title="Neuralink opens Telepathy to more patients", url=url,
             published=NOW)
    b = Item(source_id="techcrunch-all", source_name="TechCrunch", title="Neuralink opens Telepathy to more patients",
             url=url, published=NOW)
    (story,) = cluster([a, b])
    assert story.publishers == {"TechCrunch"}
    terms = config.sources_config()["ai_terms"]
    assert is_ai_related("Neuralink says its brain-computer interface now types at 40 words a minute", terms)
    assert not is_ai_related("The best electric toothbrush deals this week", terms)
    names = [s["name"] for s in config.sources_config()["sources"]]
    from fma.site import first_by_name
    assert len({s["name"] for s in first_by_name(config.sources_config()["sources"])}) == len(set(names))
