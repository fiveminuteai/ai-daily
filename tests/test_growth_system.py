"""The growth plan's system (8 Nov 2026): captions, Instagram extras, YouTube Shorts copy, the scoreboard."""
import json
from datetime import date

from fma import growth, instagram, social, social_queue, youtube

SITE = {"base_url": "https://fiveminuteai.net/"}


def section(title="OpenAI raises money", hook="OpenAI raised $11 billion[S1]."):
    return {"title": title, "card": {"hook": hook, "points": ["A point[S1]."], "ask": "Worth it?"}}


# ---- captions

def test_at_most_five_hashtags_naming_the_story_players():
    tags = social.reel_hashtags(section()).split()
    assert len(tags) <= 5 and tags[:2] == ["#ai", "#ainews"] and "#openai" in tags
    tags = social.reel_hashtags(section("Microsoft and Nvidia", "Nvidia and Microsoft and Google and Anthropic[S1].")).split()
    assert len(tags) == 5


def test_every_reel_caption_asks_for_a_send():
    cap = social.reel_caption(section(), SITE)
    assert any(line in cap for line in social.SEND_LINES)
    assert cap.count("#") <= 5


# ---- Instagram extras

class Resp:
    def __init__(self, code=200, body=None):
        self.status_code, self._body, self.content = code, body or {}, b"video"

    def json(self):
        return self._body


class IG:
    def __init__(self, refuse_extras=False):
        self.sent, self.refuse = [], refuse_extras

    def head(self, url):
        return Resp(404 if url.endswith(".jpg") else 200)

    def post(self, url, data=None, **kw):
        if url.endswith("/media"):
            self.sent.append(dict(data))
            if self.refuse and ("is_ai_generated" in data or "trial_params" in data):
                return Resp(400, {"error": {"code": 100}})
        return Resp(body={"id": "1"})

    def get(self, url, params=None, **kw):
        return Resp(body={"status_code": "FINISHED", "permalink": "https://www.instagram.com/reel/x/"})


def test_reels_carry_the_ai_label_and_an_optional_trial():
    ig = IG()
    instagram.publish_reel(ig, "ig", "t", "https://x.net/r/01.mp4", "Cap #ai", sleep=lambda s: None,
                           trial="SS_PERFORMANCE")
    assert ig.sent[0]["is_ai_generated"] == "true"
    assert json.loads(ig.sent[0]["trial_params"]) == {"graduation_strategy": "SS_PERFORMANCE"}


def test_a_refused_extra_never_costs_the_reel():
    ig = IG(refuse_extras=True)
    out = instagram.publish_reel(ig, "ig", "t", "https://x.net/r/01.mp4", "Cap #ai", sleep=lambda s: None)
    assert out["id"] == "1" and len(ig.sent) == 2 and "is_ai_generated" not in ig.sent[1]


def test_trial_reels_only_where_switched_on():
    assert social_queue.trial_for("2026-11-09-reel-4", {"trial_reels": "off", "trial_slots": [4]}) is None
    assert social_queue.trial_for("2026-11-09-reel-4", {"trial_reels": "ss_performance", "trial_slots": [4]}) == "SS_PERFORMANCE"
    assert social_queue.trial_for("2026-11-09-reel-1", {"trial_reels": "MANUAL", "trial_slots": [4]}) is None


# ---- YouTube Shorts

ENV = {"YOUTUBE_CLIENT_ID": "id", "YOUTUBE_CLIENT_SECRET": "sec", "YOUTUBE_REFRESH_TOKEN": "ref"}


class YT:
    def get(self, url, **kw):
        return Resp(200)

    def post(self, url, data=None, **kw):
        assert url == youtube.TOKEN_URL and data["grant_type"] == "refresh_token"
        return Resp(200, {"access_token": "acc"})


def test_short_titles_fit_and_say_shorts():
    assert youtube.title_for("OpenAI raised $11 billion[S1].") == "OpenAI raised $11 billion. #Shorts"
    assert len(youtube.title_for("word " * 40)) <= youtube.TITLE_MAX


