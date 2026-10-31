"""One day's run: fetch -> rank -> extract -> write -> verify -> gate -> save. All or nothing."""
from __future__ import annotations

import hashlib
import json
import logging
import re
import shutil
import tempfile
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from . import config
from .editor import apply_editor
from .extract import extract_item
from .feeds import fetch_all
from .gate import check_images, run_gate, word_count
from .rank import history_entry, pick_lineup, rank
from .verify import cites, llm_check, mark_dropped, mark_unused, norm, plain, split_sentences, verify_draft
from .write import draft_post

log = logging.getLogger(__name__)


@dataclass
class Result:
    status: str          # published | skipped
    reason: str = ""
    slug: str = ""
    post: dict | None = None
    report: dict | None = None
    summary: dict | None = None


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


def fill_summary(verified: dict, sources: list[dict]) -> dict:
    """Make the top of the post complete using only sentences that already passed verification:
    one 30-second bullet per top-three story, in section order, and a dek. If the model's own bullet or dek was cut,
    the first verified sentence of that story stands in."""
    story_of = {s["id"]: s.get("story") for s in sources}

    def story(text: str):
        ids = cites(text)
        return story_of.get(ids[0]) if ids else None

    def first_sentence(section: dict) -> str:
        for p in section.get("paragraphs", []):
            sents = split_sentences(p)
            if sents:
                return sents[0]
        return ""

    bullets = []
    for sec in verified["sections"][:3]:
        st = story(" ".join(sec["paragraphs"]))
        own = next((b for b in verified["what_happened"] if story(b) == st and b not in bullets), None)
        pick = own or first_sentence(sec)
        if pick:
            bullets.append(pick)
    dek = verified["dek"] or (first_sentence(verified["sections"][0]) if verified["sections"] else "")
    return {**verified, "what_happened": bullets, "dek": dek}


def assemble(date: str, verified: dict, sources: list[dict], site: dict, model: str, report: dict) -> dict:
    verified = fill_summary(verified, sources)
    verified = {**verified, "what_happened": verified["what_happened"][:3]}
    mark_unused(report, verified)          # verified but not in the post: "unused", never "confirmed"
    texts =[verified["dek"], *verified["what_happened"][:3], *[w["text"] for w in verified["why_it_matters"]]]
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
        "what_happened": verified["what_happened"][:3], "sections": verified["sections"],
        "why_it_matters": verified["why_it_matters"], "quote": verified.get("quote"),
        "chart": verified.get("chart"), "diagram": verified.get("diagram"), "timeline": timeline,
        "visuals": visuals, "sources": src_list, "model": model,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "verification": {k: report.get(k) for k in ("checked", "ok", "repaired", "dropped", "unused",
                                                    "layer1_done", "layer2_done")},
    }
    post["word_count"] = word_count(post)
    post["reading_minutes"] = max(1, round(post["word_count"] / 200))
    return post


def run_day(date: str, http, chain, now: datetime | None = None, skip_links: bool = False,
            root: Path | None = None, build_fn=None) -> Result:
    """Run the day and keep a run summary for the control dashboard: each stage's status, time and key numbers.
    It is always written to logs/run-<date>.json, and to data/runs/<date>.json (committed with the post) when the
    day publishes. A skipped day never touches content/ or data/."""
    root = root or config.ROOT
    summary: dict = {"date": date, "started_at": _utc_iso(), "stages": {}}
    t0 = time.monotonic()
    result = _run_day(date, http, chain, now, skip_links, root, build_fn, summary)
    summary.update(status=result.status, reason=result.reason, slug=result.slug, finished_at=_utc_iso(),
                   seconds=round(time.monotonic() - t0, 1))
    result.summary = summary
    _write_summary(root, summary, published=result.status == "published")
    return result


def _utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _stage(summary: dict, name: str, started: float, status: str = "ok", **numbers) -> None:
    summary["stages"][name] = {"status": status, "seconds": round(time.monotonic() - started, 1), **numbers}


def _source_stats(stats: dict) -> dict:
    """fetch_all's "ok:12" / "error:Timeout" / "disabled" strings as {status, items, error}."""
    out = {}
    for sid, val in stats.items():
        kind, _, rest = str(val).partition(":")
        out[sid] = {"status": kind, "items": int(rest) if kind == "ok" and rest.isdigit() else 0,
                    **({"error": rest} if kind == "error" else {})}
    return out


