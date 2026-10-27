"""One day's run: fetch -> rank -> extract -> write -> verify -> gate -> save. All or nothing."""
from __future__ import annotations

import json
import logging
import re
import shutil
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from . import config
from .extract import extract_item
from .feeds import fetch_all
from .gate import check_images, run_gate, word_count
from .rank import history_entry, pick_lineup, rank
from .verify import cites, llm_check, verify_draft
from .write import draft_post

log = logging.getLogger(__name__)


@dataclass
class Result:
    status: str          # published | skipped
    reason: str = ""
    slug: str = ""
    post: dict | None = None
    report: dict | None = None


def slugify(text: str, words: int = 7) -> str:
    w = re.findall(r"[a-z0-9]+", text.lower())
    return "-".join(w[:words]) or "post"


def load_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def recent_posts(posts_dir: Path, limit: int = 10) -> list[dict]:
    files = sorted(posts_dir.glob("*.json"), reverse=True)[:limit]
    return [load_json(f, {}) for f in files]


def assemble(date: str, verified: dict, sources: list[dict], site: dict, model: str, report: dict) -> dict:
    texts = [verified["dek"], *verified["what_happened"], *[w["text"] for w in verified["why_it_matters"]]]
    for s in verified["sections"]:
        texts.extend(s["paragraphs"])
    used = {i for t in texts for i in cites(t)}
    for extra in ("chart", "diagram", "quote"):
        if verified.get(extra):
            used.add(verified[extra]["source"])
    by_id = {s["id"]: s for s in sources}
    src_list = [{k: by_id[i][k] for k in ("id", "title", "url", "publisher", "published")}
                for i in sorted(used, key=lambda x: int(x[1:])) if i in by_id]
    timeline = []
    for s in verified["sections"]:
        ids = [i for p in s["paragraphs"] for i in cites(p)]
        lead = by_id.get(ids[0]) if ids else None
        if lead:
            timeline.append({"time": lead["published"], "title": s["title"], "publisher": lead["publisher"],
                             "category": s.get("category", "")})
    cats = [s.get("category", "") for s in verified["sections"] if s.get("category")]
    tags = list(dict.fromkeys(cats + verified.get("tags", [])))[:7]
    visuals = ["timeline"] if len(timeline) >= 2 else []
    if verified.get("chart"):
        visuals.append("chart")
    if verified.get("diagram"):
        visuals.append("diagram")
    post = {
        "date": date, "slug": f"{date}-{slugify(verified['headline'])}", "headline": verified["headline"],
        "dek": verified["dek"], "byline": site["byline"], "tags": tags,
        "what_happened": verified["what_happened"], "sections": verified["sections"],
        "why_it_matters": verified["why_it_matters"], "quote": verified.get("quote"),
        "chart": verified.get("chart"), "diagram": verified.get("diagram"), "timeline": timeline,
        "visuals": visuals, "sources": src_list, "model": model,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "verification": {k: report.get(k) for k in ("checked", "ok", "repaired", "dropped", "layer1_done", "layer2_done")},
    }
    post["word_count"] = word_count(post)
    post["reading_minutes"] = max(1, round(post["word_count"] / 200))
    return post