def test_upload_short_and_retry_without_the_disclosure_field():
    calls = []

    def uploader(url, data=None, headers=None, timeout=None):
        calls.append(data)
        if len(calls) == 1:
            return Resp(400, {"error": {"errors": [{"reason": "invalidVideoMetadata"}]}})
        return Resp(200, {"id": "abc"})
    url = youtube.upload_short(YT(), "https://x.net/r/01.mp4", "Cap. Full story, every claim sourced: link in bio "
                               "(fiveminuteai.net)", "Hook[S1].", SITE, "2026-11-09", env=ENV, uploader=uploader)
    assert url == "https://www.youtube.com/shorts/abc"
    assert b"containsSyntheticMedia" in calls[0] and b"containsSyntheticMedia" not in calls[1]
    assert b"https://fiveminuteai.net/" in calls[1] and b"link in bio" not in calls[1]


def test_youtube_stays_off_without_its_secrets(tmp_path, monkeypatch):
    for k in youtube.SECRETS:
        monkeypatch.delenv(k, raising=False)
    assert social_queue.mirror(tmp_path, "2026-11-09-reel-1", {"growth": {"youtube": True}}, YT()) == ""


# ---- the scoreboard

def test_scoreboard_finds_the_bottleneck(tmp_path):
    stats = tmp_path / "data" / "stats"
    stats.mkdir(parents=True)
    posts = [{"id": str(i), "type": "VIDEO", "timestamp": "2026-11-0%dT03:30:00+0000" % (8 - i % 3), "reach": 100,
              "likes": 1, "shares": 0, "saved": 0, "comments": 0, "avg_watch_s": 6.0 + i, "skip_rate": 40.0,
              "caption": f"Reel {i}"} for i in range(5)]
    (stats / "2026-11-01.json").write_text(json.dumps({"date": "2026-11-01", "instagram": {"followers": 1, "posts": []}}))
    (stats / "2026-11-08.json").write_text(json.dumps({"date": "2026-11-08", "instagram": {"followers": 4, "posts": posts}}))
    s = growth.write(tmp_path, date(2026, 11, 8))
    t = s["this_week"]
    assert t["reels"] == 5 and t["avg_watch_s"] == 8.0 and t["follows_per_week"] == 3
    gates = {g["metric"]: g["met"] for g in s["gates"]}
    assert gates["skip_rate"] is True and gates["avg_watch_s"] is False
    assert "Bottleneck: s watched on average" in (tmp_path / "data" / "growth" / "scoreboard.md").read_text()


# ---- the YouTube sign-in helper (9 Nov 2026)

def test_client_file_and_secrets_never_on_a_command_line(tmp_path):
    from fma import youtube_auth
    f = tmp_path / "client.json"
    f.write_text(json.dumps({"installed": {"client_id": "abc.apps.googleusercontent.com", "client_secret": "S3"}}))
    assert youtube_auth.client_from_file(f) == ("abc.apps.googleusercontent.com", "S3")
    calls = []

    class R:
        returncode, stderr = 0, ""

    youtube_auth.save_secret("YOUTUBE_REFRESH_TOKEN", "tok-value", run=lambda cmd, **kw: calls.append((cmd, kw)) or R())
    cmd, kw = calls[0]
    assert "tok-value" not in " ".join(cmd) and kw["input"] == "tok-value"


# ---- the daily carousel (9 Nov 2026)

def test_carousel_time_joins_the_clock_only_when_valid():
    from fma import clock
    s = clock.schedule({"daily": "05:45", "reels": ["09:00", "13:00"], "carousel": "11:00"})
    assert s["carousel"] == "11:00" and ("05:30", "post-scheduled.yml") in clock.events(s)
    assert "carousel" not in clock.schedule({"carousel": "06:00"})          # too soon after the daily run
    assert "carousel" not in clock.schedule({"reels": ["09:00", "13:00"], "carousel": "13:00"})


def test_charts_compare_one_measure_and_private_stories_get_no_quote_slide():
    from fma.carousel import one_measure, plan
    mixed = {"bars": [{"label": "Propaganda Before"}, {"label": "Propaganda After"}, {"label": "Fact Score Before"},
                      {"label": "Fact Score After"}]}
    assert not one_measure(mixed)
    assert one_measure({"bars": [{"label": "OpenAI"}, {"label": "Anthropic"}]})
    post = {"chart": None, "quote": {"text": "I owe my family an apology", "speaker": "CEO", "source": "S1"},
            "sections": [{"title": "CEO admits affair", "paragraphs": ["He admitted an affair[S1]."]}]}
    assert plan(post)[0]["kind"] != "quote"
