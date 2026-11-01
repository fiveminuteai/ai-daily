"""Post the day's carousel to Instagram through the Graph API (free, Instagram Content Publishing).

The token is INSTAGRAM_TOKEN: the never-expiring system-user token of the Meta app "Five Minute AI publisher", for
@fiveminute_ai (`instagram_id:` in config/site.yaml). Steps, from Meta's content-publishing reference (31 Oct 2026):
one container per slide (is_carousel_item), a CAROUSEL container with the caption, wait until it is FINISHED, then
media_publish. Images must be JPEG on a public URL: the slides the deploy build puts on the day's share page.

The token goes in POST bodies and query strings only; errors carry the HTTP status and Meta's numeric error code,
never a URL, a token or Meta's own message text.
"""
from __future__ import annotations

import re
import time

API = "https://graph.facebook.com/v26.0"
CAPTION_MAX = 2200          # Instagram's caption limit
HASHTAGS_MAX = 30
SLIDES_MAX = 10             # Meta allows up to 20; our carousels are 7 or 8
WAIT_TRIES, WAIT_SECONDS = 12, 5
REEL_WAIT_TRIES, REEL_WAIT_SECONDS = 40, 15
REEL_COVER_MS = 3500        # the grid cover: a frame with the whole hook on screen and underlined     # Meta fetches and transcodes the video: allow up to 10 minutes


class PublishError(Exception):
    """Posting failed. The message never contains a URL or a token."""


def find_posted(http, ig_id: str, token: str, caption: str) -> dict | None:
    """The recent post with this caption, if there is one: {"id", "permalink"}. Before a retry, so a post that went
    out although its run reported a failure (a timeout after media_publish, say) is recorded, not posted twice."""
    want = caption.strip()[:100]
    data = _call(http, "get", f"{API}/{ig_id}/media", "recent posts",
                 params={"fields": "id,caption,permalink", "limit": "15", "access_token": token}).get("data") or []
    for media in data:
        if (media.get("caption") or "").strip()[:100] == want:
            return {"id": media.get("id"), "permalink": media.get("permalink")}
    return None


def _json(resp, what: str) -> dict:
    if resp.status_code >= 400:
        try:
            code = (resp.json().get("error") or {}).get("code")
        except Exception:  # noqa: BLE001
            code = None
        raise PublishError(f"{what}: HTTP {resp.status_code}" + (f" (Meta error {code})" if isinstance(code, int) else ""))
    try:
        return resp.json()
    except ValueError:
        raise PublishError(f"{what}: not JSON") from None


def _call(http, method: str, url: str, what: str, **kw) -> dict:
    try:
        resp = getattr(http, method)(url, **kw)
    except Exception as exc:  # noqa: BLE001 - a network error's message can include the URL (and a token)
        raise PublishError(f"{what}: {type(exc).__name__}") from None
    return _json(resp, what)


def slide_urls(http, base_url: str, date: str) -> list[str]:
    """The day's carousel slides, read from its public share page. Only the newest post has slides, so an older
    day returns []."""
    page = f"{base_url}share/{date}/"
    try:
        resp = http.get(page)
    except Exception as exc:  # noqa: BLE001
        raise PublishError(f"share page: {type(exc).__name__}") from None
    if resp.status_code == 404:
        return []
    if resp.status_code >= 400:
        raise PublishError(f"share page: HTTP {resp.status_code}")
    names = sorted(set(re.findall(rf"/share/{re.escape(date)}/carousel/(\d{{2}}\.jpg)", resp.text)))
    return [f"{page}carousel/{n}" for n in names]


def check_caption(caption: str) -> None:
    if not caption.strip():
        raise PublishError("caption is empty")
    if len(caption) > CAPTION_MAX:
        raise PublishError(f"caption is {len(caption)} characters, over Instagram's {CAPTION_MAX}")
    if len(re.findall(r"#\w", caption)) > HASHTAGS_MAX:
        raise PublishError(f"caption has more than {HASHTAGS_MAX} hashtags")


