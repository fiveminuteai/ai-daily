from conftest import FakeChain

from fma.reel_desk import REEL_BAR, produce, total
from fma.story_reel import card_stories

SOURCES = [{"id": "S1", "publisher": "TechCrunch", "title": "Judge lets lawsuit go ahead"},
           {"id": "S2", "publisher": "The Verge", "title": "A pocket watch"}]


def draft():
    return {"date": "2026-11-03", "sections": [
        {"title": "Lawsuit", "category": "policy", "paragraphs": ["A judge let the lawsuit go ahead[S1]."],
         "card": {"hook": "Writer hook[S1].", "points": ["a[S1].", "b[S1]."], "interest": 3}},
        {"title": "Watch", "category": "impact", "paragraphs": ["Someone built a watch[S2]."],
         "card": {"hook": "Writer hook two[S2].", "points": ["a[S2].", "b[S2]."], "interest": 3}}]}


class Producer(FakeChain):
    """One reply per story, in order."""
    def __init__(self, replies):
        super().__init__([])
        self.queue = list(replies)

    def ask_json(self, system, user, temperature=0.3, careful=False, **kw):
        self.prompts.append(user)
        return self.queue.pop(0)


def script(n, **score):
    return {"score": score, "angle": "why", "hook": f"Story {n} hook names who and stakes[S{n}].",
            "points": [f"p1[S{n}].", f"p2[S{n}].", f"p3[S{n}]."], "take": f"t[S{n}].", "take_kind": "read",
            "ask": "Would you?"}


def test_rubric_total_is_clamped_to_ten():
    assert total({"stakes": 9, "surprise": 9, "names": 9, "number": 9, "relatable": 9}) == 10
    assert total({"stakes": "2", "surprise": None, "names": 1}) == 3


def test_producer_replaces_cards_with_scored_scripts_and_the_bar_drops_filler():
    chain = Producer([script(1, stakes=3, surprise=1, names=2, number=0, relatable=1),
                      script(2, stakes=0, surprise=1, names=0, number=1, relatable=1)])
    out = produce(chain, draft(), SOURCES)
    assert "Reported by: TechCrunch: Judge lets lawsuit go ahead" in chain.prompts[0]
    duo = [p for p in chain.prompts if "short lines for Spark" in p]
    assert len(chain.prompts) - len(duo) == 3 and "pocket" not in chain.prompts[0]   # one call per story + the chief
    assert duo and all("STORY: Lawsuit" in p for p in duo)       # the duo desk writes only the Reel-worthy story
    lawsuit, watch = (s["card"] for s in out["sections"])
    assert lawsuit["reel"] == 7 and lawsuit["hook"].startswith("Story 1") and len(lawsuit["points"]) == 3
    assert watch["reel"] == 3 < REEL_BAR
    assert [n for n, _ in card_stories(out)] == [0]                 # only the lawsuit gets a Reel


def test_weak_day_still_posts_its_best_story_and_a_failed_desk_keeps_the_writer_cards():
    chain = Producer([script(1, stakes=1), script(2, stakes=2, relatable=1)])
    assert [n for n, _ in card_stories(produce(chain, draft(), SOURCES))] == [1]

    class Broken(FakeChain):
        def ask_json(self, *a, **k):
            raise RuntimeError("provider down")
    kept = produce(Broken([]), draft(), SOURCES)
    assert kept == draft()


def test_low_interest_stories_only_fill_gaps_in_the_lineup():
    from datetime import datetime, timezone

    from fma.models import Item, Story
    from fma.rank import pick_lineup

    def st(title, interest, cat):
        s = Story(items=[Item(title=title, url=f"https://x/{title}", source_id=title, source_name=title, published=datetime.now(timezone.utc),
                              summary="", category=cat)])
        s.category, s.interest = cat, interest
        return s
    stories = [st("watch", 4, "impact"), st("lawsuit", 6, "policy"), st("hikers", 5, "products")]
    assert [s.items[0].title for s in pick_lineup(stories, n=2)] == ["lawsuit", "hikers"]
    assert [s.items[0].title for s in pick_lineup(stories, n=3)] == ["lawsuit", "hikers", "watch"]


