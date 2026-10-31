import json

from conftest import FakeHttp, FakeResponse

from fma import stats

SITE = {"goatcounter": "fiveminuteai"}
GC = "https://fiveminuteai.goatcounter.com/api/v0/stats"
IG = "https://graph.instagram.com/v26.0"
ENV = {"GOATCOUNTER_TOKEN": "gc-secret", "INSTAGRAM_TOKEN": "ig-secret"}


def routes():
    return {
        f"{GC}/total?": FakeResponse(200, json_data={"total": 310, "stats": [
            {"day": "2026-10-30", "daily": 120}, {"day": "2026-10-31", "daily": 190}]}),
        f"{GC}/hits?": FakeResponse(200, json_data={"hits": [
            {"path": "/posts/a/", "title": "A", "count": 150, "event": False},
            {"path": "share-click", "title": "", "count": 9, "event": True}], "more": False}),
        f"{GC}/toprefs?": FakeResponse(200, json_data={"stats": [{"name": "instagram.com", "count": 40}, {"name": "", "count": 5}]}),
        f"{IG}/me?": FakeResponse(200, json_data={"user_id": "1", "username": "fiveminute_ai", "followers_count": 87, "media_count": 4}),
        f"{IG}/me/insights?": FakeResponse(200, json_data={"data": [
            {"name": "reach", "total_value": {"value": 640}}, {"name": "views", "total_value": {"value": 1200}}]}),
        f"{IG}/me/media?": FakeResponse(200, json_data={"data": [
            {"id": "m1", "caption": "Mistral opens weights\n#ai", "timestamp": "2026-10-31T03:00:00+0000",
             "permalink": "https://www.instagram.com/p/x/", "like_count": 21, "comments_count": 3, "media_type": "CAROUSEL_ALBUM"},
            {"id": "m2", "timestamp": "2026-10-30T03:00:00+0000", "media_type": "IMAGE"}]}),
        f"{IG}/m1/insights?": FakeResponse(200, json_data={"data": [
            {"name": "reach", "values": [{"value": 410}]}, {"name": "saved", "values": [{"value": 12}]}]}),
        # m2 insights: 404 -> the post is still listed, without insight numbers
    }


def test_collects_website_and_instagram():
    snap = stats.collect(FakeHttp(routes()), "2026-10-31", SITE, ENV)
    w, ig = snap["website"], snap["instagram"]
    assert w["status"] == "ok" and w["visitors_28d"] == 310 and w["visitors_day"] == 190
    assert w["daily"] == [{"day": "2026-10-30", "visitors": 120}, {"day": "2026-10-31", "visitors": 190}]
    assert w["top_paths"] == [{"path": "/posts/a/", "title": "A", "visitors": 150}]        # events left out
    assert w["top_refs"][1]["name"] == "(direct)"
    assert ig["status"] == "ok" and ig["followers"] == 87 and ig["username"] == "fiveminute_ai"
    assert ig["day"]["reach"] == 640 and ig["day"]["accounts_engaged"] is None
    p1, p2 = ig["posts"]
    assert p1["caption"] == "Mistral opens weights" and p1["reach"] == 410 and p1["saved"] == 12 and p1["views"] is None
    assert p2["reach"] is None and p2["likes"] is None


def test_missing_tokens_mean_off_not_error():
    snap = stats.collect(FakeHttp({}), "2026-10-31", SITE, {})
    assert snap["website"] == {"status": "off", "note": "set GOATCOUNTER_TOKEN"}
    assert snap["instagram"]["status"] == "off"
    assert stats.collect(FakeHttp({}), "2026-10-31", {}, ENV)["website"]["status"] == "off"


def test_errors_never_carry_urls_or_tokens():
    class Boom(FakeHttp):
        def get(self, url, **kw):
            raise ConnectionError(f"failed to reach {url}")          # what requests' messages look like

    r = routes()
    r[f"{IG}/me?"] = FakeResponse(400, json_data={"error": {"message": "token expired"}})
    snap = stats.collect(FakeHttp(r), "2026-10-31", SITE, ENV)
    assert snap["instagram"] == {"status": "error", "error": "HTTP 400"}
    snap = stats.collect(Boom({}), "2026-10-31", SITE, ENV)
    assert snap["website"] == {"status": "error", "error": "ConnectionError"}
    text = json.dumps(snap)
    assert "secret" not in text and "http" not in text


def test_account_insights_failure_keeps_profile_numbers():
    r = routes()
    r[f"{IG}/me/insights?"] = FakeResponse(403, json_data={})
    ig = stats.collect(FakeHttp(r), "2026-10-31", SITE, ENV)["instagram"]
    assert ig["status"] == "ok" and ig["followers"] == 87 and ig["day_error"] == "HTTP 403"


def test_snapshot_file(tmp_path):
    snap = stats.collect(FakeHttp({}), "2026-10-31", SITE, {})
    path = stats.write_snapshot(tmp_path, snap)
    assert path == tmp_path / "data/stats/2026-10-31.json"
    assert json.loads(path.read_text(encoding="utf-8"))["date"] == "2026-10-31"


def test_system_user_token_reads_through_facebook_graph():
    fb = "https://graph.facebook.com/v26.0"
    r = {k.replace(f"{IG}/me", f"{fb}/1784").replace(IG, fb): v for k, v in routes().items()}
    r[f"{fb}/1784/insights?"] = FakeResponse(403, json_data={"error": {"message": "needs permission", "code": 10}})
    ig = stats.collect(FakeHttp(r), "2026-10-31", {**SITE, "instagram_id": "1784"}, ENV)["instagram"]
    assert ig["status"] == "ok" and ig["username"] == "fiveminute_ai" and ig["posts"][0]["reach"] == 410
    assert ig["day_error"] == "HTTP 403 (Meta error 10)"
