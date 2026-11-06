"""The duo desk (5 Nov 2026): writes each Reel story as a short comedy double act. Spark, the presenter, tells the
story; a guest reacts. Pavan's notes from the samples, all built in:
- plain everyday words a 12-year-old gets on the first hear (no "allegedly", "exempt", legal or finance jargon);
- a comic angle in every Reel: setup then punchline, a pause ("beat") before the big laughs, visual gags;
- 40-45 s at most: extra lines only when the story has more worth saying;
- the fixed sign-off: "Five Minute AI." / guest: "Still not taking your job." / Spark, sweating: "Yet."

Honesty rules, the same as every line we publish: every fact is Spark's, with its citation, and goes through both
fact-check layers like a card line (verify.py); the guest only jokes, reacts or asks, and its lines may hold no
numbers and no names, so it can state no facts. A duo that fails any check is dropped and the story keeps its
ordinary Reel, so the desk can improve a day but never cost one."""
from __future__ import annotations

import logging
import re

log = logging.getLogger(__name__)

GUESTS = ("doubt", "rex")
FX = {"beat", "confetti", "drop", "sweat"}
WORD_BUDGET = (50, 105)    # words in the story lines (the question, outro and sign-off come on top): ~40-45 s
SIGN_OFF = [("spark", "Five Minute AI.", "card"), ("guest", "Still not taking your job.", "card"),
            ("spark", "Yet.", "card", "beat", "sweat")]
HARD_WORDS = {"allegedly", "alleged", "exempt", "exemption", "subtle", "combustion", "litigation", "plaintiff",
              "plaintiffs", "defendant", "statutory", "moratorium", "moratoria", "jurisdiction", "pursuant",
              "aforementioned", "notwithstanding", "fiduciary", "amortise", "amortize", "ebitda", "commitments",
              "infrastructure", "leverage", "paradigm", "synergy", "operating", "revenue", "motion", "dismiss",
              "dismissal", "standing", "affirmed", "admins", "enforce", "enforcement", "regulatory", "compliance",
              "provisions", "facility", "facilities", "disable", "utilise", "utilize", "k-12",
              "proceed", "metric", "metrics", "margins", "quarterly", "filing"}
# Words people know but that read as jargon in a 40-second Reel; "sued", "court", "judge", "said no" do the same job.
# 5 Nov 2026: the first real-model run wrote "denied xAI's motion to dismiss" and "the NAACP has standing".
SWAPS = [(r"\boperating loss\b", "loss"), (r"\brevenues?\b", "sales"),
         (r"\badmins\b", "staff"), (r"\badministrators\b", "staff"), (r"\butili[sz]e\b", "use"),
         (r"\bfacilit(y|ies)\b", "site"), (r"\bquarterly\b", "this quarter's")]


def simplify(text: str) -> str:
    """Swap the jargon that has one plain, exact equivalent; anything else goes back to the writer."""
    for pat, rep in SWAPS:
        text = re.sub(pat, lambda m: rep[0].upper() + rep[1:] if m.group(0)[0].isupper() else rep, text, flags=re.I)
    return text


LIMIT_RE = re.compile(r"\b(at least|more than|over|up to|as many as|nearly|about|around|almost)\s+\$?(\d[\d,.]*)", re.I)


def ceiling_problems(lines: list[dict], source_text: str) -> list[str]:
    """A number the source gives with a limit ("at least 35") must keep it: "35 turbines" claims more than we know
    (5 Nov 2026: the writer dropped "at least" and both fact-check layers let it through)."""
    out = []
    limited = {m.group(2).rstrip(".,"): m.group(1).lower() for m in LIMIT_RE.finditer(source_text)}
    for k, ln in enumerate(lines):
        if ln.get("who") != "spark":
            continue
        t = plain(ln.get("text", ""))
        for num, qual in limited.items():
            for m in re.finditer(r"(?<![\d,.])\$?" + re.escape(num) + r"(?![\d,])", t):
                before = t[:m.start()].lower().rstrip()
                if not re.search(r"(at least|more than|over|up to|as many as|nearly|about|around|almost)$", before):
                    out.append(f"line {k + 1}: the story says \"{qual} {num}\"; keep \"{qual}\"")
    return out