def _wait(http, container: str, token: str, tries: int, seconds: float, sleep) -> None:
    for _ in range(tries):              # Meta fetches the media; publishing before FINISHED fails
        status = _call(http, "get", f"{API}/{container}", "status",
                       params={"fields": "status_code", "access_token": token}).get("status_code")
        if status == "FINISHED":
            return
        if status in ("ERROR", "EXPIRED"):
            raise PublishError(f"Instagram could not prepare the media ({status})")
        sleep(seconds)
    raise PublishError(f"the media was not ready after {int(tries * seconds)} seconds")


def _publish(http, ig_id: str, token: str, container: str) -> dict:
    media_id = _call(http, "post", f"{API}/{ig_id}/media_publish", "publish",
                     data={"creation_id": container, "access_token": token})["id"]
    try:                                # the post is live now; a missing link is not a failure
        link = _call(http, "get", f"{API}/{media_id}", "permalink",
                     params={"fields": "permalink", "access_token": token}).get("permalink")
    except PublishError:
        link = None
    return {"id": media_id, "permalink": link}


def publish_reel(http, ig_id: str, token: str, video: str, caption: str, sleep=time.sleep) -> dict:
    """Post one video as a Reel, also shown on the profile grid. Returns {"id", "permalink"}."""
    if not ig_id or not token:
        raise PublishError("instagram_id or INSTAGRAM_TOKEN is not set")
    if not video.startswith("https://") or not video.lower().endswith(".mp4"):
        raise PublishError("the Reel must be a public https MP4")
    check_caption(caption)
    try:
        head = http.head(video)
    except Exception as exc:  # noqa: BLE001
        raise PublishError(f"video check: {type(exc).__name__}") from None
    if head.status_code != 200:
        raise PublishError(f"the Reel video is not on the site yet (HTTP {head.status_code})")
    container = _call(http, "post", f"{API}/{ig_id}/media", "reel",
                      data={"media_type": "REELS", "video_url": video, "caption": caption, "share_to_feed": "true",
                            "thumb_offset": str(REEL_COVER_MS), "access_token": token})["id"]
    _wait(http, container, token, REEL_WAIT_TRIES, REEL_WAIT_SECONDS, sleep)
    return _publish(http, ig_id, token, container)


def publish_carousel(http, ig_id: str, token: str, images: list[str], caption: str, sleep=time.sleep) -> dict:
    """Post the images as one carousel. Returns {"id", "permalink"}."""
    if not ig_id or not token:
        raise PublishError("instagram_id or INSTAGRAM_TOKEN is not set")
    if not 2 <= len(images) <= SLIDES_MAX:
        raise PublishError(f"a carousel needs 2 to {SLIDES_MAX} images, got {len(images)}")
    if any(not u.startswith("https://") or not u.lower().endswith((".jpg", ".jpeg")) for u in images):
        raise PublishError("every image must be a public https JPEG")
    check_caption(caption)
    children = []
    for n, url in enumerate(images, 1):
        children.append(_call(http, "post", f"{API}/{ig_id}/media", f"slide {n}",
                              data={"image_url": url, "is_carousel_item": "true", "access_token": token})["id"])
    container = _call(http, "post", f"{API}/{ig_id}/media", "carousel",
                      data={"media_type": "CAROUSEL", "children": ",".join(children), "caption": caption,
                            "access_token": token})["id"]
    for _ in range(WAIT_TRIES):         # Meta fetches the images; publishing before FINISHED fails
        status = _call(http, "get", f"{API}/{container}", "status",
                       params={"fields": "status_code", "access_token": token}).get("status_code")
        if status == "FINISHED":
            break
        if status in ("ERROR", "EXPIRED"):
            raise PublishError(f"Instagram could not prepare the carousel ({status})")
        sleep(WAIT_SECONDS)
    else:
        raise PublishError("the carousel was not ready after a minute")
    media_id = _call(http, "post", f"{API}/{ig_id}/media_publish", "publish",
                     data={"creation_id": container, "access_token": token})["id"]
    try:                                # the post is live now; a missing link is not a failure
        link = _call(http, "get", f"{API}/{media_id}", "permalink",
                     params={"fields": "permalink", "access_token": token}).get("permalink")
    except PublishError:
        link = None
    return {"id": media_id, "permalink": link}