def _story_row(st, picked: bool) -> dict:
    return {"title": st.title, "url": st.lead.url, "score": round(st.score, 2),
            "interest": st.interest, "category": st.category, "outlets": sorted(st.publishers), "picked": picked}


def _counts(report: dict | None) -> dict:
    return {k: (report or {}).get(k, 0) for k in ("checked", "ok", "repaired", "dropped")}


def _write_summary(root: Path, summary: dict, published: bool) -> None:
    text = json.dumps(summary, ensure_ascii=False, indent=1, default=str)
    targets = [root / "logs" / f"run-{summary['date']}.json"]
    if published:
        targets.append(root / "data" / "runs" / f"{summary['date']}.json")
    for path in targets:
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        except OSError:                    # a summary must never break a run
            log.exception("could not write run summary %s", path)


def _run_day(date: str, http, chain, now, skip_links, root: Path, build_fn, summary: dict) -> Result:
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

    t = time.monotonic()
    items, stats = fetch_all(srcs, http, now=now)
    log.info("fetched %d items: %s", len(items), stats)
    _stage(summary, "collect", t, items=len(items), sources=_source_stats(stats))
    t = time.monotonic()
    history = load_json(data_dir / "history.json", [])
    ranked = rank(items, srcs, pipe, history, now, date)
    ranked = apply_editor(chain, ranked, site.get("audience", {}))
    try:                                   # keep the day's ranking, so picks can be explained later
        (root / "logs").mkdir(exist_ok=True)
        (root / "logs" / f"ranking-{date}.json").write_text(json.dumps(
            [{"title": st.title, "score": st.score, "interest": st.interest, "category": st.category,
              "outlets": sorted(st.publishers)} for st in ranked[:40]], ensure_ascii=False, indent=1), encoding="utf-8")
    except OSError:
        pass
    want = int(pipe.get("stories_per_post", 5))
    candidates = pick_lineup(ranked, n=want + 2)
    _stage(summary, "rank", t, stories=len(ranked), editor=any(st.interest is not None for st in ranked))
    t = time.monotonic()
    for st in candidates:
        for it in ([st.lead] + [i for i in st.items if i is not st.lead])[:3]:
            it.text = extract_item(it, http)
    candidates = [st for st in candidates if len(st.lead.text or st.lead.summary) >= 200] or candidates
    lineup = candidates[:want]
    _stage(summary, "extract", t, articles=sum(min(3, len(st.items)) for st in candidates),
           with_text=sum(1 for st in candidates for i in st.items[:3] if len(i.text) >= 600))
    picked = {id(st) for st in lineup}
    summary["stages"]["rank"]["top"] = [_story_row(st, id(st) in picked) for st in ranked[:12]]
    summary["stages"]["rank"]["lineup"] = [_story_row(st, True) for st in lineup]
    if len(lineup) < int(pipe.get("min_stories", 3)):
        summary["stages"]["rank"]["status"] = "failed"
        return Result("skipped", f"only {len(lineup)} new stories found")

    date_label = datetime.fromisoformat(date).strftime("%A %d %B %Y")
    recent = recent_posts(posts_dir)
    feedback, last_fail = "", ""
    attempts: list[dict] = []
    summary["attempts"] = attempts
    for attempt in range(1, int(pipe.get("attempts", 2)) + 1):
        draft = None
        times: dict[str, float] = {}
        layer1: dict = {}
        try:
            t = time.monotonic()
            draft, sources = draft_post(chain, lineup, date_label, feedback, mode=pipe.get("write_mode", "sections"))
            times["write"], t = time.monotonic() - t, time.monotonic()
            verified, report = verify_draft(draft, sources, max_quotes=int(pipe.get("max_quotes", 1)))
            layer1 = _counts(report)
            times["layer1"], t = time.monotonic() - t, time.monotonic()
            if pipe.get("llm_check", True):
                verified, report = llm_check(chain, verified, sources, report)
            times["layer2"], t = time.monotonic() - t, time.monotonic()
            post = assemble(date, verified, sources, site, chain.used or "unknown", report)
            fails = run_gate(post, report, pipe, recent, http=http, skip_links=skip_links)
            times["gate"] = time.monotonic() - t
        except Exception as exc:  # noqa: BLE001 - a crash in one attempt is a failed attempt, not a crash of the day
            log.exception("attempt %d crashed", attempt)
            fails, post, report = [f"attempt crashed: {type(exc).__name__}: {exc}"], None, None
        attempts.append({"n": attempt, "model": getattr(chain, "used", None) or "",
                         "seconds": {k: round(v, 1) for k, v in times.items()},
                         "layer1": layer1, "layer2": _counts(report) if report and report.get("layer2_done") else {},
                         "unused": (report or {}).get("unused", 0), "fails": fails})
        _dump_rejected(root, date, attempt, chain, locals().get("draft"), post, report, fails)
        if not fails:
            t = time.monotonic()
            result = _commit(post, report, lineup, history, posts_dir, reports_dir, data_dir, root, build_fn)
            ok = result.status == "published"
            _stage(summary, "publish", t, "ok" if ok else "failed",
                   **({"word_count": post["word_count"], "sources": len(post["sources"])} if ok else {"error": result.reason}))
            return result
        last_fail = "; ".join(fails)
        log.warning("attempt %d rejected: %s", attempt, last_fail)
        feedback = "\n".join(f"- {f}" for f in fails)
        if report:
            dropped = [e for e in report["entries"] if e["status"] == "dropped"][:12]
            if dropped:
                feedback += "\n- These sentences failed source checks and were removed; don't repeat the errors:\n" + \
                    "\n".join(f"  * {e['text'][:160]} ({'; '.join(e['problems'])})" for e in dropped)
    return Result("skipped", f"gate failed after retries: {last_fail}")