GUEST_NAMES_OK = {"Spark", "Rex", "Doubt", "AI", "I", "I'm", "I've", "I'd", "I'll", "OK", "Okay"}

DUO_SYSTEM = """You write a 40-second comedy news double act for Instagram Reels, for an AI news show. You are as
funny as a good sitcom writer and as strict as a newspaper fact-checker: you never add a fact, number or name that
is not in the story text. You reply with one JSON object and nothing else."""

DUO_RULES = """THE CAST
- Spark: the presenter. Bright, quick, warm. Spark tells the story and carries EVERY fact.
- The guest reacts (chosen for you, below):
  - "rex": a grumpy old T. rex in reading glasses, for power, fuel, emissions and climate stories. Jokes about
    being old, a fossil, extinct.
  - "doubt": a dry, sceptical blue box with half-closed eyes. Unimpressed, deadpan, jokes about being a box.

THE RULES (all of them matter)
1. FACTS: every Spark line states only what the story text says, and ends with its citation, like "...[S1]."
   Never add a number, name, date or claim that is not in the text. No myths (fossil fuels are NOT "made of dinosaurs").
   Keep the text's limits and doubts: "at least 35", "up to", "says", "is accused of". A claim in a lawsuit is a
   claim, not a fact: say "is accused of" or "the group says". Never copy the headline: say the story simply.
2. GUEST LINES: jokes, reactions and questions only. NO numbers (no digits, no number words), NO names of people,
   companies, places or products. The guest never states a fact. No citations on guest lines.
3. PLAIN WORDS: everyday words a 12-year-old understands on first hearing. Say "sales" not "revenue", "losing
   money" not "operating loss", "permission" not "permits" if simpler. No legal or finance jargon, no "allegedly",
   no "exempt". Short sentences.
4. COMEDY: the guest's lines are punchlines. Setup -> punchline. Callbacks are great. At least three real laughs.
   Mark a comic pause before a big punchline with "fx": ["beat"]. Optional gags: "confetti" on a celebration line,
   then "drop" on the letdown line right after (the confetti falls flat). Use gags only when the story fits.
5. SHAPE: open with Spark's hook (the most surprising fact, first). Then alternate Spark, guest, Spark, guest.
   6 to 10 lines. Spark's story lines plus the guest's lines together: 60 to 90 words. End on a guest punchline.
   Do NOT write the closing question or a sign-off: they are added for you.
6. READ IT ALOUD: each guest joke must make sense on its own and follow from the line before it. If a friend
   would not smile, or would say "what?", rewrite it. Comparisons must point the right way ("I've seen glaciers
   move faster", never "slower").
7. TONE: tease the situation, never punch down at people, groups, accents or victims. If the story is about harm
   to real people (deaths, abuse, illness), keep the guest gentle and the jokes off the victims.

Reply as {"guest": "rex", "lines": [{"who": "spark", "text": "...[S1]."}, {"who": "guest", "text": "...",
"fx": ["beat"]}, ...]}"""


REX_TOPICS = re.compile(r"\b(power|electricity|electric|energy|fuel|gas|oil|coal|nuclear|emissions?|pollut\w*|"
                        r"climate|carbon|turbines?|grid|water|megawatts?|gigawatts?|solar|wind farm)\b", re.I)


def pick_guest(section: dict) -> str:
    """Rex for power, fuel, emissions, climate and water stories (two or more mentions); Doubt for the rest."""
    text = section.get("title", "") + " " + " ".join(section.get("paragraphs", []))
    return "rex" if len(REX_TOPICS.findall(text)) >= 2 else "doubt"


