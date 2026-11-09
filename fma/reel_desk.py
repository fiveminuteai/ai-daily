"""The Reel desk: a producer pass that decides which stories deserve a Reel and writes their script.

Until 2 Nov 2026 the blog writer also wrote the Reel lines, as an afterthought to each section. The result read like
headlines with the story taken out ("35 turbines operate without permits", when the story was that a judge let a
pollution lawsuit against Musk's xAI go ahead) and every day got three Reels, the third often weak (a hobbyist's AI
pocket watch). Pavan, 2 Nov: "you aren't choosing interesting topics for the reels".

So after the post is written and before it is fact-checked, a producer looks at each story on its own (one call per
story: a single call for all of them skipped stories when the reply ran long) and:
1. scores it on a fixed rubric for a phone viewer (stakes, surprise, names and conflict, a number, relatable), out
   of 10;
2. picks the angle and writes the Reel as a short story: hook, three beats, what it means for you, a question.

Facts come only from the section text, citations kept, so both fact-check layers check these lines exactly like any
other sentence of the post. Only stories that reach REEL_BAR become Reels (story_reel.card_stories), so a slow news
day gets fewer, better Reels instead of filler.
"""
from __future__ import annotations

import logging
import re

log = logging.getLogger(__name__)

REEL_BAR = 6              # out of 10: below this a story is not worth a viewer's 30 seconds
RUBRIC = {"stakes": 3, "surprise": 2, "names": 2, "number": 1, "relatable": 2}

PRODUCER_SYSTEM = """You are the senior producer of a short-video AI news show on Instagram. You have produced
hundreds of 30-second news Reels and you know what makes a phone viewer stop scrolling and watch to the end: real
stakes, a surprise, a famous name or a fight, one striking number, and a clear "what this means for you". You are also
a strict journalist: you never add a fact, number or name that is not in the material you are given. You reply with
one JSON object and nothing else."""

PRODUCER_RULES = """VIEWERS: working professionals aged 20 to 40, most in tech, who use AI tools but are not AI specialists.
They watch on their phones, often with the sound off, and decide in two seconds.

STEP 1. Score the story honestly with this rubric. Be harsh: most stories are not Reel material.
- stakes 0-3: real consequences for people, money, jobs, safety, health, privacy, the law (3 = many people affected
  or harmed, 0 = nothing changes for anyone)
- surprise 0-2: something the viewer would not have guessed: a first, a reversal, an irony, an AI refusing or misbehaving
- names 0-2: a name everyone knows (OpenAI, Google, Apple, Meta, Microsoft, Nvidia, Musk, a government) or a real
  conflict (a lawsuit, a ban, a fight between companies)
- number 0-1: one striking, concrete number in the text
- relatable 0-2: it could touch the viewer's own work, phone, money or safety
Low by nature: gadget previews and hobby builds, developer-tool repositories, model cards, routine rebrands and
renamings, opinion pieces with no event, papers with no plain-language result.

STEP 2. Write the Reel script as a story a friend would tell, not a headline:
- angle: one sentence, why a viewer should care (for the editor, not shown)
- hook: ONE full sentence with a verb, at most 14 words. Lead with the most surprising true thing, name WHO (the
  best-known name in the text, not a minor official) and the stakes. It must make sense to someone who has never heard
  of the story. No question, no hype words, no "you won't believe".
  Bad: "35 turbines operate without permits" (no who, no stakes).
  Bad: "Zero financial payoff from AI for non-tech firms" (a label, no verb).
  Good: "A judge says villagers can sue Acme over the smoke from its AI servers[S1]."
  Good: "One AI model refused to touch the patient. A second one went ahead[S1]."
- points: exactly three beats, each at most 18 words with one concrete detail. Beat 1: what happened, plainly.
  Beat 2: the twist, the number or the detail that raises the stakes. Beat 3: who is affected or what happens next.
- take: at most 22 words: what it means for the viewer. take_kind "do" if it is a practical step they can take,
  otherwise "read".
- ask: an opinion question for the comments, at most 10 words, stating no facts.
{AUDIENCE}- TONE (9 Nov 2026): plain and decent. On a story about someone's private life (an affair, a family, a death, a
  crime), say only what happened and why it matters to the company or the public: no wordplay, no "romance",
  no puns, nothing about the people's private feelings, and the ask is about the public question.
- cover: the Reel's thumbnail headline, 3 to 7 words, the one line that makes a scroller stop: the most surprising
  TRUE angle, in plain words, with its citation. A claim stays a claim ("Memo says ...", "Founder says ...").
  cover_hi: 1 to 3 words copied from the cover that carry the punch; they are lit up on the thumbnail.
  Good: "Microsoft's AI Frontiers team is over[S1]." with cover_hi "is over".
FACTS: use O
Y facts in the story's text below. Every sentence of hook, points and take ends with the citation
markers ([S1]) of the sentence its facts come from. Never add a number, name, date or claim that is not in the text.
Do not make the story bigger or closer to the viewer than the text does: no country, company, person or group
("Indian firms", "hundreds of companies") that the text does not name, and no rounded or invented numbers.
Keep the story's status and units (3 Nov 2026: "Apple unveils a robot" for a robot Apple only plans, and "billions
of articles" for "30 billion web pages"): a plan, report or leak is not a launch or an unveiling; pages are not
articles. A lawsuit's claims are accusations: write "sues X, saying it ..." or "accuses X of ...". No comparisons
("far more than ...") that the text does not make.
"""


