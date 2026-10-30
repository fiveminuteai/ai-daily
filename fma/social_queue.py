"""The social approval queue: one file per day, data/social/<date>.json, listing what could go to Instagram, X and
LinkedIn, built from share_texts() so a social post never says more than the checked post does. Nothing here posts
anything. The control dashboard shows the queue; Approve / Edit / Skip dispatch the publish-social workflow, which
for now runs this module's dry run and only logs what it would post.

    python -m fma.social_queue build [--date YYYY-MM-DD]                  write data/social/<date>.json
    python -m fma.social_queue act ITEM_ID --action approve|skip [--text T] [--dry-run]
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from . import config
from .social import share_texts, x_length

# How each platform gets posted, as checked on 31 Oct 2026. The dashboard shows this next to each item.
PLATFORMS = {
    "instagram": {"kind": "carousel", "posting": "api",
                  "note": "Free: Instagram Content Publishing API (Instagram Login, Meta developer app)"},
    "x": {"kind": "post", "posting": "paid",
          "note": "X API has no free tier: about $0.20 per post with a link. Waiting on Pavan's decision"},
    "linkedin": {"kind": "text", "posting": "manual",
                 "note": "Company-page API needs Community Management approval: copy the text and post by hand"},
}
STATUSES = ("pending", "approved", "skipped", "posted", "failed")


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
        prev = old.get(iid)
        if prev:
            item.update({k: prev[k] for k in ("edited_text", "status", "decided_at", "posted_url") if k in prev})
        items.append(item)
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
    how = {"api": f"post to {item['platform']} through its API", "paid": "post to X through the paid API",
           "manual": "nothing (manual platform): mark approved so Pavan copies the text"}[item["posting"]]
    return {"item": iid, "action": "approve", "platform": item["platform"], "would": how,
            "text": final, "media": item.get("media", [])}


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
    args = ap.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    site = config.site_config()
    if args.cmd == "build":
        from .pipeline import today_in
        print(f"wrote {write_queue(config.ROOT, args.date or today_in(site['timezone']), site)}")
        return 0
    try:
        plan = plan_action(config.ROOT, args.item_id, args.action, args.text)
    except ValueError as exc:
        print(f"REFUSED: {exc}")
        return 1
    if not args.dry_run:
        print("REFUSED: live posting is not built yet; run with --dry-run")
        return 1
    print("DRY RUN, nothing posted. Would:", plan["would"])
    print(json.dumps(plan, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