def test_a_story_the_desk_could_not_script_keeps_the_writer_card_unscored():
    out = produce(Producer([script(1, stakes=3, names=2, surprise=1), {"oops": True}]), draft(), SOURCES)
    assert out["sections"][1]["card"] == draft()["sections"][1]["card"]
    assert [n for n, _ in card_stories(out)] == [0]


def test_the_editor_in_chief_compares_scripts_and_its_score_is_blended_in():
    chief = {"scores": [{"n": 1, "score": 3, "why": "inside baseball"}, {"n": 2, "score": 9, "why": "people at risk"}]}
    chain = Producer([script(1, stakes=3, surprise=1, names=2, number=0, relatable=1),      # rubric 7
                      script(2, stakes=1, surprise=1, names=0, number=1, relatable=1), chief])  # rubric 4
    out = produce(chain, draft(), SOURCES)
    assert "Compare the scripts" in chain.prompts[2] and "Story 2 hook" in chain.prompts[2]
    lawsuit, watch = (s["card"] for s in out["sections"])
    assert lawsuit["reel"] == 5 and watch["reel"] == 6            # (7+3)/2 and (4+9)/2, rounded to even
    assert watch["desk"] == {"rubric": 4, "chief": 9.0, "why": "people at risk"}
    assert [n for n, _ in card_stories(out)] == [1]


def test_a_retry_tells_the_producer_which_reel_lines_the_fact_check_rejected():
    chain = Producer([script(1, stakes=3), script(2, stakes=1), {"scores": []}])
    produce(chain, draft(), SOURCES, ["Apple unveils a robot. (model check: Apple only plans it)"])
    assert all("REJECTED THESE REEL LINES" in p and "Apple only plans it" in p for p in chain.prompts[:2])
    chain = Producer([script(1, stakes=3), script(2, stakes=1), {"scores": []}])
    produce(chain, draft(), SOURCES)
    assert not any("REJECTED" in p for p in chain.prompts)


def test_a_card_the_fact_check_rejected_gets_one_checked_rewrite(monkeypatch):
    """14 Nov 2026: 13 Nov lost all five Reel cards and 14 Nov four of five, so there were no Reels or one."""
    from fma import reel_desk
    src = [{"id": "S1", "story": 1, "title": "Acme ships Nova", "url": "u", "publisher": "P",
            "text": "Acme shipped Nova on Monday. Nova costs 5 dollars a month. Acme said 2 million people signed up."}]
    old = {"hook": "Acme's Nova will change how you work forever[S1].", "points": ["a[S1].", "b[S1]."], "reel": 7}
    draft = {"sections": [{"story": 1, "title": "Acme ships Nova", "card": old,
                           "paragraphs": ["Acme shipped Nova on Monday[S1]."]}]}
    verified = {"sections": [{"story": 1, "title": "Acme ships Nova", "card": None,
                              "paragraphs": ["Acme shipped Nova on Monday[S1]."]}]}
    report = {"entries": [{"where": "card[0] hook", "text": "Acme's Nova will change how you work forever.",
                           "status": "dropped", "problems": ["model check: the source does not say it changes work"]}]}
    asked = []

    def fake_script(chain, section, sources, lessons=None, rejected=""):
        asked.append(rejected)
        return {"hook": "Acme shipped Nova on Monday[S1].", "points": ["Nova costs 5 dollars a month[S1].",
                "Acme said 2 million people signed up[S1]."], "reel": 7}
    monkeypatch.setattr(reel_desk, "script", fake_script)
    out, rep = reel_desk.repair_cards(object(), verified, draft, src, report, check_layer2=False)
    assert "does not say it changes work" in asked[0]
    card = out["sections"][0]["card"]
    assert card["repaired"] and card["hook"].startswith("Acme shipped Nova") and len(card["points"]) == 2
    assert rep["cards_repaired"] == 1 and any(e["where"].startswith("repair") for e in rep["entries"])

    # a rewrite that fails layer 1 too is not used
    monkeypatch.setattr(reel_desk, "script", lambda *a, **k: {"hook": "Acme has 9 million users[S1].",
                                                              "points": ["x 7 y[S1].", "z 8 q[S1]."]})
    verified["sections"][0]["card"] = None
    out, _ = reel_desk.repair_cards(object(), verified, draft, src, {"entries": report["entries"]}, check_layer2=False)
    assert out["sections"][0]["card"] is None

    # 15 Nov 2026: layer 2 dropped the mini-post's only section, the IndexError crashed the 05:45 attempt and the post
    # was skipped. With layer 2 on, a dropped section or a crash leaves the story without a card; the run goes on.
    import fma.verify as verify
    monkeypatch.setattr(reel_desk, "script", fake_script)
    for check in (lambda chain, post, s, r, **k: ({**post, "sections": []}, r),
                  lambda chain, post, s, r, **k: (_ for _ in ()).throw(RuntimeError("layer 2 down"))):
        monkeypatch.setattr(verify, "llm_check", check)
        verified["sections"][0]["card"] = None
        out, _ = reel_desk.repair_cards(object(), verified, draft, src, {"entries": report["entries"]}, check_layer2=True)
        assert out["sections"][0]["card"] is None