# The two scripts Pavan approved (5 Nov 2026, Rex v6 and Doubt v6): the writer copies their rhythm, not their words.
EXAMPLES = {
    "rex": [("spark", "xAI is accused of running at least 35 turbines at its Memphis data centre without the "
                      "permission it needed[S1]."),
            ("guest", "Turbines? The ones that burn fuel? I'm a fossil. I take that personally."),
            ("spark", "A group says it broke clean air rules[S1]."),
            ("guest", "Clean air. I remember clean air.", "beat"),
            ("spark", "xAI said the turbines can move, so the rules don't apply[S1]."),
            ("guest", "They can move? I've seen glaciers move faster."),
            ("spark", "The judge said no. The government asked to throw the case out too. Also no[S1][S2]."),
            ("guest", "Even I did my paperwork. And I'm extinct.", "beat")],
    "doubt": [("spark", "Anthropic now spends 58 cents of every dollar it earns on computing power, up from 48 "
                        "cents[S1]."),
              ("guest", "Wait. All that? Just on computers?"),
              ("spark", "Its sales hit $17 billion this quarter, up from $11.5 billion[S1]."),
              ("guest", "We're rich! Party!", "confetti"),
              ("spark", "But it is also losing more money than before[S1].", "beat", "drop"),
              ("guest", "Cancel the party."),
              ("spark", "Half of its computing bill went on short deals, which cost a lot more[S1]."),
              ("guest", "So, like booking a taxi at midnight. In the rain."),
              ("spark", "Pretty much. Demand grew so fast, it grabbed whatever it could get[S1]."),
              ("guest", "Even I plan ahead. And I am a box.", "beat")],
}


def example(guest: str) -> str:
    rows = []
    for who, text, *fx in EXAMPLES[guest]:
        rows.append({"who": who, "text": text, **({"fx": fx} if fx else {})})
    import json
    return json.dumps({"guest": guest, "lines": rows}, ensure_ascii=False)


def duo_prompt(section: dict, card: dict, guest: str) -> str:
    return (DUO_RULES + f"\n\nTHE GUEST FOR THIS STORY IS \"{guest}\" (already chosen; keep it).\n"
            "AN APPROVED SCRIPT FOR THIS GUEST (a different story; copy its rhythm, plain words and kind of joke, never "
            "its facts):\n" + example(guest) +
            "\n\nWHAT MAKES IT WORK: every guest line is a reaction a real person would say out loud, short and "
            "specific to the fact just said, often turning it on the guest itself (the fossil, the box). The joke "
            "lands on the situation, never on people. Spark's lines are simple and clear, one fact each.\n"
            f"\nSTORY: {section.get('title', '')}\nThe Reel's hook: {card.get('hook', '')}\n"
            "Text:\n" + "\n".join(section.get("paragraphs", [])))


def plain(s: str) -> str:
    return re.sub(r"\[S\d+\]", "", s or "").strip()


NUMBER_WORDS = re.compile(r"\b(zero|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|twenty|thirty|"
                          r"forty|fifty|hundred|thousand|million|billion|trillion|percent|half|dozen)\b", re.I)


