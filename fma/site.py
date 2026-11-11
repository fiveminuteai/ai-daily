"""Static site builder: posts, archive, tags, about, verification logs, RSS, sitemap, Open Graph cards."""
from __future__ import annotations

import hashlib
import html
import json
import re
import shutil
from datetime import datetime, timezone
from email.utils import format_datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from jinja2 import Environment, FileSystemLoader, select_autoescape
from markupsafe import Markup

from . import config
from .verify import CITE_RE, cites, split_sentences
from .social import instagram_card, plain, share_texts, x_length
from .visuals import CAT_LABEL, NARROW, WIDE, bar_chart_svg, flow_svg, og_card, timeline_svg

CITE_GROUP = re.compile(r"((?:\[S\d+\])+)")


def base_path(base_url: str) -> str:
    p = re.sub(r"^https?://[^/]+", "", base_url)
    return p if p.endswith("/") else p + "/"


def _render_markers(text: str, numbers: dict[str, int], href: str) -> str:
    out = []
    for part in CITE_GROUP.split(text):
        ids = re.findall(r"S\d+", part) if CITE_GROUP.fullmatch(part or "") else None
        if ids:
            links = ",".join(f'<a href="{href}#src-{i}" aria-label="Source {numbers.get(i, "?")}">{numbers.get(i, "?")}</a>' for i in ids)
            out.append(f'<sup class="cite">{links}</sup>')
        else:
            out.append(html.escape(part))
    return "".join(out)


def render_text(text: str, numbers: dict[str, int], href: str = "") -> Markup:
    """Escape text and turn [S1][S3] markers into superscript links to the source list. When consecutive
    sentences cite the same sources, the superscript is shown once, at the end of the run."""
    sents = split_sentences(text)
    keys = [tuple(cites(s)) for s in sents]
    out = []
    for n, s in enumerate(sents):
        last_of_run = n == len(sents) - 1 or keys[n + 1] != keys[n]
        out.append(_render_markers(s if last_of_run else CITE_RE.sub("", s), numbers, href))
    return Markup(" ".join(out))


def _utc(iso: str) -> datetime:
    """A post's publish time for the feed: when it was generated, or 00:15 UTC (the daily run) for a bare date."""
    d = datetime.fromisoformat(iso)
    return d.astimezone(timezone.utc) if d.tzinfo else d.replace(hour=0, minute=15, tzinfo=timezone.utc)


def local_day(iso: str, tz: str) -> str:
    """The calendar day of a timestamp in the site's timezone (an article from 03:00 India time is that day, not
    the previous UTC day)."""
    d = datetime.fromisoformat(iso)
    return (d.astimezone(ZoneInfo(tz)) if d.tzinfo else d).date().isoformat()


def fmt_date(iso: str, style: str = "long") -> str:
    d = datetime.fromisoformat(iso)
    if style == "short":
        return d.strftime("%d %b %Y").lstrip("0")
    return d.strftime("%A %d %B %Y").replace(" 0", " ")


def load_posts(content_dir: Path) -> list[dict]:
    posts = []
    for f in sorted((content_dir / "posts").glob("*.json"), reverse=True):
        try:
            posts.append(json.loads(f.read_text(encoding="utf-8")))
        except json.JSONDecodeError:
            continue
    return posts


