"""Who we make Reels for, what they worry about, and how a Reel earns their attention (9 Nov 2026, growth engine).

The content framework every Reel follows, end to end:
  1. PAIN      the viewer's worry this story touches (PAINS); a story that touches none is a weak Reel
  2. HOOK      one of the HOOK_TYPES, in the first line and on the cover; the first 3 seconds decide the reach
  3. VALUE     three fact-checked points: what happened, the twist, who it affects
  4. SOLVE     the take: what it means for the viewer, or one thing to do
  5. VISUAL    cover headline, the number panel, the cast reacting
  6. CTA       one action matched to the Reel's goal (cta_for): save a how-to, send a surprise, answer a question
  7. LEARN     pain and hook type are recorded on every card, and fma/learn.py measures which hold viewers

Viewers: people aged 20-40 who work with or around tech, in India and the US (the US is where ad money and
sponsors pay most), who use AI tools but don't follow AI for a living."""
from __future__ import annotations

import zlib

PAINS = {
    "job": "Will AI take or change my job?",
    "skills": "What should I learn so I don't fall behind?",
    "tools": "Which AI tool should I use, and is it worth paying for?",
    "money": "What does AI cost me, and who is getting rich from it?",
    "privacy": "Is my data and my privacy safe?",
    "trust": "Can I trust what AI tells me (mistakes, deepfakes, scams)?",
    "keepup": "AI moves too fast to keep up with.",
    "power": "Who controls AI: the giants, governments, the rules?",
    "safety": "Is AI safe for my kids, my health, society?",
}
HOOK_TYPES = {
    "stakes": "what changes for people, first (\"Your Gmail now writes back for you.\")",
    "surprise": "a first, a reversal or an irony (\"An AI refused its own company's order.\")",
    "number": "one striking number up front (\"OpenAI is now worth $1.25 trillion.\")",
    "conflict": "a fight between names everyone knows (\"The New York Times is suing Brave.\")",
    "you": "speaks to the viewer's own life (\"If you use Chrome, read this.\")",
    "gap": "says there is something to know without saying it yet (\"Nvidia's board just opened an investigation into its own CEO.\")",
}

# One call to action per Reel, by what the Reel is for (Instagram ranks sends and saves highly; Mosseri, Jan 2025)
CTA_SAVE = ["Save this for when you need it.", "Save this so you can find it later."]
CTA_SEND = ["Know someone who follows AI? Send this to them.", "Send this to the friend who keeps up with AI.",
            "Send this to your group chat's AI person."]
CTA_SEND_WORK = ["Send this to a colleague who uses AI at work.", "Send this to a friend in tech."]
CTA_SEND_SENSITIVE = ["Send this to someone who follows tech news."]


def _pick(options: list[str], key: str) -> str:
    return options[zlib.crc32(key.encode()) % len(options)]


def cta_for(card: dict, sensitive: bool = False) -> str:
    """The caption's one action. A practical take ("do") gets a save; a work or skills story a send to a colleague;
    a sensitive story a plain send; everything else a send to a friend. The opinion question stays as it is."""
    key = str(card.get("hook") or "")
    if sensitive:
        return _pick(CTA_SEND_SENSITIVE, key)
    if card.get("take_kind") == "do":
        return _pick(CTA_SAVE, key)
    if card.get("pain") in ("job", "skills", "tools"):
        return _pick(CTA_SEND_WORK, key)
    return _pick(CTA_SEND, key)


def producer_brief() -> str:
    """The part of the Reel desk's instructions that names the audience's worries and the hook formulas."""
    pains = "\n".join(f"  {k}: {v}" for k, v in PAINS.items())
    hooks = "\n".join(f"  {k}: {v}" for k, v in HOOK_TYPES.items())
    return (f"""- pain: which ONE of these viewer worries the story speaks to, or "none" (a story that touches none of
  them is rarely worth a Reel; score relatable 0 then):
{pains}
- hook_type: which formula your hook uses, one of:
{hooks}
""")


def clean_labels(c: dict) -> dict:
    """The card's pain and hook type, kept only when they are known values (they steer learning, so no free text)."""
    out = {}
    if str(c.get("pain") or "").strip().lower() in PAINS:
        out["pain"] = str(c["pain"]).strip().lower()
    if str(c.get("hook_type") or "").strip().lower() in HOOK_TYPES:
        out["hook_type"] = str(c["hook_type"]).strip().lower()
    return out
