"""Static site builder: posts, archive, tags, about, verification logs, RSS, sitemap, Open Graph cards."""
from __future__ import annotations

import html
import json
import re
import shutil
from datetime import datetime, timezone
from email.utils import format_datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape
from markupsafe import Markup

from . import config
from .verify import CITE_RE, cites, split_sentences
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
                figs.append({"svg": Markup(svg), "caption": obj["title"], "source_n": numbers.get(obj["source"]), "kind_text": "figures" if kind == "chart" else "the steps described"})
                placed.add(kind)
        sections.append({**s, "label": CAT_LABEL.get(s.get("category"), s.get("category", "").title()),
                         "html": [r(p) for p in s["paragraphs"]], "figures": figs})
    for kind in ("chart", "diagram"):   # a figure whose source section was dropped goes after the last section
        obj = post.get(kind)
        if obj and kind not in placed and sections:
            label = src_by_id.get(obj["source"], {}).get("publisher", "the source")
            svg = dual(bar_chart_svg if kind == "chart" else flow_svg, obj, label)
            sections[-1]["figures"].append({"svg": Markup(svg), "caption": obj["title"], "source_n": numbers.get(obj["source"]), "kind_text": "figures" if kind == "chart" else "the steps described"})
    quote = post.get("quote")
    return {
        **post,
        "date_long": fmt_date(post["date"]), "date_short": fmt_date(post["date"], "short"),
        "dek_html": r(post["dek"]),
        "what_html": [r(b) for b in post["what_happened"]],
        "what_html_home": [render_text(b, numbers, f"posts/{post['slug']}/") for b in post["what_happened"]],
        "sections_r": sections,
        "why_html": [{"html": r(w["text"]), "speculative": w["speculative"]} for w in post["why_it_matters"]],
        "quote_r": {**quote, "source_n": numbers.get(quote["source"])} if quote else None,
        "timeline_svg": dual(timeline_svg, post.get("timeline", []), site.get("timezone", "Asia/Kolkata"))
        if len(post.get("timeline", [])) >= 2 else None,
        "sources_r": [{**s, "n": n, "date": fmt_date(s["published"][:10], "short") if s.get("published") else ""}
                      for n, s in enumerate(post["sources"], 1)],
        "url_path": f"posts/{post['slug']}/",
        "dek_plain": re.sub(r"\s*\[S\d+\]", "", post["dek"]),
    }


def dual(fn, *args) -> Markup:
    """Draw a visual twice: a wide layout for desktop and a narrow one for phones (CSS shows one)."""
    return Markup(f'<div class="viz-wide">{fn(*args, W=WIDE)}</div><div class="viz-narrow">{fn(*args, W=NARROW)}</div>')


def tag_slug(tag: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", tag.lower()).strip("-")


def build(content_dir: Path | None = None, out_dir: Path | None = None, base_url: str | None = None) -> Path:
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
    (out_dir / ".nojekyll").write_text("", encoding="utf-8")

    env = Environment(loader=FileSystemLoader(config.SITE_DIR / "templates"), autoescape=select_autoescape(["html", "xml"]),
                      trim_blocks=True, lstrip_blocks=True)
    env.globals.update(site=site, base=base, origin=origin, year=datetime.now(timezone.utc).year, tag_slug=tag_slug)

    posts = [prepare(p, site) for p in load_posts(content_dir)]
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
        og_card(out_dir / f"og/{p['slug']}.png", p["headline"], site["name"], p["date_short"], f"{p['reading_minutes']} min read")
        newer = posts[i - 1] if i > 0 else None
        older = posts[i + 1] if i + 1 < len(posts) else None
        write(f"posts/{p['slug']}/index.html", env.get_template("post.html").render(
            post=p, newer=newer, older=older, page_title=p["headline"], description=p["dek_plain"],
            og_image=f"{base}og/{p['slug']}.png", canonical=p["url_path"], og_type="article"))
        rep = content_dir / "reports" / f"{p['date']}.json"
        if rep.exists():
            report = json.loads(rep.read_text(encoding="utf-8"))
            write(f"posts/{p['slug']}/verification/index.html", env.get_template("verification.html").render(
                post=p, report=report, page_title=f"Verification log · {p['date_short']}",
                description="Every sentence the verifier checked for this post, and what it removed.",
                og_image=f"{base}og/{p['slug']}.png", canonical=f"{p['url_path']}verification/", og_type="article"))

    write("index.html", env.get_template("index.html").render(
        latest=posts[0] if posts else None, earlier=posts[1:13], page_title=None, description=site["tagline"],
        og_image=f"{base}og/{posts[0]['slug']}.png" if posts else f"{base}og/default.png", canonical="", og_type="website"))
    by_month: dict[str, list[dict]] = {}
    for p in posts:
        by_month.setdefault(datetime.fromisoformat(p["date"]).strftime("%B %Y"), []).append(p)
    write("archive/index.html", env.get_template("archive.html").render(
        months=by_month, count=len(posts), page_title="Archive", description=f"Every {site['name']} post.",
        og_image=f"{base}og/default.png", canonical="archive/", og_type="website"))
    tag_list = sorted(tags.items(), key=lambda kv: (-len(kv[1]), kv[0]))
    write("tags/index.html", env.get_template("tags.html").render(
        tags=tag_list, page_title="Tags", description="Posts by topic.", og_image=f"{base}og/default.png",
        canonical="tags/", og_type="website", labels=CAT_LABEL))
    for t, ps in tags.items():
        write(f"tags/{tag_slug(t)}/index.html", env.get_template("tag.html").render(
            tag=t, label=CAT_LABEL.get(t, t), posts=ps, page_title=f"Tag: {CAT_LABEL.get(t, t)}",
            description=f"{site['name']} posts tagged {t}.", og_image=f"{base}og/default.png",
            canonical=f"tags/{tag_slug(t)}/", og_type="website"))
    write("about/index.html", env.get_template("about.html").render(
        page_title="How this blog is made", description="Five Minute AI is AI-assisted and generated automatically from linked sources.",
        og_image=f"{base}og/default.png", canonical="about/", og_type="website",
        sources=config.sources_config()["sources"], providers=site.get("providers", [])))
    write("404.html", env.get_template("404.html").render(page_title="Not found", description=site["tagline"],
                                                           og_image=f"{base}og/default.png", canonical="", og_type="website"))
    write("feed.xml", env.get_template("feed.xml").render(
        posts=posts[:20], now=format_datetime(datetime.now(timezone.utc)),
        rfc=lambda iso: format_datetime(datetime.fromisoformat(iso).replace(hour=6, tzinfo=timezone.utc))))
    urls = ["", "archive/", "tags/", "about/"] + [p["url_path"] for p in posts] + [f"tags/{tag_slug(t)}/" for t in tags]
    write("sitemap.xml", '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
          + "\n".join(f"  <url><loc>{html.escape(origin + base + u)}</loc></url>" for u in urls) + "\n</urlset>\n")
    write("robots.txt", f"User-agent: *\nAllow: /\nSitemap: {origin}{base}sitemap.xml\n")
    return out_dir
