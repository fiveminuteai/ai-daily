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

    def ask_json(self, system, user, temperature=0.3, careful=False):
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
    duo = [p for p in chain.prompts if "comedy" in p.lower() and "THE CAST" in p]
    assert len(chain.prompts) - len(duo) == 3 and "pocket" not in chain.prompts[0]   # one call per story + the chief
    assert len(duo) == 1 and "STORY: Lawsuit" in duo[0]          # the duo desk writes only the Reel-worthy story
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