def test_a_repaired_card_survives_the_real_model_check_when_it_passes(monkeypatch):
    """19 Nov 2026: the real layer 2 removed every section under 80 words of story, and the repair's one-card
    mini-post has none, so from 14 Nov no repaired card was ever kept (0 in five runs). The old test faked llm_check."""
    import re
    from fma import reel_desk
    src = [{"id": "S1", "story": 1, "title": "Acme ships Nova", "url": "u", "publisher": "P",
            "text": "Acme shipped Nova on Monday. Nova costs 5 dollars a month. Acme said 2 million people signed up."}]
    draft = {"sections": [{"story": 1, "title": "Acme ships Nova", "card": {"hook": "x[S1].", "points": []},
                           "paragraphs": ["Acme shipped Nova on Monday[S1]."]}]}
    verified = {"sections": [{"story": 1, "title": "Acme ships Nova", "card": None,
                              "paragraphs": ["Acme shipped Nova on Monday[S1]."]}]}
    report = {"entries": [{"where": "card[0] hook", "text": "x", "status": "dropped", "problems": ["model check: no"]}]}
    monkeypatch.setattr(reel_desk, "script", lambda *a, **k: {
        "hook": "Acme shipped Nova on Monday[S1].",
        "points": ["Nova costs 5 dollars a month[S1].", "Acme said 2 million people signed up[S1]."], "reel": 7})

    class Approves:                     # a checker that supports every claim with a real quote from the source
        def ask_json(self, system, prompt, **k):
            claims = prompt.split("CLAIMS", 1)[1].split("SOURCES", 1)[0]
            return {"checks": [{"id": i, "evidence": "Nova costs 5 dollars a month", "supported": True, "reason": "ok"}
                               for i in dict.fromkeys(re.findall(r"\bC\d+\b", claims))]}
    out, rep = reel_desk.repair_cards(Approves(), verified, draft, src, report, check_layer2=True)
    card = out["sections"][0]["card"]
    assert card and card["repaired"] and card["hook"].startswith("Acme shipped Nova")
    assert rep["cards_repaired"] == 1


def test_the_producer_prompt_says_only_facts_from_the_text():
    """15 Nov 2026: from 3 Nov the rule read "use O / Y facts" (a stray line break inside ONLY) and nothing noticed."""
    import re
    from fma.reel_desk import PRODUCER_RULES
    assert "FACTS: use ONLY facts in the story's text below." in PRODUCER_RULES
    assert not re.search(r"\b[A-Z]\n[A-Z] ", PRODUCER_RULES)          # no word broken across a line


