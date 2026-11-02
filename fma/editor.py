"""The editor pass: one model call rates the day's top candidates for how interesting they are to the readers,
and that rating is blended with the importance score before the lineup is picked."""
from __future__ import annotations

import logging

from .models import Story

log = logging.getLogger(__name__)

EDITOR_SYSTEM = """You are the news editor of a daily AI briefing that also runs as short Instagram Reels. You spent
fifteen years on a consumer technology desk and you know which stories people talk about at lunch and which only
specialists read. You are hard to impress: most days, most candidates are filler. You reply with one JSON object and
nothing else."""

# Anchored scale (2 Nov 2026): without anchors the editor gave a GitHub repo 6 and "chatbots are leading hikers into
# danger" 5, and a hobbyist's AI pocket watch made the post and a Reel.
SCALE = """Score 0 to 10 with these anchors:
9-10: affects or endangers many ordinary people, or a giant move everyone will hear about (a ban, a huge lawsuit or
      fine, a major outage or breach, a launch from OpenAI, Google, Apple or Meta that people can use)
7-8:  a big name in a fight or a surprise (a court ruling, a reversal, money trouble, a striking first), AI causing
      real-world harm or help, a security threat to everyday users, a change arriving in apps people already use
5-6:  a solid industry story with a clear consequence, but it stays inside the industry
3-4:  product previews and reviews, hobby builds, renamings and rebrands, opinion essays, single-outlet rumours
0-2:  code repositories, model cards, library releases, customer case studies, papers with no plain result"""


def editor_prompt(stories: list[Story], audience: dict) -> str:
    lines = []
    for n, st in enumerate(stories, 1):
        lead = st.lead
        blurb = " ".join((lead.summary or "").split())[:220]
        lines.append(f"{n}. {lead.title} | {', '.join(sorted(st.publishers))[:80]} | {blurb}")
    interests = "\n".join(f"- {i}" for i in audience.get("interests", []))
    return (f"READERS: {audience.get('description', '')}\nThey care most about:\n{interests}\n\n"
            "Rate each candidate story for how much these readers would want it today, as a story they would tell "
            f"a friend.\n{SCALE}\n"
            "Give near-duplicates of the same event the same score.\n"
            'Reply as {"scores": [{"n": 1, "interest": 7}]} with one entry per candidate.\n\nCANDIDATES\n'
            + "\n".join(lines))


def apply_editor(chain, stories: list[Story], audience: dict, top: int = 30) -> list[Story]:
    """Re-rank the top candidates by importance + interest. Falls back to importance alone on any failure."""
    pool = stories[:top]
    if not pool or not audience or not chain:
        return stories
    weight = float(audience.get("editor_weight", 1.5))
    try:
        reply = chain.ask_json(EDITOR_SYSTEM, editor_prompt(pool, audience), temperature=0.2)
        scores = {int(x["n"]): float(x["interest"]) for x in reply.get("scores", [])
                  if isinstance(x, dict) and str(x.get("n", "")).isdigit()}
    except Exception as exc:  # noqa: BLE001 - the editor is an improvement, never a point of failure
        log.warning("editor pass failed, using importance only: %s", exc)
        return stories
    for n, st in enumerate(pool, 1):
        interest = max(0.0, min(10.0, scores.get(n, 5.0)))
        st.interest = interest
        st.score = round(st.score + weight * interest / 10 * 2, 4)   # interest 10 adds up to 2 x weight
    return sorted(pool, key=lambda s: s.score, reverse=True) + stories[top:]
