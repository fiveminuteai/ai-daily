"""The social approval queue: one file per day, data/social/<date>.json, listing what could go to Instagram, X and
LinkedIn, built from share_texts() so a social post never says more than the checked post does. The control
dashboard shows the queue; Approve / Edit / Skip dispatch the publish-social workflow, which runs `act`:
Instagram is posted through the Graph API (fma/instagram.py), LinkedIn is marked approved for Pavan to paste by
hand, X is refused until its paid API is switched on. The result is written back to the queue file.

    python -m fma.social_queue build [--date YYYY-MM-DD]                  write data/social/<date>.json
    python -m fma.social_queue act ITEM_ID --action approve|skip [--text T] [--dry-run]
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from . import config
from .social import share_texts, x_length

# How each platform gets posted, as checked on 31 Oct 2026. The dashboard shows this next to each item.
PLATFORMS = {
    "instagram": {"kind": "carousel", "posting": "api",
                  "note": "The day's carousel, made from the checked post. Posts at schedule.carousel when "
                          "growth.daily_carousel is on (9 Nov 2026)"},
    "x": {"kind": "post", "posting": "paid",
          "note": "X API has no free tier: about $0.20 per post with a link. Waiting on Pavan's decision"},
    "linkedin": {"kind": "text", "posting": "manual",
                 "note": "Company-page API needs Community Management approval: copy the text and post by hand"},
}
STATUSES = ("pending", "approved", "skipped", "posted", "failed")
MAX_ATTEMPTS = 5            # a failed Instagram post is tried again by `due` until it has failed this many times
# One Reel per story with a fact-checked card (fma/story_reel.py), posted at these India times after approval.
REEL = {"kind": "reel", "posting": "api",
        "note": "Free: Instagram Reels through the Content Publishing API. Approve, and it posts at its time"}
REEL_SLOTS = ("09:00", "13:00", "19:00")     # the default; schedule.reels in config/site.yaml (control app) wins


def reel_slots(site: dict) -> tuple[str, ...]:
    from .clock import schedule
    return tuple(schedule(site.get("schedule"))["reels"])


def slot_utc(date: str, hhmm: str) -> str:
    from zoneinfo import ZoneInfo
    local = datetime.fromisoformat(f"{date}T{hhmm}:00").replace(tzinfo=ZoneInfo("Asia/Kolkata"))
    return local.astimezone(timezone.utc).isoformat(timespec="seconds")


def item_id(date: str, platform: str) -> str:
    return f"{date}-{platform}"


def build_queue(post: dict, site: dict, existing: dict | None = None) -> dict:
    """The day's queue. Decisions already made (status, edited text) survive a rebuild."""
    texts = share_texts(post, site)
    old = {i["id"]: i for i in (existing or {}).get("items", [])}
    items = []
    for platform, meta in PLATFORMS.items():
        iid = item_id(post["date"], platform)
        item = {"id": iid, "platform": platform, **meta, "text": texts[platform], "edited_text": None,
                "status": "pending", "decided_at": None, "posted_url": None}
        if platform == "x":
            item["chars"] = x_length(texts["x"])
        if platform == "instagram":
            item["media"] = [f"{site['base_url']}share/{post['date']}/instagram.png"]
            from .clock import schedule
            car = schedule(site.get("schedule")).get("carousel")
            if (site.get("growth") or {}).get("daily_carousel") and car:
                item["status"], item["scheduled_at"] = "approved", slot_utc(post["date"], car)   # 9 Nov 2026
            else:
                item["status"] = "skipped"        # off: still postable on request
        prev = old.get(iid)
        if prev:
            item.update({k: prev[k] for k in ("edited_text", "status", "decided_at", "posted_url", "scheduled_at", "media_id", "error")
                         if k in prev})
        items.append(item)
    from .social import reel_caption
    from .story_reel import card_stories
    slots = reel_slots(site)
    for k, (n, sec) in enumerate(card_stories(post, limit=len(slots))):
        iid = f"{post['date']}-reel-{k + 1}"
        item = {"id": iid, "platform": "instagram_reel", **REEL, "story": n, "hook": sec["card"]["hook"],
                "duo": bool(sec["card"].get("duo")),       # the Reel must render as the duo (media_problem)
                "cover": sec["card"].get("cover"),
                "text": reel_caption(sec, site), "edited_text": None,
                # auto_post_reels (Pavan, 1 Nov 2026: "don't ask, just post them"): queued already approved, so
                # post-scheduled.yml posts each at its time; Skip in the control app before then still stops it
                "status": "approved" if site.get("auto_post_reels") else "pending", "decided_at": None,
                "posted_url": None, "media": [f"{site['base_url']}share/{post['date']}/reels/{k + 1:02d}.mp4"],
                "scheduled_at": slot_utc(post["date"], slots[k])}
        prev = old.get(iid)
        if prev:
            item.update({k2: prev[k2] for k2 in ("edited_text", "status", "decided_at", "posted_url", "scheduled_at",
                                                  "media_id", "error", "attempts", "youtube_url", "youtube_error",
                                                  "youtube_tries") if k2 in prev})
        items.append(item)
    # a Reel already in this day's queue stays, unchanged, even if the schedule now has fewer slots: a change of
    # times only shapes new queues, never what is already queued, approved or posted
    have = {i["id"] for i in items}
    items += [i for iid, i in old.items() if iid not in have and i.get("platform") == "instagram_reel"]
    return {"date": post["date"], "slug": post["slug"], "headline": post["headline"], "url": texts["url"],
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "items": items}


