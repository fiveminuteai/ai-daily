"""The editor pass: one model call rates the day's top candidates for how interesting they are to the readers,
and that rating is blended with the importance score before the lineup is picked."""
from __future__ import annotations

import logging

from .models import Story

log = logging.getLogger(__name__)

EDITOR_SYSTEM = """You are the editor of a daily five-minute AI briefing. You pick what readers will find worth their
time. You reply with one JSON object and nothing else."""


def editor_prompt(stories: list[Story], audience: dict) -> str:
    lines = []
    for n, st in enumerate(stories, 1):
        lead = st.lead
        blurb = " ".join((lead.summary or "").split())[:220]
        lines.append(f"{n}. {lead.title} | {', '.join(sorted(st.publishers))[:80]} | {blurb}")
    interests = "\n".join(f"- {i}" for i in audience.get("interests", []))
    return (f"READERS: {audience.get('description', '')}\nThey care most about:\n{interests}\n\n"
            "Rate each candidate story from 0 to 10 for how interesting and useful it would be to these readers today. "
            "High: major launches, surprising capabilities, things they can use at work, big company moves, "
            "controversies, security, India. Low: customer case studies, routine product notes, niche academic papers "
            "with no clear takeaway, opinion essays, and rumours carried by a single less-reliable outlet. "
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