def _rules() -> str:
    from .audience import producer_brief
    return PRODUCER_RULES.replace("{AUDIENCE}", producer_brief())


def market_note() -> str:
    """This week's most-watched AI Shorts on YouTube (fma/market.py), as hook ideas only: titles are other people's
    words and claims, never facts for us, and never copied."""
    try:
        import json
        from . import config
        m = json.loads((config.ROOT / "data" / "growth" / "market.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return ""
    titles = [f'- "{t["title"][:90]}" ({t["views"]:,} views, {t["region"]})' for t in (m.get("top") or [])[:8]]
    if not titles:
        return ""
    return ("\nWHAT AI SHORTS GOT WATCHED THIS WEEK (YouTube, " + m.get("week", "") + "). Use them only to see which "
            "worries and hook shapes pull viewers; never take a fact, number or wording from them:\n" + "\n".join(titles) + "\n")


def producer_prompt(section: dict, sources: list[dict], lessons: list[dict] | None = None) -> str:
    by_id = {s["id"]: s for s in sources}
    ids = sorted({i for p in section.get("paragraphs", []) for i in re.findall(r"S\d+", p)}, key=lambda x: int(x[1:]))
    outlets = "; ".join(dict.fromkeys(f"{by_id[i].get('publisher', '')}: {by_id[i].get('title', '')}"
                                      for i in ids if i in by_id))
    taught = "".join(f"- {x['lesson']} ({'; '.join(x.get('evidence', []))})\n" for x in lessons or [])
    if taught:        # from our own Instagram numbers (fma/learn.py), each checked against the data
        taught = "\nLESSONS FROM OUR OWN REEL RESULTS (follow them; they never override the FACTS rule):\n" + taught
    return (_rules() + taught + market_note() + '\nReply as {"score": {"stakes": 2, "surprise": 1, "names": 2, "number": 1, '
            '"relatable": 1}, "angle": "...", "hook": "...[S1].", "points": ["...[S1].", "...[S2].", "...[S1]."], '
            '"take": "...[S1].", "take_kind": "read", "ask": "...?", "cover": "...[S1].", "cover_hi": "...", "pain": "job", "hook_type": "stakes"}\n\n'
            f"STORY: {section.get('title', '')}\nReported by: {outlets[:400]}\nText:\n"
            + "\n".join(section.get("paragraphs", [])))


def total(score: dict) -> int:
    """Rubric total out of 10, each part clamped to its maximum."""
    out = 0
    for k, top in RUBRIC.items():
        try:
            out += max(0, min(top, int(float(score.get(k, 0)))))
        except (TypeError, ValueError):
            pass
    return out


def script(chain, section: dict, sources: list[dict], lessons: list[dict] | None = None,
           rejected: str = "") -> dict | None:
    """The producer's card for one story, with its rubric score ("reel", 0-10) and angle; None on any failure.
    A script with a line over its word limit is sent back once: the fact-check drops an over-long line, and a hook
    over 14 words loses the whole Reel."""
    from .write import normalise_card

    base = producer_prompt(section, sources, lessons) + rejected
    prompt = base
    for _try in range(2):
        try:
            x = chain.ask_json(PRODUCER_SYSTEM, prompt, temperature=0.4)
        except Exception as exc:  # noqa: BLE001
            log.warning("Reel desk failed on %r: %s", section.get("title"), exc)
            return None
        card = normalise_card(x) if isinstance(x, dict) else None
        if not card or not card.get("hook") or len(card.get("points") or []) < 2:
            return None
        card.update(hook=tidy(card["hook"]), points=[tidy(p) for p in card["points"]][:3], take=tidy(card.get("take")))
        long = [f"{plain_text(w)!r} ({len(plain_text(w).split())} words, limit {lim})"
                for w, lim in [(card["hook"], 14), *[(p, 18) for p in card["points"]], (card.get("take"), 22)]
                if w and len(plain_text(w).split()) > lim]
        if not long:
            score = total(x.get("score") if isinstance(x.get("score"), dict) else {})
            card.update(reel=score, interest=max(1, min(5, round(score / 2))), angle=str(x.get("angle") or "")[:300])
            return card
        prompt = (base + "\n\nYOUR LAST SCRIPT HAD LINES OVER THE WORD LIMIT. Rewrite "
                  "them shorter, keeping the facts and citations:\n" + "\n".join(long))
    log.warning("Reel desk script for %r still too long", section.get("title"))
    return None


def tidy(t: str | None) -> str | None:
    """'polluting Memphis.[S1].' -> 'polluting Memphis[S1].'"""
    return re.sub(r"[.!]\s*((?:\[S\d+\])+)\s*\.?$", r"\1.", t.strip()) if t else t


CHIEF_SYSTEM = """You are the editor-in-chief of a short-video AI news show. Each evening you choose which of the
day's scripted stories go out as Reels. You compare them side by side and you are blunt: a viewer gives a Reel two
seconds. You reply with one JSON object and nothing else."""


def chief_prompt(cards: list[tuple[int, dict]]) -> str:
    rows = [f"{n}. HOOK: {plain_text(c['hook'])}\n   WHY: {c.get('angle', '')}\n   BEATS: "
            + " / ".join(plain_text(p) for p in c.get("points", [])) for n, c in cards]
    return ("VIEWERS: working professionals in India aged 20 to 40, mostly in tech, scrolling on their phones.\n"
            "Score each script 0 to 10 for whether these viewers would stop, watch to the end and talk about it:\n"
            "9-10: everyone at the office would bring it up today (people harmed or at risk, a giant company in "
            "trouble or a fight, AI doing something startling or refusing to)\n"
            "7-8: a clear surprise or real stakes with a name viewers know\n"
            "5-6: interesting to people in the industry, little for anyone else\n"
            "0-4: previews, hobby projects, developer tools, routine company news\n"
            "Compare the scripts with each other: two stories should not get the same score unless they are equally "
            'strong.\nReply as {"scores": [{"n": 1, "score": 7, "why": "short reason"}]}\n\n' + "\n".join(rows))


def plain_text(s: str) -> str:
    return re.sub(r"\[S\d+\]", "", s or "").strip()


def produce(chain, draft: dict, sources: list[dict], rejected: list[str] | None = None) -> dict:
    """Replace each section's card with the producer's script, then let the editor-in-chief compare the scripts. The
    card's "reel" score (0-10) is the mean of the producer's rubric and the chief's comparison, and "desk" keeps both
    with the chief's reason, for the run log. A story the desk could not script keeps the writer's card without a
    score, so the Reel desk can improve a day but never cost one. On a retry, `rejected` holds the Reel lines the
    fact-check dropped last time, with its reasons, so the producer does not write them again."""
    if not draft.get("sections") or not chain:
        return draft
    from .learn import learned_settings
    learned = learned_settings()
    back = ("\n\nTHE FACT-CHECK REJECTED THESE REEL LINES LAST TIME. Do not repeat the error:\n"
            + "\n".join(f"- {x}" for x in rejected[:8])) if rejected else ""
    out = []
    for sec in draft["sections"]:
        card = script(chain, sec, sources, learned.get("lessons"), back)
        if card:          # a bounded lean learned from our results; frozen into the card so Reels never change later
            card["bonus"] = float(learned.get("category_bonus", {}).get(sec.get("category"), 0.0))
        out.append({**sec, "card": card} if card else sec)
    scripted = [(n, s["card"]) for n, s in enumerate(out, 1) if isinstance((s.get("card") or {}).get("reel"), int)]
    chief: dict[int, tuple[float, str]] = {}
    if len(scripted) > 1:
        try:
            reply = chain.ask_json(CHIEF_SYSTEM, chief_prompt(scripted), temperature=0.2)
            for x in reply.get("scores", []) if isinstance(reply, dict) else []:
                if isinstance(x, dict) and str(x.get("n", "")).isdigit():
                    chief[int(x["n"])] = (max(0.0, min(10.0, float(x.get("score", 0)))), str(x.get("why") or "")[:200])
        except Exception as exc:  # noqa: BLE001 - without the chief, the producer's rubric alone decides
            log.warning("editor-in-chief failed, using the producer's scores: %s", exc)
    for n, card in scripted:
        rubric = card["reel"]
        c_score, why = chief.get(n, (None, ""))
        card["desk"] = {"rubric": rubric, "chief": c_score, "why": why}
        if c_score is not None:
            card["reel"] = int(round((rubric + c_score) / 2))
            card["interest"] = max(1, min(5, round(card["reel"] / 2)))
    # the duo desk (5 Nov 2026): each story that will get a Reel is also written as a Spark-and-guest comedy act;
    # the strongest story always gets one, as card_stories always gives the best story a Reel
    from .duo_desk import write as write_duo
    ranked = sorted(scripted, key=lambda nc: -nc[1]["reel"])
    from . import config
    from .social_queue import reel_slots
    for k, (n, card) in enumerate(ranked[:len(reel_slots(config.site_config()))]):   # one duo per Reel slot
        if k == 0 or card["reel"] >= REEL_BAR:
            duo = write_duo(chain, out[n - 1], card)
            if duo:
                card["duo"] = duo
    return {**draft, "sections": out}
