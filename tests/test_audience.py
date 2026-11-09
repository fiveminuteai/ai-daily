"""The growth engine's content framework (9 Nov 2026): pains, hook types, CTAs by goal, the market scout."""
from datetime import datetime, timezone

from fma import audience, learn, market, reel_desk, social


def test_labels_keep_only_known_values():
    assert audience.clean_labels({"pain": "Job", "hook_type": "stakes"}) == {"pain": "job", "hook_type": "stakes"}
    assert audience.clean_labels({"pain": "world peace", "hook_type": "clickbait"}) == {}


def test_cta_matches_the_reels_goal():
    assert audience.cta_for({"hook": "h", "take_kind": "do"}) in audience.CTA_SAVE
    assert audience.cta_for({"hook": "h", "pain": "job"}) in audience.CTA_SEND_WORK
    assert audience.cta_for({"hook": "h", "pain": "power"}) in audience.CTA_SEND
    assert audience.cta_for({"hook": "h", "take_kind": "do"}, sensitive=True) in audience.CTA_SEND_SENSITIVE


def test_caption_uses_the_goal_cta():
    sec = {"title": "OpenAI ships a tool", "card": {"hook": "OpenAI ships a tool[S1].", "points": ["A[S1]."],
                                                    "take": "Try it[S1].", "take_kind": "do"}}
    assert any(c in social.reel_caption(sec, {"base_url": "https://x.net/"}) for c in audience.CTA_SAVE)


def test_producer_sees_pains_hooks_and_asks_for_labels():
    p = reel_desk.producer_prompt({"title": "T", "paragraphs": ["x[S1]."]}, [])
    assert "Will AI take or change my job?" in p and "hook_type" in p and '"pain": "job"' in p


def test_learning_measures_pain_and_hook_type():
    assert "pain" in learn.FEATURES and "hook type" in learn.FEATURES


class Resp:
    def __init__(self, body):
        self.status_code, self._b = 200, body

    def json(self):
        return self._b


class YT:
    def __init__(self):
        self.calls = []

    def get(self, url, params=None, **kw):
        self.calls.append((url, params))
        if url.endswith("/search"):
            return Resp({"items": [{"id": {"videoId": "a"}}, {"id": {"videoId": "b"}}]})
        return Resp({"items": [
            {"id": "a", "snippet": {"title": "ChatGPT just changed", "channelTitle": "X"}, "statistics": {"viewCount": "900"},
             "contentDetails": {"duration": "PT45S"}},
            {"id": "b", "snippet": {"title": "A long talk", "channelTitle": "Y"}, "statistics": {"viewCount": "5000"},
             "contentDetails": {"duration": "PT12M3S"}}]})


def test_market_scout_keeps_shorts_ranked_by_views():
    yt = YT()
    m = market.scout(yt, "k", now=datetime(2026, 11, 9, tzinfo=timezone.utc))
    assert [r["id"] for r in m["top"]] == ["a"]                        # the 12-minute video is not a Short
    assert m["top"][0]["region"] == "US"                               # US asked first
    searches = [p for u, p in yt.calls if u.endswith("/search")]
    assert len(searches) == len(market.QUERIES) * len(market.REGIONS)
    assert all(p["videoDuration"] == "short" and p["order"] == "viewCount" for p in searches)


def test_hook_checker_catches_filler_openers_and_buried_news():
    from fma.reel_desk import hook_problems
    assert hook_problems("Hey guys, OpenAI did a thing.")
    assert hook_problems("The new tool will change everything for you soon")
    assert not hook_problems("OpenAI cut its funding goal to $20 billion[S5].")
    assert not hook_problems("Your Gmail now writes back for you[S1].")


def test_duo_hook_line_must_land_in_four_seconds():
    from fma import duo_desk

    class Chain:
        providers = []

        def __init__(self):
            self.prompts = []

        def ask_json(self, system, prompt, **kw):
            self.prompts.append(prompt)
            long = "Nvidia's board says it is starting a big independent investigation into its CEO today[S1]."
            return {"lines": [long, "A memo claims a spy was recruited[S1].", "The board will report back[S1].",
                              "Huang apologised to the company[S1]."]}
    c = Chain()
    assert duo_desk.facts_step(c, {"title": "T", "paragraphs": ["x[S1]."]}, check_facts=False) is None
    assert "the hook must be 12 at most" in c.prompts[-1]


def test_youtube_title_uses_the_short_cover_headline():
    from fma import youtube
    assert youtube.title_for("Nvidia's board opens an investigation into its CEO[S1].") == \
        "Nvidia's board opens an investigation into its CEO. #Shorts"