def queue_path(root: Path, date: str) -> Path:
    return root / "data" / "social" / f"{date}.json"


def write_queue(root: Path, date: str, site: dict) -> Path:
    post = json.loads((root / "content" / "posts" / f"{date}.json").read_text(encoding="utf-8"))
    path = queue_path(root, date)
    existing = json.loads(path.read_text(encoding="utf-8")) if path.exists() else None
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(build_queue(post, site, existing), ensure_ascii=False, indent=1), encoding="utf-8")
    return path


def plan_action(root: Path, iid: str, action: str, text: str | None = None) -> dict:
    """What approving or skipping an item would do. Raises ValueError for an unknown item or action."""
    if action not in ("approve", "skip"):
        raise ValueError(f"unknown action {action!r}")
    date = iid[:10]
    path = queue_path(root, date)
    if not path.exists():
        raise ValueError(f"no social queue for {date}")
    queue = json.loads(path.read_text(encoding="utf-8"))
    item = next((i for i in queue["items"] if i["id"] == iid), None)
    if item is None:
        raise ValueError(f"no item {iid}")
    final = text if text else (item.get("edited_text") or item["text"])
    if action == "skip":
        return {"item": iid, "action": "skip", "would": "mark skipped, post nothing"}
    if item["platform"] == "x" and x_length(final) > 280:
        raise ValueError(f"X text is {x_length(final)} characters, over 280")
    if item["status"] == "posted":
        raise ValueError(f"{iid} is already posted ({item.get('posted_url') or 'no link'})")
    how = {"api": f"post to {item['platform']} through its API", "paid": "post to X through the paid API",
           "manual": "nothing (manual platform): mark approved so Pavan copies the text"}[item["posting"]]
    if item.get("scheduled_at") and item["posting"] == "api":
        how += f", at {item['scheduled_at']} (UTC) or as soon as possible after"
    return {"item": iid, "action": "approve", "platform": item["platform"], "would": how,
            "text": final, "media": item.get("media", []), "scheduled_at": item.get("scheduled_at"),
            "story": item.get("story"), "duo": item.get("duo")}


JOURNAL = ".post-journal.jsonl"   # not committed: what this run did, replayed if git can't merge the queue


