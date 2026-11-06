"""The prompt playbook: every model step of Five Minute AI, written out from the code, so any model, a small local one
included, can be run on exactly the same instructions (6 Nov 2026, Pavan: "ensure whatever we are doing is given as
a prompt in detail so that even a low level model with limits can work and produce the same output").

    python -m fma.playbook            # writes docs/PLAYBOOK.md

The file is generated: edit the prompts in the code, then run this again. tests/test_playbook.py fails if the file is
out of date, so the playbook can never drift from what the pipeline really sends."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "PLAYBOOK.md"

INTRO = """# Five Minute AI: the prompt playbook

Generated from the code by `python -m fma.playbook`. Do not edit by hand: change the prompts in `fma/`, then run it
again (a test fails when this file is out of date).

## How the day works

Every model step below is small, has its rules written out in full, and has its answer checked by code. A step that
breaks a rule is sent back with the exact problems (up to the retries shown). Nothing a model writes is trusted on its
own: every fact goes through two fact-check layers, and any step that still fails falls back to something safe, so a
weaker model makes a plainer day, never a wrong one.

| # | Step | Model task | Checked by code | If it still fails |
|---|------|-----------|-----------------|-------------------|
| 1 | Editor | pick the day's stories for our readers | scores, categories | the ranker's own order |
| 2 | Writer | write each story section, then the dek, bullets and why it matters | words, citations, hype, length | retry with the gate's reasons, then a short edition, then skip |
| 3 | Reel desk | score each story for a Reel and write its card | word limits per line | the writer's own card |
| 4 | Editor-in-chief | compare the Reel scripts | score range | the producer's rubric alone |
| 5 | Duo desk, facts | the story as 4 plain Spark lines with citations | citations, plain words, "at least" kept, length | ordinary Reel |
| 6 | Duo desk, jokes | one guest reaction per Spark line | no numbers, names or facts; length | ordinary Reel |
| 7 | Comedy editor | punch up the guest lines, score the script | same rules; score 6/10 or more | ordinary Reel |
| 8 | Fact-check layer 1 | (code only) names, numbers, citations against the sources | | the sentence is dropped |
| 9 | Fact-check layer 2 | check each claim against its source text | quoted evidence must be in the source | the sentence is dropped |
| 10 | Analyst | turn our Reel numbers into lessons | each lesson checked against the data | no lessons that day |

## Backup plan (6 Nov 2026)

- Small style slips are fixed, not fatal: a stray "!" becomes a full stop; a headline that fails its check becomes
  the lead story's checked title.
- If every attempt fails only on length or "why it matters", the post goes out as a short edition (450+ words, every
  fact still checked twice, and the page says it is a short edition).
- The free cloud models have daily caps shared with the daily post. Off GitHub Actions they are switched off unless
  `FMA_ALLOW_PROD_KEYS=1`; experiments use the local model (Ollama).
- Providers are tried in order (`config/site.yaml`), each with retries and waits for passing outages; the daily
  workflow runs several times a morning and the last try raises an alert if there is still no post.
"""


def _block(title: str, what: str, system: str, user: str) -> str:
    return (f"\n## {title}\n\n{what}\n\n**System prompt**\n\n```text\n{system.strip()}\n```\n\n"
            f"**User prompt** (the parts in braces are filled in by the code)\n\n```text\n{user.strip()}\n```\n")


def build() -> str:
    from . import duo_desk, editor, learn, reel_desk, verify, write

    sample_section = {"title": "{story title}", "paragraphs": ["{the story's checked paragraphs, with [S1] citations}"]}
    sample_card = {"hook": "{the Reel hook}"}
    duo_sample = {"guest": "rex", "lines": [{"who": "spark", "text": "{Spark line 1}[S1]."},
                                            {"who": "guest", "text": "{guest reaction 1}"}]}
    parts = [INTRO]
    parts.append(_block("1. Editor: choose the stories", "Picks and scores the day's stories for our readers.",
                        editor.EDITOR_SYSTEM, "{the ranked candidate stories and the audience, as built by "
                        "fma.editor.editor_prompt}"))
    parts.append(_block("2. Writer: the post", "Writes each section from its sources, then the frame.",
                        write.SYSTEM, write.RULES))
    parts.append(_block("3. Reel desk: score and script each story", "One call per story.",
                        reel_desk.PRODUCER_SYSTEM, reel_desk.producer_prompt(sample_section, [])))
    parts.append(_block("4. Editor-in-chief: compare the Reels", "One call for the day.", reel_desk.CHIEF_SYSTEM,
                        "{the day's Reel scripts, as built by fma.reel_desk.chief_prompt}"))
    parts.append(_block("5. Duo desk, step 1: Spark's facts",
                        "The guest is chosen in code: Rex when the story mentions power, fuel, emissions, climate or "
                        "water two or more times, otherwise Doubt.",
                        duo_desk.FACTS_SYSTEM, duo_desk.FACTS_TASK + "\n\nSTORY: {story title}\nStory text:\n{paragraphs}"))
    for guest in duo_desk.GUESTS:
        name = guest.capitalize()
        pairs = "\n".join(f'Spark: "{f}"\n{name}: "{j}"' for f, j in duo_desk.JOKE_PAIRS[guest])
        parts.append(_block(f"6. Duo desk, step 2: {name}'s reactions", "One call per story.", duo_desk.JOKES_SYSTEM,
                            duo_desk.JOKES_TASK.format(name=name, name_up=name.upper(), persona=duo_desk.PERSONA[guest],
                                                       n="{n}", pairs=pairs, lines="{Spark's numbered lines}")))
    parts.append(_block("7. Comedy editor", f"Rewrites only the guest lines; below {duo_desk.EDITOR_BAR}/10 the story "
                        "keeps its ordinary Reel.", duo_desk.EDITOR_SYSTEM, duo_desk.editor_prompt(duo_sample, sample_section)))
    parts.append("\n## Step 3 of the duo (code, no model)\n\nSpark, guest, Spark, guest; a comic pause before the last "
                 "two punchlines; then the card's question, the outro and the fixed sign-off:\n\n" + "\n".join(
                     f"- {who}: {text}" for who, text, *_ in duo_desk.SIGN_OFF) + "\n")
    parts.append(_block("9. Fact-check layer 2", "Every claim, with the text of the source it cites.",
                        verify.LLM_CHECK_SYSTEM, "{numbered sentences with their sources, as built by fma.verify.llm_check}"))
    parts.append(_block("10. Analyst: lessons from our numbers", "Weekly, from our own Instagram results.",
                        learn.LESSON_SYSTEM, "{our Reel results table, as built by fma.learn.lesson_prompt}"))
    del sample_card
    return "".join(parts)


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(build(), encoding="utf-8")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