def remove_sentences(root: Path, date: str, prefixes: list[str], reason: str, suppress: bool = False) -> list[str]:
    """Editorial correction by removal only (removing never adds a claim). Each removal is appended to the post's
    public verification log with the reason. With suppress (legal, defamation or privacy reasons) the log keeps
    "[text withheld: <reason>]" and a sha256 of the sentence's plain text instead of the words, and the words are
    also scrubbed from the sentence's earlier log entries. Returns the sentences removed."""
    post_path, rep_path = root / "content/posts" / f"{date}.json", root / "content/reports" / f"{date}.json"
    post, report = load_json(post_path, None), load_json(rep_path, {"entries": []})
    if post is None:
        raise SystemExit(f"no post for {date}")
    removed: list[str] = []

    def norm_start(s: str) -> str:
        return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()

    def keep(text: str) -> str:
        out = []
        for s in split_sentences(text):
            hit = next((p for p in prefixes if norm_start(re.sub(r"\[S\d+\]", "", s)).startswith(norm_start(p))), None)
            if hit:
                removed.append(s)
            else:
                out.append(s)
        return " ".join(out)

    post["dek"] = keep(post["dek"])
    post["what_happened"] = [x for x in (keep(b) for b in post["what_happened"]) if x]
    post["sections"] = [{**s, "paragraphs": [x for x in (keep(p) for p in s["paragraphs"]) if x]} for s in post["sections"]]
    post["why_it_matters"] = [{**w, "text": keep(w["text"])} for w in post["why_it_matters"] if keep(w["text"])]
    removed = list(dict.fromkeys(removed))
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    for s in removed:
        problem = f"removed in editorial review on {stamp}: {reason}"
        # the sentence's own "Confirmed" entry becomes "Removed", so the totals still add up after a correction
        mark_dropped(report, plain(s), cites(s), problem)
        if suppress:
            digest = hashlib.sha256(plain(s).encode("utf-8")).hexdigest()
            withheld = {"text": f"[text withheld: {reason}]", "sha256": digest, "withheld": True}
            for e in report.get("entries", []):          # every entry that carries the words
                if not e.get("withheld") and norm(plain(e.get("text", ""))) == norm(plain(s)):
                    e.update(withheld)
    for k in ("checked", "ok", "repaired", "dropped"):
        post["verification"][k] = report.get(k, 0)
    post["word_count"] = word_count(post)
    post["reading_minutes"] = max(1, round(post["word_count"] / 200))
    post_path.write_text(json.dumps(post, ensure_ascii=False, indent=2), encoding="utf-8")
    rep_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return removed


def _dump_rejected(root: Path, date: str, attempt: int, chain, draft, post, report, fails) -> None:
    """Keep every attempt's raw reply and verification report under logs/ (never content/) for diagnosis."""
    try:
        d = root / "logs" / "attempts"
        d.mkdir(parents=True, exist_ok=True)
        (d / f"{date}-attempt{attempt}.json").write_text(json.dumps(
            {"fails": fails, "raw_reply": getattr(chain, "last_raw", ""), "draft": draft, "post": post, "report": report},
            ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    except Exception:  # noqa: BLE001 - diagnostics must never break a run
        log.exception("could not write attempt log")


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
