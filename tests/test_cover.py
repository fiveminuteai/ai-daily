"""The Reel cover (8 Nov 2026): what goes on it, and how Instagram is told to use it."""
from fma import cover, instagram


def test_headline_uses_the_cover_line_and_lights_up_its_words():
    card = {"hook": "A long hook sentence[S1].", "cover": "Microsoft's AI Frontiers team is over[S4].", "cover_hi": "is over"}
    assert cover.headline(card) == ("Microsoft's AI Frontiers team is over", "is over")


def test_headline_falls_back_to_the_hook_and_drops_a_highlight_not_in_it():
    assert cover.headline({"hook": "Acme ships Nova[S1]."}) == ("Acme ships Nova", "")
    assert cover.headline({"cover": "Acme ships Nova[S1].", "cover_hi": "Beta"})[1] == ""


def test_bubble_is_the_guest_punchline_when_it_fits():
    duo = {"lines": [{"who": "spark", "text": "Fact[S1]."}, {"who": "guest", "text": "Short one."},
                     {"who": "spark", "text": "Fact[S1]."}, {"who": "guest", "text": "No interns? Who makes the coffee?"}]}
    assert cover.bubble({"duo": duo}) == "No interns? Who makes the coffee?"
    duo["lines"][-1]["text"] = "A punchline far too long to fit in a bubble on the cover image."
    assert cover.bubble({"duo": duo}) == "Short one."
    assert cover.bubble({}) is None


class Resp:
    def __init__(self, code=200, body=None):
        self.status_code, self._body = code, body or {}

    def json(self):
        return self._body


class Http:
    def __init__(self, cover_code):
        self.cover_code, self.sent = cover_code, None

    def head(self, url):
        return Resp(self.cover_code if url.endswith(".jpg") else 200)

    def post(self, url, data=None, **kw):
        if url.endswith("/media"):
            self.sent = data
        return Resp(body={"id": "1"})

    def get(self, url, params=None, **kw):
        return Resp(body={"status_code": "FINISHED", "permalink": "https://www.instagram.com/reel/x/"})


def test_reel_uses_the_cover_when_it_is_on_the_site_else_the_frame():
    for code, want in ((200, "cover_url"), (404, "thumb_offset")):
        http = Http(code)
        instagram.publish_reel(http, "ig", "tok", "https://x.net/r/01.mp4", "Caption #ai", sleep=lambda s: None,
                               cover="https://x.net/r/01.jpg")
        assert want in http.sent and ({"cover_url", "thumb_offset"} - {want}).isdisjoint(http.sent)