def problems(duo: dict) -> list[str]:
    """Everything wrong with a duo script, in words the writer can act on. Empty means it passes the desk's checks
    (the fact-check layers still check Spark's lines afterwards)."""
    out = []
    if duo.get("guest") not in GUESTS:
        out.append(f"guest must be one of {GUESTS}")
    lines = duo.get("lines") or []
    if not 6 <= len(lines) <= 10:
        out.append(f"{len(lines)} lines; write 6 to 10")
    words = 0
    for k, ln in enumerate(lines):
        who, text = ln.get("who"), str(ln.get("text") or "")
        words += len(plain(text).split())
        if who not in ("spark", "guest"):
            out.append(f"line {k + 1}: who must be spark or guest")
            continue
        if set(ln.get("fx") or []) - FX:
            out.append(f"line {k + 1}: unknown fx {sorted(set(ln.get('fx') or []) - FX)}")
        hard = sorted({w for w in re.findall(r"[a-z0-9]+(?:[-‑][a-z0-9]+)*", plain(text).lower())
                       if w.replace("‑", "-") in HARD_WORDS})
        if hard:
            out.append(f"line {k + 1}: hard words {hard}; use plain everyday words")
        if who == "spark" and not re.search(r"\[S\d+\]", text):
            out.append(f"line {k + 1}: a Spark line needs its citation like [S1]")
        if who == "guest":
            if re.search(r"\d", text) or NUMBER_WORDS.search(text):
                out.append(f"line {k + 1}: the guest may not say numbers")
            if re.search(r"\[S\d+\]", text):
                out.append(f"line {k + 1}: guest lines carry no citations (the guest states no facts)")
            caps = [w for i, w in enumerate(re.findall(r"[A-Za-z']+", text)) if w[0].isupper()
                    and w not in GUEST_NAMES_OK and not re.search(r"(^|[.!?]\s+|\"|“)" + re.escape(w), text)]
            if caps:
                out.append(f"line {k + 1}: the guest may not name anyone or anything ({', '.join(caps)})")
    if lines and lines[0].get("who") != "spark":
        out.append("line 1 must be Spark's hook")
    if lines and lines[-1].get("who") != "guest":
        out.append("end on a guest punchline")
    if not WORD_BUDGET[0] <= words <= WORD_BUDGET[1]:
        out.append(f"{words} words; write {WORD_BUDGET[0]} to {WORD_BUDGET[1]}")
    return out


# ---------------------------------------------------------------- the writing, in small steps
# 6 Nov 2026, Pavan: "even a low level model with limits [should] produce the same output". A small model cannot
# write a whole comedy script in one go, but it does small, well-defined tasks with worked examples well. So:
#   step 1 (facts): the story as 3-4 short, plain Spark lines with citations;
#   step 2 (jokes): one guest reaction per Spark line, from approved fact -> joke pairs;
#   step 3 (code): alternate the lines, add the pauses, the question and the sign-off.
# Every step's output is checked in code and sent back once with the exact problems, as before.

FACTS_SYSTEM = """You turn a news story into short, plain lines for a video presenter. You never add a fact, number
or name that is not in the story text. You reply with one JSON object and nothing else."""

FACTS_TASK = """TASK: write the story as 4 short lines for Spark, the presenter, in the order a friend would tell it.

RULES (check every line against each rule before you reply)
1. Line 1 is the most surprising fact. Lines 2-4 add the next most interesting facts, one fact per line.
2. Each line: 8 to 18 words. Plain everyday words a 12-year-old understands. Short sentences.
3. Only facts from the story text. Never add a number, name or date that is not there.
4. Keep every limit and doubt the text has: "at least 35" stays "at least 35"; "says", "claims", "is accused of"
   stay. A claim in a lawsuit is not a proven fact.
5. End every line with its citation from the text, like [S1] or [S1][S2].
6. Swap jargon for plain words: "sales" not "revenue", "losing money" not "operating loss", "the court said no" not
   "denied the motion to dismiss", "school staff" not "admins". Never use: allegedly, exempt, plaintiffs, standing.

EXAMPLE
Story text: "A federal judge denied xAI's motion to dismiss a lawsuit filed by the NAACP that alleges the company
operated at least 35 combustion turbines at its Colossus data centre in Memphis without required permits[S1]. xAI
argued the turbines were mobile and thus exempt, but the judge rejected both defenses[S1][S2]."
Reply: {"lines": ["xAI is accused of running at least 35 turbines at its Memphis data centre without the permission it needed[S1].",
"The NAACP took xAI to court over it[S1].",
"xAI said the turbines can move, so the rules don't apply[S1][S2].",
"The judge said no, and the case goes ahead[S1][S2]."]}

Reply as {"lines": ["...[S1].", "...[S1].", "...[S2].", "...[S1]."]}"""

JOKES_SYSTEM = """You write the punchlines for a comedy news double act. You are funny, quick and kind. You reply
with one JSON object and nothing else."""

