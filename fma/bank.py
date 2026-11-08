"""The knowledge bank (6 Nov 2026): every published day's checked content, kept as worked examples so smaller models
can be shown how we write, one small task at a time. Pavan's plan: Groq and Gemini first, Claude as the backup, and
the bank growing every day so a local model can take over if the cloud models stop being free.

    data/bank/sections.jsonl   one checked section per line: title, category, paragraphs
    data/bank/cards.jsonl      one Reel card per line: hook, points, take, ask, score
    data/bank/duo_pairs.jsonl  one Spark line -> guest punchline per line, from published duo Reels

Only published, fact-checked content goes in (it comes from content/posts). Adding a day twice changes nothing.

    python -m fma.bank add [date]
    python -m fma.bank stats"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from . import config

BANK = config.ROOT / "data" / "bank"


def _plain(s: str) -> str:
    return re.sub(r"\[S\d+\]", "", s or "").strip()


def _read(name: str) -> list[dict]:
    p = BANK / name
    if not p.exists():
        return []
    return [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines() if x.strip()]


def _write(name: str, rows: list[dict]) -> None:
    BANK.mkdir(parents=True, exist_ok=True)
    (BANK / name).write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")


def add(date: str, posts_dir: Path | None = None) -> dict:
    """Add one published day to the bank; returns how many rows each file gained."""
    p = (posts_dir or config.ROOT / "content" / "posts") / f"{date}.json"
    post = json.loads(p.read_text(encoding="utf-8"))
    new = {"sections.jsonl": [], "cards.jsonl": [], "duo_pairs.jsonl": []}
    for sec in post.get("sections", []):
        new["sections.jsonl"].append({"date": date, "title": sec.get("title"), "category": sec.get("category"),
                                      "paragraphs": [_plain(x) for x in sec.get("paragraphs", [])]})
        c = sec.get("card") or {}
        if c.get("hook"):
            new["cards.jsonl"].append({"date": date, "story": sec.get("title"), "hook": _plain(c["hook"]),
                                       "points": [_plain(x) for x in c.get("points", [])], "take": _plain(c.get("take")),
                                       "ask": c.get("ask"), "reel": c.get("reel")})
        lines = (c.get("duo") or {}).get("lines", [])
        for a, b in zip(lines, lines[1:]):
            if a.get("who") == "spark" and a.get("kind") != "comeback" and b.get("who") == "guest":
                new["duo_pairs.jsonl"].append({"date": date, "guest": c["duo"]["guest"], "spark": _plain(a["text"]),
                                               "joke": b["text"]})
    gained = {}
    for name, rows in new.items():
        old = [r for r in _read(name) if r.get("date") != date]
        _write(name, old + rows)
        gained[name] = len(rows)
    return gained


def joke_pairs(guest: str, limit: int = 6) -> list[tuple[str, str]]:
    """The newest published punchlines for a guest, as (Spark line, guest line) examples for the duo writer."""
    rows = [r for r in _read("duo_pairs.jsonl") if r.get("guest") == guest]
    return [(r["spark"], r["joke"]) for r in rows[-limit:]]


def stats() -> dict:
    return {name: len(_read(name)) for name in ("sections.jsonl", "cards.jsonl", "duo_pairs.jsonl")}


def main() -> None:
    args = sys.argv[1:]
    if args[:1] == ["add"]:
        for d in args[1:] or [sorted((config.ROOT / "content/posts").glob("*.json"))[-1].stem]:
            print(d, add(d))
    else:
        print(stats())


if __name__ == "__main__":
    main()
