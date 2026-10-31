"""Command line.

    python -m fma daily [--date YYYY-MM-DD] [--provider NAME] [--skip-links]   make today's post (or skip cleanly)
    python -m fma build [--base-url URL]                                        build the site into public/
    python -m fma candidates                                                    show today's ranked stories
    python -m fma correct DATE --remove PREFIX --reason TEXT [--suppress]       remove a sentence, log it publicly
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys

from . import config
from .feeds import Http, fetch_all
from .llm import Chain, providers_from_config
from .pipeline import load_json, run_day, today_in
from .rank import pick_lineup, rank
from .site import build


def set_output(key: str, value: str) -> None:
    path = os.environ.get("GITHUB_OUTPUT")
    if path:
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(f"{key}={value}\n")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="fma")
    sub = ap.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("daily")
    d.add_argument("--date")
    d.add_argument("--provider", help="use only this provider from config/site.yaml (e.g. ollama)")
    d.add_argument("--skip-links", action="store_true")
    b = sub.add_parser("build")
    b.add_argument("--base-url")
    b.add_argument("--media", action="store_true", help="also make the day's Instagram carousel and Reel (needs ffmpeg)")
    sub.add_parser("candidates")
    c = sub.add_parser("correct", help="remove a sentence, or replace the headline, and log the correction publicly")
    c.add_argument("date")
    c.add_argument("--remove", action="append", default=[], help="the start of the sentence to remove (repeatable)")
    c.add_argument("--headline", help="replace the headline with this (checked by hand against --source)")
    c.add_argument("--source", action="append", default=[], help="source id that supports the new headline (S1)")
    c.add_argument("--note", help="the correction note readers see on the post (with --headline)")
    c.add_argument("--reason", required=True)
    c.add_argument("--suppress", action="store_true",
                   help="legal, defamation or privacy: keep the words out of the public log (log keeps a sha256)")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    site = config.site_config()

    if args.cmd == "build":
        out = build(base_url=args.base_url, media_on=args.media)
        print(f"built {out}")
        return 0

    if args.cmd == "correct":
        from .pipeline import remove_sentences, retitle
        if args.headline:
            if not args.note:
                raise SystemExit("--headline needs --note: readers are told what changed")
            print("old headline:", retitle(config.ROOT, args.date, args.headline, args.reason, args.source, args.note))
        if not args.remove:
            return 0
        removed = remove_sentences(config.ROOT, args.date, args.remove, args.reason, suppress=args.suppress)
        for s in removed:
            print("removed:", s)
        return 0 if len(removed) == len(args.remove) else 1

    if args.cmd == "candidates":
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        items, stats = fetch_all(config.sources_config(), Http(), now=now)
        print(stats)
        ranked = rank(items, config.sources_config(), site["pipeline"], load_json(config.DATA_DIR / "history.json", []),
                      now, today_in(site["timezone"]))
        for st in ranked[:20]:
            print(f"{st.score:6.2f}  {st.category:9} {len(st.items)}x  {st.title[:90]}  [{', '.join(sorted(st.publishers))}]")
        print("\nLINEUP")
        for st in pick_lineup(ranked, n=int(site["pipeline"]["stories_per_post"])):
            print(f"{st.score:6.2f}  {st.category:9} {st.title[:90]}")
        return 0

    date = args.date or today_in(site["timezone"])
    chain = Chain(providers_from_config(site, only=args.provider))
    result = run_day(date, Http(), chain, skip_links=args.skip_links, build_fn=lambda **kw: build(**kw))
    set_output("published", "true" if result.status == "published" else "false")
    if result.summary:          # one line the control dashboard reads back from the Actions log
        print("FMA_RUN_SUMMARY " + json.dumps(result.summary, ensure_ascii=False, separators=(",", ":"), default=str))
    if result.status == "published":
        print(f"PUBLISHED {result.slug} ({result.post['word_count']} words, model {result.post['model']})")
    else:
        print(f"SKIPPED {date}: {result.reason}")
    return 0      # a skipped day is a clean outcome, not a failure


if __name__ == "__main__":
    sys.exit(main())