PERSONA = {
    "rex": "Rex, a grumpy old T. rex in reading glasses. Rex is old, a fossil, extinct, slow, tired, and takes "
           "anything about burning fuel personally.",
    "doubt": "Doubt, a dry, sceptical blue box with half-closed eyes. Doubt is deadpan, unimpressed, a box (no "
             "hands, no legs, lives on a shelf), and always sees the catch.",
}
# Approved fact -> joke pairs (5 Nov 2026 samples Pavan liked, plus more in the same voice). The model copies the
# kind of joke, never the words.
JOKE_PAIRS = {
    "rex": [("xAI is accused of running at least 35 turbines without the permission it needed.",
             "Turbines? The ones that burn fuel? I'm a fossil. I take that personally."),
            ("A group says it broke clean air rules.", "Clean air. I remember clean air."),
            ("xAI said the turbines can move, so the rules don't apply.", "They can move? I've seen glaciers move faster."),
            ("The judge said no, and the case goes ahead.", "Even I did my paperwork. And I'm extinct."),
            ("Data centres now use as much power as a small country.", "A small country? I used to be a small country."),
            ("The company says the new chip uses less energy.", "Less energy. Finally, something my age."),
            ("Several states are thinking about pausing new data centres.", "Pausing? I paused once. It did not go well.")],
    "doubt": [("Anthropic now spends 58 cents of every dollar it earns on computing power.", "Wait. All that? Just on computers?"),
              ("Its sales hit $17 billion this quarter.", "We're rich! Party!"),
              ("But it is also losing more money than before.", "Cancel the party."),
              ("Half of its computing bill went on short deals, which cost a lot more.",
               "So, like booking a taxi at midnight. In the rain."),
              ("Demand grew so fast, it grabbed whatever it could get.", "Even I plan ahead. And I am a box."),
              ("Google says schools that turn off its AI will also lose Search.", "So it's AI or nothing. Very relaxed."),
              ("The app can now read your bank statements.", "Great. Now my bank knows I talk to a box."),
              ("The company says the feature is safe.", "They always say that. Right before the sequel.")],
}

JOKES_TASK = """TASK: Spark, the presenter, will say the numbered lines below. After each one, {name} reacts with one
short line. Write those reactions.

WHO IS SPEAKING: {persona}

RULES (check every reaction against each rule before you reply)
1. One reaction per numbered line, in the same order. Exactly {n} reactions.
2. Each reaction: 3 to 12 words, something a real person would say out loud, reacting to THAT line.
3. Make it funny: surprise, sarcasm, or turn it back on {name} (see the examples). If a friend would say "what?",
   rewrite it. Comparisons must point the right way ("move faster", never "slower").
4. NO numbers or number words, NO names of people, companies, places or products, NO new facts. The reaction only
   reacts.
5. Never joke about victims, illness, death, groups of people or accents.

EXAMPLES OF {name_up}'S REACTIONS (copy the kind of joke, never the words)
{pairs}

SPARK'S LINES
{lines}

Reply as {{"reactions": ["...", "..."]}}"""


def _ask(chain, system: str, prompt: str, temperature: float) -> dict | None:
    try:
        x = chain.ask_json(system, prompt, temperature=temperature, careful=True)
    except Exception as exc:  # noqa: BLE001
        log.warning("duo desk call failed: %s", exc)
        return None
    return x if isinstance(x, dict) else None