def _save_item(root: Path, iid: str, **fields) -> None:
    path = queue_path(root, iid[:10])
    queue = json.loads(path.read_text(encoding="utf-8"))
    item = next(i for i in queue["items"] if i["id"] == iid)
    item.update(decided_at=datetime.now(timezone.utc).isoformat(timespec="seconds"), **fields)
    path.write_text(json.dumps(queue, ensure_ascii=False, indent=1), encoding="utf-8")
    # 9 Nov 2026: a run uploaded a Short, then lost the record when its commit clashed with a push to the same
    # queue file, and the next run uploaded it again. Every change is also journalled, so the record step can
    # replay it onto the fresh queue instead of losing it (post-scheduled.yml "Record the result").
    with (root / JOURNAL).open("a", encoding="utf-8") as j:
        j.write(json.dumps({"id": iid, "fields": {"decided_at": item["decided_at"], **fields}}, ensure_ascii=False) + "\n")


def replay(root: Path, journal: Path) -> int:
    """Apply a run's journalled changes to the current queue files (after taking the latest main). Returns how
    many changes were applied. A change for an item that no longer exists is skipped."""
    n = 0
    if not journal.exists():
        return 0
    for line in journal.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        rec = json.loads(line)
        path = queue_path(root, rec["id"][:10])
        if not path.exists():
            continue
        queue = json.loads(path.read_text(encoding="utf-8"))
        item = next((i for i in queue["items"] if i["id"] == rec["id"]), None)
        if item is None:
            continue
        item.update(rec["fields"])
        path.write_text(json.dumps(queue, ensure_ascii=False, indent=1), encoding="utf-8")
        n += 1
    return n


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _post(root: Path, iid: str, plan: dict, site: dict, http, token: str | None, edited: str | None,
          attempts: int = 0, now: datetime | None = None) -> str:
    """Publish one Instagram item now and record the result. Raises PublishError (recorded) on failure.
    `attempts` is how many tries already failed; a retry first checks Instagram so nothing is posted twice."""
    from .instagram import PublishError, find_posted, publish_carousel, publish_reel, slide_urls

    ig_id = str(site.get("instagram_id") or "")
    try:
        # 11 Nov 2026 audit: checked before every post, not only retries: a run whose record was lost (a merge
        # clash, a timeout after media_publish) leaves the item "approved" with no attempts, and it would go twice
        try:
            found = find_posted(http, ig_id, token or "", plan["text"])
        except PublishError:
            if attempts:
                raise
            found = None             # Instagram unreachable for the check: the publish call below will say so
        if found:
            result, what = found, "found on Instagram after a reported failure"
        elif plan["platform"] == "instagram_reel":
            video = plan["media"][0]
            problem = media_problem(http, {**plan, "id": iid}, site["base_url"]) if early(root, iid, now) else ""
            if problem:            # after the wait it posts what there is, and the health check reports it
                raise PublishError(problem)
            growth = site.get("growth") or {}
            result = publish_reel(http, ig_id, token or "", video, plan["text"],
                                  cover=video[:-4] + ".jpg" if video.endswith(".mp4") else None,
                                  ai_label=growth.get("ai_label", True), trial=trial_for(iid, growth))
            what = "Reel"
        else:
            images = slide_urls(http, site["base_url"], iid[:10])
            if not images:
                raise PublishError("no carousel slides on the share page (only the newest post has them)")
            result = publish_carousel(http, ig_id, token or "", images, plan["text"])
            what = f"{len(images)} slides"
    except PublishError as exc:
        if waiting(str(exc)) and early(root, iid, now):
            # the Reel isn't on the site yet (the deploy is still rendering): not a failed attempt for two hours,
            # or five quick 404s while a late post deploys would give the Reel up for good
            _save_item(root, iid, status="approved", error=str(exc), edited_text=edited)
        else:
            _save_item(root, iid, status="failed", error=str(exc), edited_text=edited, attempts=attempts + 1)
        raise
    _save_item(root, iid, status="posted", posted_url=result["permalink"], media_id=result["id"], error=None,
               edited_text=edited)
    done = f"{iid} posted to Instagram: {result['permalink'] or result['id']} ({what})"
    if plan["platform"] == "instagram_reel":
        done += mirror(root, iid, site, http)
    return done


WAIT_FOR_MEDIA = timedelta(hours=2)


def waiting(error: str) -> bool:
    return "not on the site yet" in error or "media not ready" in error