def prepare(post: dict, site: dict) -> dict:
    """Add render-ready fields to a post."""
    numbers = {s["id"]: n for n, s in enumerate(post["sources"], 1)}
    r = lambda t: render_text(t, numbers)  # noqa: E731
    src_by_id = {s["id"]: s for s in post["sources"]}
    sections = []
    placed = set()
    for s in post["sections"]:
        ids = {i for p in s["paragraphs"] for i in re.findall(r"S\d+", p)}
        figs = []
        for kind in ("chart", "diagram"):
            obj = post.get(kind)
            if obj and kind not in placed and obj["source"] in ids:
                label = src_by_id.get(obj["source"], {}).get("publisher", "the source")
                svg = dual(bar_chart_svg if kind == "chart" else flow_svg, obj, label)
                figs.append({"svg": Markup(svg), "caption": obj["title"], "source_n": numbers.get(obj["source"]), "kind_text": "figures" if kind == "chart" else ("the design described" if obj.get("kind") == "compare" else "the steps described")})
                placed.add(kind)
        sections.append({**s, "label": CAT_LABEL.get(s.get("category"), s.get("category", "").title()),
                         "html": [r(p) for p in s["paragraphs"]], "figures": figs})
    for kind in ("chart", "diagram"):   # a figure whose source section was dropped goes after the last section
        obj = post.get(kind)
        if obj and kind not in placed and sections:
            label = src_by_id.get(obj["source"], {}).get("publisher", "the source")
            svg = dual(bar_chart_svg if kind == "chart" else flow_svg, obj, label)
            sections[-1]["figures"].append({"svg": Markup(svg), "caption": obj["title"], "source_n": numbers.get(obj["source"]), "kind_text": "figures" if kind == "chart" else ("the design described" if obj.get("kind") == "compare" else "the steps described")})
    quote = post.get("quote")
    topic_list = list(dict.fromkeys(s.get("category") for s in post["sections"] if s.get("category") in CAT_LABEL))
    sec_ids = [(s.get("category"), {i for p in s["paragraphs"] for i in re.findall(r"S\d+", p)}) for s in post["sections"]]

    def topic_of(text: str) -> str:
        ids = set(re.findall(r"S\d+", text))
        best = max(sec_ids, key=lambda c: len(c[1] & ids), default=(None, set()))
        return best[0] if best[0] and best[1] & ids else (topic_list[0] if topic_list else "research")

    head_a, head_b = split_headline(post["headline"])
    return {
        **post,
        "date_long": fmt_date(post["date"]), "date_short": fmt_date(post["date"], "short"),
        "dek_html": r(post["dek"]),
        "what_post": [{"html": r(b), "topic": topic_of(b)} for b in post["what_happened"]],
        "what_home": [{"html": render_text(b, numbers, f"posts/{post['slug']}/"), "topic": topic_of(b)}
                      for b in post["what_happened"]],
        "head_a": head_a, "head_b": head_b, "topic_list": topic_list,
        "date_day": datetime.fromisoformat(post["date"]).strftime("%a %d"),
        "sections_r": sections,
        "why_html": [{"html": r(w["text"]), "speculative": w["speculative"]} for w in post["why_it_matters"]],
        "quote_r": {**quote, "source_n": numbers.get(quote["source"])} if quote else None,
        "timeline_svg": dual(timeline_svg, post.get("timeline", []), site.get("timezone", "Asia/Kolkata"))
        if len(post.get("timeline", [])) >= 2 else None,
        "sources_r": [{**s, "n": n, "date": fmt_date(local_day(s["published"], site.get("timezone", "Asia/Kolkata")), "short")
                       if s.get("published") else ""}
                      for n, s in enumerate(post["sources"], 1)],
        "url_path": f"posts/{post['slug']}/",
        "dek_plain": re.sub(r"\s*\[S\d+\]", "", post["dek"]),
    }


def split_headline(h: str) -> tuple[str, str]:
    """Split a headline so its second clause can carry the colour gradient."""
    for sep in (", and ", ", as ", "; ", ", ", " as ", " while "):
        i = h.rfind(sep)
        if 12 <= i <= len(h) - 10:
            cut = i + (1 if sep.startswith((",", ";")) else 0)
            return h[:cut].strip(), h[cut:].strip()
    return h, ""                        # no natural break: no gradient rather than an odd emphasis


TOPICS = ["models", "architecture", "research", "products", "tools", "policy", "impact"]
TOPIC_BLURBS = {
    "models": "New AI models, what they can do and how they compare.",
    "architecture": "How models are built: attention, mixture-of-experts, long context, reasoning, efficiency.",
    "research": "Papers and findings, explained without the jargon.",
    "products": "AI features arriving in apps and services people use.",
    "tools": "Open-source projects, libraries and developer tools.",
    "policy": "Laws, regulation, safety, lawsuits and the money behind AI companies.",
    "impact": "What AI is changing at work, in health, schools and society.",
}