def facts_step(chain, section: dict) -> list[str] | None:
    """Step 1: the story as 3-4 plain Spark lines with citations, checked in code (citations, hard words, length,
    limits like "at least"), sent back once with the problems."""
    source = " ".join(section.get("paragraphs", []))
    base = FACTS_TASK + f"\n\nSTORY: {section.get('title', '')}\nStory text:\n" + "\n".join(section.get("paragraphs", []))
    prompt = base
    for _try in range(3):
        x = _ask(chain, FACTS_SYSTEM, prompt, 0.3)
        lines = [simplify(str(t).strip()) for t in (x or {}).get("lines") or [] if str(t).strip()][:4]
        bad = []
        if len(lines) < 3:
            bad.append(f"write 4 lines, not {len(lines)}")
        for k, t in enumerate(lines):
            words = len(plain(t).split())
            if not 6 <= words <= 20:
                bad.append(f"line {k + 1} has {words} words; write 8 to 18")
            if not re.search(r"\[S\d+\]", t):
                bad.append(f"line {k + 1} needs its citation like [S1]")
            hard = sorted({w for w in re.findall(r"[a-z0-9]+(?:[-‑][a-z0-9]+)*", plain(t).lower())
                           if w.replace("‑", "-") in HARD_WORDS})
            if hard:
                bad.append(f"line {k + 1}: replace {hard} with plain everyday words")
        bad += ceiling_problems([{"who": "spark", "text": t} for t in lines], source)
        if not bad:
            return lines
        prompt = base + "\n\nYOUR LAST REPLY BROKE THESE RULES. Fix every one:\n" + "\n".join(f"- {b}" for b in bad)
    log.warning("duo facts step for %r failed: %s", section.get("title"), "; ".join(bad))
    return None


def jokes_step(chain, guest: str, lines: list[str]) -> list[str] | None:
    """Step 2: one reaction per Spark line, from the guest's approved fact -> joke pairs; checked in code (no numbers,
    names or citations, length), sent back once."""
    name = guest.capitalize()
    pairs = "\n".join(f'Spark: "{f}"\n{name}: "{j}"' for f, j in JOKE_PAIRS[guest])
    base = JOKES_TASK.format(name=name, name_up=name.upper(), persona=PERSONA[guest], n=len(lines), pairs=pairs,
                             lines="\n".join(f"{k + 1}. {plain(t)}" for k, t in enumerate(lines)))
    prompt = base
    for _try in range(3):
        x = _ask(chain, JOKES_SYSTEM, prompt, 0.8)
        jokes = [simplify(str(t).strip().strip('"')) for t in (x or {}).get("reactions") or [] if str(t).strip()]
        trial = {"guest": guest, "lines": [ln for f, j in zip(lines, jokes)
                                           for ln in ({"who": "spark", "text": f}, {"who": "guest", "text": j})]}
        bad = [] if len(jokes) == len(lines) else [f"write exactly {len(lines)} reactions, not {len(jokes)}"]
        bad += [b for b in problems(trial) if "guest" in b or "line " in b and not b.endswith("citation like [S1]")]
        bad += [f"reaction {k + 1} has {len(j.split())} words; write 3 to 12" for k, j in enumerate(jokes)
                if not 2 <= len(j.split()) <= 14]
        bad = [b for b in bad if "words; write 50" not in b and "lines; write 6" not in b]
        if not bad:
            return jokes
        prompt = base + "\n\nYOUR LAST REPLY BROKE THESE RULES. Fix every one:\n" + "\n".join(f"- {b}" for b in bad)
    log.warning("duo jokes step failed: %s", "; ".join(bad))
    return None


def assemble(guest: str, lines: list[str], jokes: list[str]) -> dict:
    """Step 3, in code: Spark, guest, Spark, guest...; a comic pause before the last two punchlines."""
    out = []
    for k, (f, j) in enumerate(zip(lines, jokes)):
        out.append({"who": "spark", "text": f})
        out.append({"who": "guest", "text": j, **({"fx": ["beat"]} if k >= len(lines) - 2 else {})})
    return {"guest": guest, "lines": out}


def write(chain, section: dict, card: dict) -> dict | None:
    """The duo script for one story, or None: facts, then jokes, then assembly; the whole script must pass
    problems() and the comedy editor's bar (punch_up)."""
    guest = pick_guest(section)
    lines = facts_step(chain, section)
    if not lines:
        return None
    jokes = jokes_step(chain, guest, lines)
    if not jokes:
        return None
    duo = assemble(guest, lines, jokes)
    bad = problems(duo) + ceiling_problems(duo["lines"], " ".join(section.get("paragraphs", [])))
    if bad:
        log.warning("duo script for %r failed the final check: %s", section.get("title"), "; ".join(bad))
        return None
    return punch_up(chain, duo, section)