def early(root: Path, iid: str, now: datetime | None = None) -> bool:
    """True within WAIT_FOR_MEDIA of the item's slot."""
    try:
        item = next(i for i in json.loads(queue_path(root, iid[:10]).read_text(encoding="utf-8"))["items"]
                    if i["id"] == iid)
        return (now or _now()) < datetime.fromisoformat(item["scheduled_at"]) + WAIT_FOR_MEDIA
    except (OSError, ValueError, KeyError, StopIteration, TypeError):
        return False


def media_problem(http, item: dict, base_url: str) -> str:
    """Why this Reel's rendered file isn't the one to post yet, from share/<date>/media.json (fma/site.py), or "".
    11 Nov 2026 audit: the file is re-rendered on every deploy; it must be for the item's own story and, when the
    card has a duo, be the duo. No manifest (older deploys) means no objection."""
    try:
        resp = http.get(f"{base_url.rstrip('/')}/share/{item['id'][:10]}/media.json")
        man = resp.json() if resp.status_code == 200 else None
    except Exception:  # noqa: BLE001
        return ""
    if not isinstance(man, dict):
        return ""
    name = str((item.get("media") or [""])[0]).rsplit("/share/", 1)[-1].split("/", 1)[-1]
    reel = next((r for r in man.get("reels", []) if r.get("file") == name), None)
    if reel is None:
        return f"media not ready: {name} is not in this deploy's render"
    if isinstance(item.get("story"), int) and reel.get("story") != item["story"]:
        return f"media not ready: {name} shows story {reel.get('story')}, the caption is story {item['story']}"
    if item.get("duo") and not reel.get("duo"):
        return f"media not ready: {name} rendered plain ({reel.get('plain_because', '?')}) but the card has a duo"
    return ""


def trial_for(iid: str, growth: dict) -> str | None:
    """The trial-Reel setting for this Reel: growth.trial_reels is "off", or a graduation strategy (MANUAL or
    SS_PERFORMANCE) for the Reel numbers listed in growth.trial_slots (default: none)."""
    strategy = str(growth.get("trial_reels") or "off").upper()
    if strategy not in ("MANUAL", "SS_PERFORMANCE"):
        return None
    n = int(iid.rsplit("-", 1)[-1]) if iid.rsplit("-", 1)[-1].isdigit() else 0
    return strategy if n in (growth.get("trial_slots") or []) else None


def mirror(root: Path, iid: str, site: dict, http) -> str:
    """Copy a posted Reel to YouTube Shorts (8 Nov 2026, growth plan). Off until the YouTube secrets exist; a failure
    is recorded on the item and never touches the Instagram post. Returns a note for the log."""
    from .youtube import YouTubeError, configured, upload_short
    if not (site.get("growth") or {}).get("youtube", True) or not configured():
        return ""
    path = queue_path(root, iid[:10])
    item = next(i for i in json.loads(path.read_text(encoding="utf-8"))["items"] if i["id"] == iid)
    if item.get("youtube_url") or item.get("youtube_tries", 0) >= MAX_ATTEMPTS:
        return ""
    try:
        url = upload_short(http, item["media"][0], item.get("edited_text") or item["text"],
                           item.get("cover") or item.get("hook") or "",
                           site, iid[:10])
    except YouTubeError as exc:
        gone = "HTTP 404" in str(exc) or "outcome unknown" in str(exc)   # won't come back / may already be there
        _save_item(root, iid, youtube_error=str(exc),
                   youtube_tries=MAX_ATTEMPTS if gone else item.get("youtube_tries", 0) + 1)
        return f"; YouTube not uploaded (recorded{', given up' if gone else ''}): {exc}"
    _save_item(root, iid, youtube_url=url, youtube_error=None)
    return f"; YouTube Short: {url}"


