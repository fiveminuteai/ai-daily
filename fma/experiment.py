"""One test at a time, on one Reel a day (15 Nov 2026).

Why: 70% of what we post should be what is proven, 20% small changes and 10% experiments (Caleb Ralston's team
practice), and a test changes ONE thing. With 3-4 Reels a day, one Reel in the same slot each day is the test and
the rest are the control. The arm's name is written on the story's card, so the Reel is built that way and the
learning loop (fma/learn.py, feature "test arm") can compare it with the others under its usual guards: 8 Reels a
side, an effect over twice its error, the newest third agreeing.

config/site.yaml:
    experiment: {arm: short-close, reel: 4, until: "2026-12-06", why: "..."}
An arm this code does not know, a missing slot or a date past `until` means no test: the day runs as normal.
"""
from __future__ import annotations

ARMS = {"short-close"}       # each is honoured where the Reel is built (fma/duo_desk.script)


def assign(post: dict, site: dict, slots: int) -> dict:
    exp = site.get("experiment") or {}
    arm, reel = exp.get("arm"), exp.get("reel")
    if arm not in ARMS or not isinstance(reel, int) or str(post.get("date", "")) > str(exp.get("until") or "9999"):
        return post
    from .story_reel import card_stories
    stories = card_stories(post, limit=slots)
    if 1 <= reel <= len(stories):
        stories[reel - 1][1]["card"]["arm"] = arm
    return post