def script(card: dict, outro: str) -> tuple[str, list[tuple]]:
    """The duo as duo_reel takes it: (guest, [(who, text, *tags)]), with the card's question, the outro and the
    sign-off added. Citations stay in the text; the Reel strips them for speech and captions."""
    duo = card["duo"]
    guest = duo["guest"]
    lines = [(guest if ln["who"] == "guest" else "spark", ln["text"], *ln.get("fx", [])) for ln in duo["lines"]]
    close = ((card.get("ask") or "").strip() + " " + outro).strip()
    lines.append(("spark", close))
    lines += [tuple(guest if x == "guest" else x for x in s[:1]) + s[1:] for s in SIGN_OFF]
    return guest, lines


EDITOR_SYSTEM = """You are the head comedy writer on a short-video news show. You punch up jokes and you are honest
about whether they are funny. You reply with one JSON object and nothing else."""


def editor_prompt(duo: dict, section: dict) -> str:
    rows = "\n".join(f"{k + 1}. {('SPARK' if ln['who'] == 'spark' else duo['guest'].upper())}: {plain(ln['text'])}"
                     for k, ln in enumerate(duo["lines"]))
    persona = ("a grumpy old T. rex in reading glasses: jokes about being old, a fossil, extinct" if duo["guest"] == "rex"
               else "a dry, sceptical blue box: deadpan, unimpressed, jokes about being a box")
    return f"""A 40-second news double act. Spark tells the story (those lines are fixed: they are fact-checked).
The guest is {persona}.

{rows}

YOUR JOB
1. Rewrite the GUEST lines only, to make each one genuinely funny: a short reaction a real person would say out
   loud, following from Spark's line just before it, often turned back on the guest. Keep the same number of guest
   lines, in the same places. Plain everyday words. NO numbers, NO names of people, companies, places or products,
   NO new facts. Never punch down at people. Comparisons must point the right way. A line that is already funny,
   keep it.
2. Then score the WHOLE script, honestly, 1 to 10: would a 25-year-old scrolling Instagram laugh at least twice?
   (5 = mildly amusing, 7 = good, 9 = would share it.) Approved example for scale, scored 8: "They can move? I've
   seen glaciers move faster." / "Even I did my paperwork. And I'm extinct."

Reply as {{"guest_lines": ["...", "..."], "score": 7, "why": "one sentence"}}"""


EDITOR_BAR = 6     # out of 10: below this the story keeps its ordinary Reel


def punch_up(chain, duo: dict, section: dict) -> dict | None:
    """The comedy editor's pass: rewrite the guest's lines and score the script. Returns the duo with the better
    guest lines and the editor's score, or None when the script is still not funny enough (under EDITOR_BAR)."""
    try:
        x = chain.ask_json(EDITOR_SYSTEM, editor_prompt(duo, section), temperature=0.8, careful=True)
    except Exception as exc:  # noqa: BLE001 - without the editor the writer's own script is not trusted to be funny
        log.warning("comedy editor failed on %r: %s", section.get("title"), exc)
        return None
    if not isinstance(x, dict):
        return None
    new = [str(t).strip() for t in x.get("guest_lines") or [] if str(t).strip()]
    slots = [k for k, ln in enumerate(duo["lines"]) if ln["who"] == "guest"]
    out = duo
    if len(new) == len(slots):
        trial = {**duo, "lines": [dict(ln) for ln in duo["lines"]]}
        for k, t in zip(slots, new):
            trial["lines"][k]["text"] = simplify(t)
        if not problems(trial):           # the editor's lines must pass every rule the writer's did
            out = trial
    try:
        score = int(round(float(x.get("score", 0))))
    except (TypeError, ValueError):
        score = 0
    log.info("comedy editor scored %r %d/10: %s", section.get("title"), score, str(x.get("why") or "")[:160])
    if score < EDITOR_BAR:
        return None
    return {**out, "laughs": score, "laughs_why": str(x.get("why") or "")[:200]}
