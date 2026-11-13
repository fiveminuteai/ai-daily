"""Pilot Reels (13 Nov 2026): three samples in the proposed style, rendered locally from the 12 Nov post.
Nothing here touches the live flow: no post, queue or site file is written. Usage: pilot.py check | render OUT_DIR"""
import json
import sys
from pathlib import Path

from fma import config
from fma.duo_desk import joke_problems, plain, script as duo_script
from fma.verify import Verifier
from fma.voice import OUTRO

S = lambda t: {"who": "spark", "text": t}                         # noqa: E731
C = lambda t: {"who": "spark", "text": t, "kind": "comeback"}     # noqa: E731
G = lambda t, beat=False: {"who": "guest", "text": t, **({"fx": ["beat"]} if beat else {})}   # noqa: E731

PILOTS = {
    "A-united-wide-appeal": {"section": 2, "ask": "Would you let an AI book your flights?",
                             "card": "AI can't book United flights", "lines": [
        S("Your AI can't book United flights anymore[S5]."),
        G("So I still have to click things. Tragic."),
        S("United says giving an AI your card or login could lead to purchases you never meant[S6]."),
        G("My card does that without any help."),
        C("That one's on you, Doubt."),
        G("Fair. Harsh, but fair.", True),
        S("One more reason: only a human can confirm a bag has no explosives[S6]."),
        G("Finally, a job I'm overqualified for. I'm a box.", True)]},
    "D-hook-loop": {"section": 2, "ask": "Would you let an AI book your flights?",
                    "card": "AI can't book United flights", "lines": [      # hook, question, rehook, question, answer last
        S("Your AI can't book United flights anymore[S5]."),
        G("Why? Did it break something?"),
        C("Not yet. Stay for the reason."),
        S("First, United points to Meta's Muse leaking a user's address online[S6]."),
        G("Leaking addresses. Bold career move."),
        C("And the real rule is stranger, Doubt."),
        S("Only a human can confirm a bag has no explosives[S6]."),
        G("Finally, a rule I can't break. I'm a box.", True)]},
    "B-chatgpt-new-hook": {"section": 0, "ask": "Would you trust a shop's own AI agent?",
                           "card": "ChatGPT gets business listings", "lines": [
        S("ChatGPT is getting business listings, like Google's[S1]."),
        G("Great. Now the shops can find me too."),
        S("Companies can verify their profile and run an agent that answers your product questions[S1]."),
        G("A robot salesman. It can't even shake hands."),
        C("You don't have hands either, Doubt."),
        G("Which is why I never buy anything.", True),
        S("OpenAI tried a checkout cart inside ChatGPT before, and retired it in March[S1]."),
        G("So even the cart got abandoned.", True)]},
    "C-myth-or-fact": {"section": 3, "ask": "Do you pay for an AI model today?",
                       "card": "Smartest AI = priciest?", "badge": "MYTH OR FACT?", "lines": [
        G("The smartest AI is always the priciest."),
        C("Not this week, Doubt."),
        S("Google's strongest model yet, Gemini 4 Carbon, is out[S7]."),
        S("Google says it costs over two times less per task than the next best outside model[S7]."),
        G("Smarter and cheaper. That never happens to me."),
        S("Google also says it ranks first on three benchmarks run by other companies[S7]."),
        G("Top of the class and on sale. Suspicious.", True),
        S("So that myth is busted, at least by Google's own numbers[S7]."),
        G("I'll believe it when my bill agrees.", True)]},
}


def load():
    post = json.loads((config.ROOT / "content/posts/2026-11-12.json").read_text(encoding="utf-8"))
    sources = json.loads((config.ROOT / "data/sources/2026-11-12.json").read_text(encoding="utf-8"))
    return post, sources


def check() -> bool:
    post, sources = load()
    v = Verifier(sources)
    ok = True
    for name, p in PILOTS.items():
        words = sum(len(plain(ln["text"]).split()) for ln in p["lines"])
        print(f"== {name}: {len(p['lines'])} lines, {words} words")
        for ln in p["lines"]:
            if ln["who"] == "guest":
                bad = joke_problems(ln["text"])
                if any(ch.isdigit() for ch in ln["text"]):
                    bad.append("guest says a number")
            elif ln.get("kind") == "comeback":
                bad = joke_problems(ln["text"])
            else:
                n = len(plain(ln["text"]).split())
                bad = [] if v.sentence(ln["text"], "pilot", []) else list(v.log[-1]["problems"])
                if n > 16:
                    bad.append(f"{n} words, over 16")
            if bad:
                ok = False
                print("   PROBLEM", ln["text"], "->", bad)
    return ok


def render(out_dir: Path) -> None:
    from fma.duo_reel import duo_reel
    post, _ = load()
    site = config.site_config()
    out_dir.mkdir(parents=True, exist_ok=True)
    only = sys.argv[3] if len(sys.argv) > 3 else ""
    for k, (name, p) in enumerate(PILOTS.items()):
        if only and not name.startswith(only):
            continue
        sec = post["sections"][p["section"]]
        card = {"ask": p["ask"], "duo": {"guest": "doubt", "lines": p["lines"]}}
        guest, lines = duo_script(card, OUTRO, pick=k)
        path = out_dir / f"pilot-{name}.mp4"
        import fma.duo_reel as dr
        base = dr.timeline if not hasattr(dr, "_base_timeline") else dr._base_timeline
        dr._base_timeline = base

        def with_card(post_, section_, pl, p=p):          # pilot only: the hook card rides in the timeline props
            tl = base(post_, section_, pl)
            tl.update(hookCard=p["card"], hookUntil=round(tl["lines"][0]["end"], 2), **({"badge": p["badge"]} if p.get("badge") else {}))
            return tl
        dr.timeline = with_card
        duo_reel(post, sec, p["section"] + 1, site, path, lines, guest=guest, renderer="remotion")
        print("rendered", path)


if __name__ == "__main__":
    if sys.argv[1] == "check":
        sys.exit(0 if check() else 1)
    render(Path(sys.argv[2]))
