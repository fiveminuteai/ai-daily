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
# 3 Nov 2026 (Pavan): the AI giants and the companies that challenge them are what bring readers to the page.
SCALE = """THE PLAYERS: the giants are OpenAI, Anthropic, Google (Gemini, DeepMind), Meta, Microsoft, Apple, Nvidia,
xAI and Amazon; the challengers are the labs and companies taking them on (DeepSeek, Mistral, Qwen, Kimi,
Perplexity, Cursor and the like). Our readers follow this race like sport.
Score 0 to 10 with these anchors:
9-10: a giant's big move (a new frontier model, a major outage or breach, a huge lawsuit, deal, fine or leadership
      fight), a challenger beating or undercutting a giant, or AI harming or endangering many ordinary people
7-8:  a giant or challenger in a fight, a reversal, money trouble or a striking first; a giant's feature arriving
      in apps people already use; a security threat to everyday users
5-6:  a solid industry story with a clear consequence, but no giant or challenger at its centre
3-4:  product previews and reviews from small companies, hobby builds, renamings and rebrands, opinion essays,
      single-outlet rumours
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