def dual(fn, *args) -> Markup:
    """Draw a visual twice: a wide layout for desktop and a narrow one for phones (CSS shows one)."""
    return Markup(f'<div class="viz-wide">{fn(*args, W=WIDE)}</div><div class="viz-narrow">{fn(*args, W=NARROW)}</div>')


def first_by_name(sources: list[dict]) -> list[dict]:
    """Sources for the About page, one per outlet: an outlet read through two feeds is listed once."""
    seen: set[str] = set()
    return [s for s in sources if not (s["name"] in seen or seen.add(s["name"]))]


def tag_slug(tag: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", tag.lower()).strip("-")


def social_media(folder: Path, post: dict, site: dict) -> dict:
    """The day's Instagram carousel (slides plus a zip) and the Reel. Slow (about a minute for the Reel) and needs
    ffmpeg, so only the deploy build makes them, and only for the newest post. A failure here never stops the site."""
    import logging
    import zipfile

    from .carousel import carousel
    from .reel import reel

    out: dict = {}
    try:
        slides = carousel(folder / "carousel", post, site, fmt_date(post["date"]))
        with zipfile.ZipFile(folder / "carousel.zip", "w", zipfile.ZIP_STORED) as z:
            for s in slides:
                z.write(s, f"fiveminuteai-{post['date']}-{s.name}")
        out["slides"] = [s.name for s in slides]
    except Exception as exc:  # noqa: BLE001
        logging.getLogger(__name__).warning("carousel failed: %s", exc)
    try:
        reel(post, site, fmt_date(post["date"], "short"), folder / "reel.mp4")
        out["reel"] = "reel.mp4"
    except Exception as exc:  # noqa: BLE001
        logging.getLogger(__name__).warning("reel failed: %s", exc)
    from .story_reel import card_stories, palettes_for, story_reel
    out["story_reels"] = []
    from .social_queue import reel_slots
    stories = card_stories(post, limit=len(reel_slots(site)))      # one Reel per slot (up to 5 from 7 Nov 2026)
    for k, ((n, sec), pal) in enumerate(zip(stories, palettes_for(stories, post["date"]))):   # up to three, each its own colours
        path = folder / "reels" / f"{k + 1:02d}.mp4"
        if duo_ok(post, sec):      # the duo Reel (5 Nov 2026); on any failure the story gets its ordinary Reel
            try:
                from .duo_desk import script as duo_script
                from .duo_reel import duo_reel
                from .voice import OUTRO
                from datetime import date as _date
                day = _date.fromisoformat(str(post["date"])).toordinal()
                from .duo_desk import closing_order
                for pick in closing_order(day * 5 + k):    # a different closing each Reel; if it runs the Reel
                    guest, lines = duo_script(sec["card"], OUTRO, pick=pick)   # over the cap, a shorter one
                    try:
                        duo_reel(post, sec, n, site, path, lines, guest=guest)
                        break
                    except ValueError as exc:
                        if "cap" not in str(exc):
                            raise
                else:
                    raise ValueError("over the length cap with every closing")
                reel_cover(post, sec, path.with_suffix(".jpg"), guest=guest, lines=lines)
                out["story_reels"].append({"file": f"reels/{k + 1:02d}.mp4", "hook": plain(sec["card"]["hook"]),
                                           "duo": guest, "story": n})
                continue
            except Exception as exc:  # noqa: BLE001
                logging.getLogger(__name__).warning("duo reel %d failed, using the ordinary Reel: %s", k + 1, exc)
                why = f"duo render failed: {exc}"[:300]
        else:
            from . import voice as _voice
            why = ("card has no duo" if not (sec.get("card") or {}).get("duo") else
                   "no voice (Kokoro missing)" if not _voice.available() else "before duo Reels started")
        try:
            story_reel(post, sec, n, site, path, palette=pal, narrate=True)   # 11 Nov 2026: was silent
            reel_cover(post, sec, path.with_suffix(".jpg"), guest="solo")
            out["story_reels"].append({"file": f"reels/{k + 1:02d}.mp4", "hook": plain(sec["card"]["hook"]),
                                       "duo": None, "story": n, "plain_because": why})
        except Exception as exc:  # noqa: BLE001
            logging.getLogger(__name__).warning("story reel %d failed: %s", k + 1, exc)
            out["story_reels"].append({"file": None, "story": n, "error": str(exc)[:300]})
    write_manifest(folder, post, out)
    return out


def write_manifest(folder: Path, post: dict, out: dict) -> None:
    """share/<date>/media.json: what this deploy rendered, for the daily health check (fma/health.py, 11 Nov 2026:
    a plain Reel used to look exactly like a duo one to every check). Each Reel's length and whether it has sound
    are measured from the file itself."""
    import json
    import shutil
    import subprocess
    reels = []
    for r in out.get("story_reels", []):
        r = dict(r)
        f = folder / r["file"] if r.get("file") else None
        if f and f.exists() and shutil.which("ffprobe"):
            try:
                probe = json.loads(subprocess.run(
                    ["ffprobe", "-v", "error", "-show_entries", "format=duration:stream=codec_type", "-of", "json",
                     str(f)], capture_output=True, text=True, timeout=60, stdin=subprocess.DEVNULL).stdout or "{}")
                r["seconds"] = round(float(probe.get("format", {}).get("duration", 0)), 1)
                r["audio"] = any(st.get("codec_type") == "audio" for st in probe.get("streams", []))
            except Exception:  # noqa: BLE001 - the health check reports a Reel it cannot measure
                pass
        r["cover"] = bool(f and f.with_suffix(".jpg").exists())
        reels.append(r)
    from .voice import available as voice_on
    if not voice_on():
        print("::warning::Reels rendered WITHOUT a voice: Kokoro is missing in this build")
    for r in reels:          # a degraded Reel is a GitHub warning on the run, not an INFO line nobody reads
        if r.get("error") or str(r.get("plain_because", "")).startswith(("duo render", "no voice")):
            print(f"::warning::Reel {r.get('file') or r.get('story')}: {r.get('error') or r['plain_because']}"[:400])
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "media.json").write_text(json.dumps({
        "date": post["date"], "slug": post.get("slug"), "voice": voice_on(), "slides": out.get("slides", []),
        "reel": out.get("reel"), "reels": reels}, ensure_ascii=False, indent=1), encoding="utf-8")