def test_machine_phrases_and_model_disclaimers_are_caught_on_cards_and_in_the_blog():
    """16 Nov 2026, from blader/humanizer: "plays a pivotal role", "based on available information" and the like."""
    from fma.reel_desk import style_problems
    from fma.write import HYPE_WORDS
    card = {"hook": "Nvidia plays a pivotal role in the evolving landscape of chips[S1].", "points": [
        "Based on available information, sales rose[S1].", "Acme cut prices to 5 dollars[S1]."]}
    found = style_problems(card)
    assert any("hook" in p for p in found) and any("points" in p for p in found)
    assert not style_problems({"hook": "Nvidia cut its chip prices by 10 percent[S1].", "points": ["Sales rose[S1]."]})
    assert {"plays a pivotal role", "based on available information", "let's dive in"} <= set(HYPE_WORDS)


def test_a_lost_card_is_rebuilt_from_the_storys_checked_sentences():
    """16 Nov 2026: 4 of 5 cards were rejected for overstating their stories and only 1 Reel of 4 was made."""
    from fma.reel_desk import fallback_cards
    para = ("Acme cut the price of Nova to 5 dollars a month on Monday[S1]. "
            "She said the change was overdue for many of the smaller customers[S1]. "
            "The company said 2 million people already use the cheaper plan every week[S1]. "
            "Rivals including Beta and Gamma have not changed their prices yet this month[S2].")
    verified = {"what_happened": ["Acme halved the price of its Nova assistant to 5 dollars[S1]."],
                "sections": [{"story": 1, "title": "Acme cuts prices", "paragraphs": [para], "card": None},
                             {"story": 2, "title": "Kept", "paragraphs": [para], "card": {"hook": "h[S1]."}}]}
    draft = {"sections": [{"story": 1, "card": {"hook": "Acme destroys rivals[S1].", "reel": 8, "pain": "money"}},
                          {"story": 2, "card": {"hook": "h[S1]."}}]}
    v, rep = fallback_cards(verified, draft, {})
    card = v["sections"][0]["card"]
    assert rep["cards_fallback"] == 1 and card["fallback"] and card["reel"] == 8 and card["pain"] == "money"
    assert card["hook"] == "Acme halved the price of its Nova assistant to 5 dollars[S1]."   # the post's own bullet leads
    assert all(p in para for p in card["points"]) and len(card["points"]) >= 2               # whole checked sentences
    assert not any("She said" in p for p in card["points"])                                 # no unnamed "she"
    assert v["sections"][1]["card"] == {"hook": "h[S1]."}                                   # a card that survived is kept
    v, rep = fallback_cards({"what_happened": [], "sections": [{"story": 1, "paragraphs": ["Too short[S1]."], "card": None}]},
                            draft, {})
    assert v["sections"][0]["card"] is None and "cards_fallback" not in rep                 # nothing usable: no card


def test_a_rebuilt_card_keeps_a_plain_comment_question_and_never_a_claim():
    """19 Nov 2026, Pavan: the 09:00 Reel's rebuilt card had no question, so it said "Tell us in the comments" to
    nothing. A rebuilt card keeps the writer's question when it states nothing the card does not."""
    from fma.reel_desk import carried_ask
    lines = ["Nvidia stopped H200 chip sales to China[S4].", "Interim CEO Colette Kress announced the halt[S4]."]
    assert carried_ask({"ask": "Will this slow your AI projects?"}, lines) == "Will this slow your AI projects?"
    assert carried_ask({"ask": "Will AI IPOs change your career path[S6]?"}, lines) == "Will AI IPOs change your career path?"
    assert carried_ask({"ask": "Would you trust Kress?"}, lines)                  # a name the card already says
    assert carried_ask({"ask": "Will Nvidia lose 5 billion?"}, lines) is None      # a number is a claim
    assert carried_ask({"ask": "Should Huawei win now?"}, lines) is None           # a name the card never says
    assert carried_ask({"ask": "Tell us what you think"}, lines) is None           # not a question
    assert carried_ask({}, lines) is None