def act(root: Path, iid: str, action: str, text: str | None, site: dict, http, token: str | None,
        now: datetime | None = None) -> str:
    """Carry out an approve or skip and record it in the queue file. Returns a one-line result.
    An approved Instagram item with a later scheduled time waits for `due`; otherwise it posts now.
    Raises ValueError for a refused request (nothing changed) and PublishError when posting failed (recorded)."""
    plan = plan_action(root, iid, action, text)
    edited = text or None
    if action == "skip":
        _save_item(root, iid, status="skipped")
        return f"{iid} skipped, nothing posted"
    platform = plan["platform"]
    if platform == "linkedin":
        _save_item(root, iid, status="approved", edited_text=edited)
        return f"{iid} approved: copy the text and post it on LinkedIn by hand"
    if platform not in ("instagram", "instagram_reel"):
        raise ValueError(f"posting to {platform} is not switched on")
    when = plan.get("scheduled_at")
    if when and datetime.fromisoformat(when) > (now or _now()):
        _save_item(root, iid, status="approved", edited_text=edited, error=None)
        return f"{iid} approved, will post at {when} (UTC)"
    return _post(root, iid, plan, site, http, token, edited, now=now)


def due(root: Path, site: dict, http, token: str | None, now: datetime | None = None) -> list[str]:
    """Post every approved Instagram item whose time has come (today's and yesterday's queues), and try failed ones
    again until they have failed MAX_ATTEMPTS times. One failure is recorded and the rest still go."""
    from .instagram import PublishError

    now = now or _now()
    out = []
    for path in sorted(queue_path(root, "x").parent.glob("*.json"))[-2:]:
        for item in json.loads(path.read_text(encoding="utf-8"))["items"]:
            if item["platform"] not in ("instagram", "instagram_reel"):
                continue
            if item["platform"] == "instagram_reel" and item["status"] == "posted":
                note = mirror(root, item["id"], site, http)       # a YouTube copy that failed earlier, again
                if note:
                    out.append(f"{item['id']}{note}")
                continue
            tried = item.get("attempts", 1 if item["status"] == "failed" else 0)
            retry = item["status"] == "failed" and tried < MAX_ATTEMPTS
            if item["status"] != "approved" and not retry:
                continue
            if item.get("scheduled_at") and datetime.fromisoformat(item["scheduled_at"]) > now:
                continue
            plan = {"platform": item["platform"], "media": item.get("media", []),
                    "text": item.get("edited_text") or item["text"], "story": item.get("story"), "duo": item.get("duo")}
            try:
                out.append(_post(root, item["id"], plan, site, http, token, item.get("edited_text"), tried, now=now))
            except PublishError as exc:
                out.append(f"{item['id']} FAILED (recorded): {exc}")
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="fma.social_queue")
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build")
    b.add_argument("--date")
    a = sub.add_parser("act")
    a.add_argument("item_id")
    a.add_argument("--action", required=True)
    a.add_argument("--text")
    a.add_argument("--dry-run", action="store_true")
    sub.add_parser("due", help="post approved Instagram items whose time has come")
    rp = sub.add_parser("replay", help="apply a run's journal to the queue files (after a merge clash)")
    rp.add_argument("journal")
    args = ap.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    site = config.site_config()
    if args.cmd == "build":
        from .pipeline import today_in
        print(f"wrote {write_queue(config.ROOT, args.date or today_in(site['timezone']), site)}")
        return 0
    if args.cmd == "replay":
        print(f"replayed {replay(config.ROOT, Path(args.journal))} changes")
        return 0
    if args.cmd == "due":
        import os

        from .feeds import Http
        lines = due(config.ROOT, site, Http(), os.environ.get("INSTAGRAM_TOKEN"))
        print("\n".join(lines) or "nothing due")
        return 1 if any("FAILED" in ln for ln in lines) else 0
    try:
        plan = plan_action(config.ROOT, args.item_id, args.action, args.text)
    except ValueError as exc:
        print(f"REFUSED: {exc}")
        return 1
    if args.dry_run:
        print("DRY RUN, nothing posted. Would:", plan["would"])
        print(json.dumps(plan, ensure_ascii=False, indent=1))
        return 0
    import os

    from .feeds import Http
    from .instagram import PublishError
    try:
        print(act(config.ROOT, args.item_id, args.action, args.text, site, Http(), os.environ.get("INSTAGRAM_TOKEN")))
    except ValueError as exc:
        print(f"REFUSED: {exc}")
        return 1
    except PublishError as exc:
        print(f"FAILED (recorded in the queue): {exc}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