def reel_cover(post: dict, sec: dict, out, guest: str, lines: list | None = None) -> None:
    """The Reel's thumbnail (8 Nov 2026); a failure only costs the cover, never the Reel."""
    import logging
    try:
        from .cover import render_cover
        render_cover(post, sec, out, guest=guest, lines=lines)
    except Exception as exc:  # noqa: BLE001
        logging.getLogger(__name__).warning("cover for %s failed: %s", out.name, exc)


# ---------------------------------------------------------------- structured data (10 Nov 2026, AEO check)
# Answer engines (Google AI Overviews, ChatGPT search, Perplexity) read schema.org JSON-LD to know who publishes a
# page, when, and from which sources. Every page carries the Organization and WebSite; posts a NewsArticle with
# its dates and citations; About an AboutPage with the FAQ it shows.

def _org(site: dict, origin: str, base: str) -> dict:
    return {"@type": "Organization", "@id": f"{origin}{base}#org", "name": site["name"], "url": f"{origin}{base}",
            "logo": f"{origin}{base}assets/icon.svg", "email": "hello@fiveminuteai.net",
            "sameAs": [s["url"] for s in site.get("social", [])]}


def site_jsonld(site: dict, origin: str, base: str) -> dict:
    return {"@context": "https://schema.org", "@graph": [
        _org(site, origin, base),
        {"@type": "WebSite", "@id": f"{origin}{base}#site", "name": site["name"], "url": f"{origin}{base}",
         "description": site.get("tagline", ""), "inLanguage": site.get("language", "en"),
         "publisher": {"@id": f"{origin}{base}#org"}}]}


