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
