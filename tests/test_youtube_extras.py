"""YouTube after the upload (22 Nov 2026): stats per Short, topic playlists, the question as first comment."""
import json

from fma import youtube

ENV = {"YOUTUBE_CLIENT_ID": "c", "YOUTUBE_CLIENT_SECRET": "s", "YOUTUBE_REFRESH_TOKEN": "r"}


class R:
    def __init__(self, code, body):
        self.status_code, self._b = code, body
        self.content = json.dumps(body).encode()

    def json(self):
        return self._b


class FakeYT:
    def __init__(self, fail=()):
        self.calls, self.playlists, self.fail = [], [], set(fail)

    def post(self, url, data=None, json=None, headers=None, **kw):
        self.calls.append(("POST", url, json))
        if url == youtube.TOKEN_URL:
            return R(200, {"access_token": "A"})
        name = url.split("/v3/")[1].split("?")[0]
        if name in self.fail:
            return R(403, {"error": {"errors": [{"reason": "insufficientPermissions"}]}})
        if name == "playlists":
            self.playlists.append({"id": f"PL{len(self.playlists)}", "snippet": json["snippet"]})
            return R(200, self.playlists[-1])
        return R(200, {"id": "x"})

    def get(self, url, headers=None, **kw):
        self.calls.append(("GET", url, None))
        if "/playlists?" in url:
            return R(200, {"items": self.playlists})
        if "/videos?" in url:
            return R(200, {"items": [{"id": "abcdefghijk", "snippet": {"title": "T", "publishedAt": "2026-11-22"},
                                      "statistics": {"viewCount": "91", "likeCount": "3", "commentCount": "1"}},
                                     {"id": "zzzzzzzzzzz", "snippet": {"title": "U"}, "statistics": {"viewCount": "0"}}]})
        if "/channels?" in url:
            return R(200, {"items": [{"statistics": {"subscriberCount": "4", "viewCount": "400"}}]})
        return R(404, {})


def test_video_ids_come_out_of_shorts_and_watch_urls():
    assert youtube.video_id("https://www.youtube.com/shorts/qqt-6S20uCo") == "qqt-6S20uCo"
    assert youtube.video_id("https://www.youtube.com/watch?v=qqt-6S20uCo") == "qqt-6S20uCo"
    assert youtube.video_id("nope") == ""


def test_a_short_joins_its_topic_playlist_made_once_and_gets_the_question_as_first_comment():
    yt = FakeYT()
    note = youtube.extras(yt, "https://www.youtube.com/shorts/abcdefghijk", "products", "Will you miss it[S2]?", ENV)
    assert "playlist New AI products" in note and "first comment" in note
    youtube.extras(yt, "https://www.youtube.com/shorts/abcdefghijk", "products", "", ENV)
    made = [c for c in yt.calls if c[0] == "POST" and "/playlists?" in c[1]]
    assert len(made) == 1 and made[0][2]["status"]["privacyStatus"] == "public"        # reused the second time
    comment = next(c for c in yt.calls if "/commentThreads?" in c[1])
    assert comment[2]["snippet"]["topLevelComment"]["snippet"]["textOriginal"] == "Will you miss it?"


def test_an_extra_that_fails_is_a_note_never_an_error():
    note = youtube.extras(FakeYT(fail={"commentThreads", "playlistItems"}), "https://youtu.be/abcdefghijk", "x", "Q?", ENV)
    assert "playlist failed" in note and "comment failed" in note
    assert youtube.extras(FakeYT(), "https://youtu.be/abcdefghijk", "x", "Q?", {}) == ""            # no secrets: nothing


def test_stats_read_each_shorts_numbers_and_the_channel():
    got = youtube.shorts_stats(FakeYT(), ["https://www.youtube.com/shorts/abcdefghijk",
                                          "https://www.youtube.com/shorts/zzzzzzzzzzz"], ENV)
    assert got["status"] == "ok" and got["subscribers"] == 4
    assert got["shorts"]["abcdefghijk"]["viewCount"] == 91
    assert got["summary"] == {"shorts": 2, "zero_views": 1, "median_views": 91}
    assert youtube.shorts_stats(FakeYT(), [], {})["status"] == "off"


def test_the_reels_topic_and_question_come_from_its_story(tmp_path):
    from fma.social_queue import _story_of
    (tmp_path / "content/posts").mkdir(parents=True)
    (tmp_path / "content/posts/2026-11-22.json").write_text(json.dumps({"sections": [
        {"category": "policy", "card": {"ask": "A?"}}, {"category": "products", "card": {"ask": "B?"}}]}), encoding="utf-8")
    assert _story_of(tmp_path, "2026-11-22", {"story": "1"}) == ("products", "B?")
    assert _story_of(tmp_path, "2026-11-22", {"story": None}) == ("", "")