def article_jsonld(p: dict, site: dict, origin: str, base: str) -> dict:
    url = f"{origin}{base}{p['url_path']}"
    published = f"{p['date']}T05:45:00+05:30"
    modified = p.get("generated_at") or published
    return {"@context": "https://schema.org", "@type": "NewsArticle", "@id": f"{url}#article", "headline": p["headline"],
            "description": p.get("dek_plain", ""), "url": url, "mainEntityOfPage": url, "datePublished": published,
            "dateModified": modified, "inLanguage": site.get("language", "en"),
            "image": f"{origin}{base}og/{p['slug']}.png", "author": {"@id": f"{origin}{base}#org"},
            "publisher": {"@id": f"{origin}{base}#org"},
            "articleSection": [s.get("title", "") for s in p.get("sections", [])],
            "citation": [s["url"] for s in p.get("sources", []) if s.get("url")],
            "isAccessibleForFree": True}


ABOUT_FAQ = [
    ("Is Five Minute AI written by AI?", "Yes. A language model drafts each post from the public sources linked in it, "
     "and a program checks every number and name against those sources before anything is published."),
    ("How are the facts checked?", "Twice: code compares every number and name with the cited source, and a second "
     "pass re-reads each sentence next to its source. Anything that can't be confirmed is deleted, not reworded."),
    ("How often is it published?", "Every morning, India time, with short video Reels through the day on Instagram "
     "and YouTube Shorts."),
    ("Where can I report a mistake?", "On GitHub issues or by email to hello@fiveminuteai.net; corrections are noted "
     "on the post."),
]