def run_day(date: str, http, chain, now: datetime | None = None, skip_links: bool = False,
            root: Path | None = None, build_fn=None) -> Result:
    root = root or config.ROOT
    posts_dir, reports_dir, data_dir = root / "content/posts", root / "content/reports", root / "data"
    site = _yaml(root / "config/site.yaml")
    srcs = _yaml(root / "config/sources.yaml")
    pipe = site.get("pipeline", {})
    now = now or datetime.now(timezone.utc)

    if site.get("paused"):
        return Result("skipped", "paused in config/site.yaml")
    if (posts_dir / f"{date}.json").exists():
        return Result("skipped", f"post for {date} already exists")
    if not chain:
        return Result("skipped", "no model provider available (set GEMINI_API_KEY, or run Ollama locally)")

    items, stats = fetch_all(srcs, http, now=now)
    log.info("fetched %d items: %s", len(items), stats)
    history = load_json(data_dir / "history.json", [])
    ranked = rank(items, srcs, pipe, history, now, date)
    want = int(pipe.get("stories_per_post", 5))
    candidates = pick_lineup(ranked, n=want + 2)
    for st in candidates:
        for it in ([st.lead] + [i for i in st.items if i is not st.lead])[:3]:
            it.text = extract_item(it, http)
    candidates = [st for st in candidates if len(st.lead.text or st.lead.summary) >= 200] or candidates
    lineup = candidates[:want]
    if len(lineup) < int(pipe.get("min_stories", 3)):
        return Result("skipped", f"only {len(lineup)} new stories found")

    date_label = datetime.fromisoformat(date).strftime("%A %d %B %Y")
    recent = recent_posts(posts_dir)
    feedback, last_fail = "", ""
    for attempt in range(1, int(pipe.get("attempts", 2)) + 1):
        try:
            draft, sources = draft_post(chain, lineup, date_label, feedback)
            verified, report = verify_draft(draft, sources, max_quotes=int(pipe.get("max_quotes", 1)))
            if pipe.get("llm_check", True):
                verified, report = llm_check(chain, verified, sources, report)
            post = assemble(date, verified, sources, site, chain.used or "unknown", report)
            fails = run_gate(post, report, pipe, recent, http=http, skip_links=skip_links)
        except Exception as exc:  # noqa: BLE001 - a crash in one attempt is a failed attempt, not a crash of the day
            log.exception("attempt %d crashed", attempt)
            fails, post, report = [f"attempt crashed: {type(exc).__name__}: {exc}"], None, None
        if not fails:
            return _commit(post, report, lineup, history, posts_dir, reports_dir, data_dir, root, build_fn)
        last_fail = "; ".join(fails)
        log.warning("attempt %d rejected: %s", attempt, last_fail)
        feedback = "\n".join(f"- {f}" for f in fails)
        if report:
            dropped = [e for e in report["entries"] if e["status"] == "dropped"][:12]
            if dropped:
                feedback += "\n- These sentences failed source checks and were removed; don't repeat the errors:\n" + \
                    "\n".join(f"  * {e['text'][:160]} ({'; '.join(e['problems'])})" for e in dropped)
    return Result("skipped", f"gate failed after retries: {last_fail}")


def _yaml(path: Path) -> dict:
    import yaml
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _commit(post, report, lineup, history, posts_dir, reports_dir, data_dir, root, build_fn) -> Result:
    """Build the whole site in a scratch folder with the new post first; only if that passes the image check
    do the post, report and history get written. Nothing half-made ever lands in content/."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        stage = tmp / "content"
        shutil.copytree(root / "content", stage, dirs_exist_ok=True)
        (stage / "posts").mkdir(parents=True, exist_ok=True)
        (stage / "posts" / f"{post['date']}.json").write_text(json.dumps(post, ensure_ascii=False, indent=2), encoding="utf-8")
        if build_fn is not None:
            out = tmp / "public"
            build_fn(content_dir=stage, out_dir=out)
            page = (out / "posts" / post["slug"] / "index.html").read_text(encoding="utf-8")
            missing = check_images(page, out, "/" + _base_path(root))
            if missing:
                return Result("skipped", f"broken images in built page: {missing}")
    posts_dir.mkdir(parents=True, exist_ok=True)
    reports_dir.mkdir(parents=True, exist_ok=True)
    data_dir.mkdir(parents=True, exist_ok=True)
    report_out = {**report, "date": post["date"], "slug": post["slug"], "model": post["model"]}
    (reports_dir / f"{post['date']}.json").write_text(json.dumps(report_out, ensure_ascii=False, indent=2), encoding="utf-8")
    history = [h for h in history if h.get("date") != post["date"]] + [history_entry(post["date"], post["slug"], lineup)]
    (data_dir / "history.json").write_text(json.dumps(history[-120:], ensure_ascii=False, indent=1), encoding="utf-8")
    (posts_dir / f"{post['date']}.json").write_text(json.dumps(post, ensure_ascii=False, indent=2), encoding="utf-8")
    return Result("published", slug=post["slug"], post=post, report=report_out)


def _base_path(root: Path) -> str:
    try:
        site = _yaml(root / "config/site.yaml")
        return re.sub(r"^https?://[^/]+/?", "", site["base_url"])
    except Exception:  # noqa: BLE001
        return ""


def today_in(tz: str, now: datetime | None = None) -> str:
    return (now or datetime.now(timezone.utc)).astimezone(ZoneInfo(tz)).date().isoformat()