def about_jsonld(site: dict, origin: str, base: str) -> dict:
    return {"@context": "https://schema.org", "@graph": [
        {"@type": "AboutPage", "url": f"{origin}{base}about/", "name": "How this blog is made",
         "about": {"@id": f"{origin}{base}#org"}},
        {"@type": "FAQPage", "mainEntity": [{"@type": "Question", "name": q,
                                             "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in ABOUT_FAQ]}]}


def llms_txt(posts: list[dict], site: dict, origin: str, base: str) -> str:
    """/llms.txt (llmstxt.org): what the site is and where the good pages are, for AI crawlers that read it."""
    root = f"{origin}{base}"
    lines = [f"# {site['name']}", "", f"> {site.get('tagline', '')}", "",
             "Daily AI news, generated from linked public sources and fact-checked sentence by sentence.", "",
             "## Pages", f"- [How it's made]({root}about/): sources, models and the checking process",
             f"- [Archive]({root}archive/): every post", f"- [Topics]({root}tags/)", "", "## Latest posts"]
    lines += [f"- [{p['headline']}]({root}{p['url_path']}): {p['date']}" for p in posts[:20]]
    return "\n".join(lines) + "\n"


DUO_FROM = "2026-11-06"     # the first day of duo Reels: earlier days keep their Reels exactly as they were


def duo_ok(post: dict, sec: dict) -> bool:
    from . import voice
    return (str(post.get("date", "")) >= DUO_FROM and bool((sec.get("card") or {}).get("duo"))
            and voice.available())


def build(content_dir: Path | None = None, out_dir: Path | None = None, base_url: str | None = None,
          media_on: bool = False) -> Path:
    content_dir = content_dir or config.CONTENT_DIR
    out_dir = out_dir or config.OUT_DIR
    site = config.site_config()
    if base_url:
        site = {**site, "base_url": base_url}
    base = base_path(site["base_url"])
    origin = re.match(r"^https?://[^/]+", site["base_url"])
    origin = origin.group(0) if origin else ""

    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True)
    shutil.copytree(config.SITE_DIR / "static", out_dir / "assets")
    # hand-made pages served as they are (10 Nov 2026: the Five Minute AI Desk sales page at /desk/, approved by
    # Pavan); not posts, so they stay out of the feed and the sitemap
    if (config.SITE_DIR / "pages").is_dir():
        shutil.copytree(config.SITE_DIR / "pages", out_dir, dirs_exist_ok=True)
    (out_dir / ".nojekyll").write_text("", encoding="utf-8")

    env = Environment(loader=FileSystemLoader(config.SITE_DIR / "templates"), autoescape=select_autoescape(["html", "xml"]),
                      trim_blocks=True, lstrip_blocks=True)
    # a fingerprint in the stylesheet URL, so browsers fetch the new file the moment the design changes
    # instead of mixing new pages with a cached old stylesheet (GitHub Pages lets browsers cache it 10 minutes)
    asset_v = hashlib.sha256((config.SITE_DIR / "static" / "style.css").read_bytes()).hexdigest()[:10]
    env.globals.update(asset_v=asset_v, site=site, base=base, origin=origin, year=datetime.now(timezone.utc).year, tag_slug=tag_slug,
                       labels=CAT_LABEL, topics=TOPICS, topic_blurbs=TOPIC_BLURBS, nav="",
                       site_ld=site_jsonld(site, origin, base), page_ld=None)

    posts = [prepare(p, site) for p in load_posts(content_dir)]
    for i, p in enumerate(posts):
        p["issue"] = len(posts) - i                    # "No. 2" on the front page: posts so far, oldest is No. 1
    tags: dict[str, list[dict]] = {}
    for p in posts:
        for t in p["tags"]:
            tags.setdefault(t, []).append(p)

    def write(rel: str, text: str):
        path = out_dir / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    og_card(out_dir / "og/default.png", site["tagline"], site["name"], "Daily", "One post a day")
    for i, p in enumerate(posts):
        og_card(out_dir / f"og/{p['slug']}.png", p["headline"], site["name"], p["date_short"], f"{p['reading_minutes']} min read",
                topics=p["topic_list"])
        newer = posts[i - 1] if i > 0 else None
        older = posts[i + 1] if i + 1 < len(posts) else None
        write(f"posts/{p['slug']}/index.html", env.get_template("post.html").render(
            post=p, newer=newer, older=older, page_title=p["headline"], description=p["dek_plain"],
            og_image=f"{base}og/{p['slug']}.png", canonical=p["url_path"], og_type="article",
            page_ld=article_jsonld(p, site, origin, base)))
        rep = content_dir / "reports" / f"{p['date']}.json"
        if rep.exists():
            report = json.loads(rep.read_text(encoding="utf-8"))
            write(f"posts/{p['slug']}/verification/index.html", env.get_template("verification.html").render(
                post=p, report=report, page_title=f"Verification log · {p['date_short']}",
                description="Every sentence the verifier checked for this post, and what it removed.",
                og_image=f"{base}og/{p['slug']}.png", canonical=f"{p['url_path']}verification/", og_type="article"))

    # share kits for the last week: ready-to-paste posts and an Instagram card. Unlisted pages (noindex, not in the
    # sitemap); share/ always holds today's
    for i, p in enumerate(posts[:7]):
        instagram_card(out_dir / f"share/{p['date']}/instagram.png", p, site["name"], p["date_long"], p["topic_list"])
        texts = share_texts(p, site)
        media = social_media(out_dir / f"share/{p['date']}", p, site) if (i == 0 and media_on) else {}
        page = env.get_template("share.html").render(
            post=p, texts=texts, x_len=x_length(texts["x"]), latest=i == 0, noindex=True, media=media,
            page_title=f"Share kit · {p['date_short']}", description="Ready-to-paste social posts for this issue.",
            og_image=f"{base}og/{p['slug']}.png", canonical=f"share/{p['date']}/", og_type="website")
        write(f"share/{p['date']}/index.html", page)
        if i == 0:
            write("share/index.html", page)

    write("index.html", env.get_template("index.html").render(
        latest=posts[0] if posts else None, week=posts[:7], page_title=None, description=site["tagline"],
        og_image=f"{base}og/{posts[0]['slug']}.png" if posts else f"{base}og/default.png", canonical="", og_type="website"))
    by_month: dict[str, list[dict]] = {}
    for p in posts:
        by_month.setdefault(datetime.fromisoformat(p["date"]).strftime("%B %Y"), []).append(p)
    write("archive/index.html", env.get_template("archive.html").render(
        months=by_month, count=len(posts), page_title="Archive", description=f"Every {site['name']} post.", nav="archive",
        og_image=f"{base}og/default.png", canonical="archive/", og_type="website"))
    other = sorted(((t, ps) for t, ps in tags.items() if t not in CAT_LABEL), key=lambda kv: (-len(kv[1]), kv[0]))
    write("tags/index.html", env.get_template("tags.html").render(
        tag_map=tags, other_tags=other, page_title="Topics", description="Posts by topic.", nav="topics",
        og_image=f"{base}og/default.png", canonical="tags/", og_type="website"))
    for t in TOPICS:
        tags.setdefault(t, [])
    for t, ps in tags.items():
        write(f"tags/{tag_slug(t)}/index.html", env.get_template("tag.html").render(
            tag=t, label=CAT_LABEL.get(t, t), posts=ps, page_title=CAT_LABEL.get(t, f"Tag: {t}"), nav="topics",
            description=f"{site['name']} posts tagged {t}.", og_image=f"{base}og/default.png",
            canonical=f"tags/{tag_slug(t)}/", og_type="website"))
    write("llms.txt", llms_txt(posts, site, origin, base))
    write("about/index.html", env.get_template("about.html").render(page_ld=about_jsonld(site, origin, base),
        page_title="How this blog is made", description="Five Minute AI is AI-assisted and generated automatically from linked sources.",
        og_image=f"{base}og/default.png", canonical="about/", og_type="website", nav="about",
        sources=first_by_name(config.sources_config()["sources"]), providers=site.get("providers", [])))
    for slug, title, desc in (("privacy", "Privacy policy", f"What {site['name']} collects: almost nothing."),
                              ("terms", "Terms of use", f"How to use {site['name']}'s posts and videos.")):
        write(f"{slug}/index.html", env.get_template(f"{slug}.html").render(
            page_title=title, description=desc, og_image=f"{base}og/default.png", canonical=f"{slug}/",
            og_type="website", nav=""))
    write("search/index.html", env.get_template("search.html").render(
        page_title="Search", description=f"Search every {site['name']} post.", nav="search",
        og_image=f"{base}og/default.png", canonical="search/", og_type="website"))
    index = [{"u": f"{base}{p['url_path']}", "t": p["headline"], "d": p["dek_plain"], "date": p["date"],
              "ds": p["date_short"], "x": " ".join([s["title"] for s in p["sections"]] +
                                                    [CITE_RE.sub("", t) for s in p["sections"] for t in s["paragraphs"]])}
             for p in posts]
    write("search.json", json.dumps(index, ensure_ascii=False, separators=(",", ":")))
    write("404.html", env.get_template("404.html").render(page_title="Not found", description=site["tagline"],
                                                           og_image=f"{base}og/default.png", canonical="", og_type="website"))
    write("feed.xml", env.get_template("feed.xml").render(
        posts=posts[:20], now=format_datetime(datetime.now(timezone.utc)),
        rfc=lambda iso: format_datetime(_utc(iso).astimezone(ZoneInfo(site.get("timezone", "Asia/Kolkata"))))))
    urls = (["", "archive/", "tags/", "about/", "search/", "privacy/", "terms/"] + [p["url_path"] for p in posts]
            + [f"{p['url_path']}verification/" for p in posts if (content_dir / "reports" / f"{p['date']}.json").exists()]
            + [f"tags/{tag_slug(t)}/" for t in tags])
    write("sitemap.xml", '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
          + "\n".join(f"  <url><loc>{html.escape(origin + base + u)}</loc></url>" for u in urls) + "\n</urlset>\n")
    write("robots.txt", f"User-agent: *\nAllow: /\nDisallow: {base}share/\nSitemap: {origin}{base}sitemap.xml\n")
    return out_dir
