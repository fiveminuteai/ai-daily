"""Original visuals, generated from the post's own verified data. Never copied from a source site.

SVGs are inlined into the page and coloured with CSS classes, so they follow the light/dark theme."""
from __future__ import annotations

import html
import textwrap
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

CAT_LABEL = {"models": "Models", "research": "Research", "products": "Products", "tools": "Tools",
             "policy": "Policy & safety", "impact": "Real-world impact"}


def esc(s) -> str:
    return html.escape(str(s), quote=True)


def _wrap(text: str, width: int, max_lines: int) -> list[str]:
    lines = textwrap.wrap(text, width=width) or [""]
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        lines[-1] = lines[-1].rstrip(" ,.;:") + "…"
    return lines


def timeline_svg(entries: list[dict], tz: str = "Asia/Kolkata") -> str:
    """entries: [{time: iso, title, publisher, category}] -> vertical timeline, oldest first."""
    zone = ZoneInfo(tz)
    rows = []
    for e in entries:
        try:
            t = datetime.fromisoformat(e["time"]).astimezone(zone) if e.get("time") else None
        except ValueError:
            t = None
        rows.append((t, e))
    rows.sort(key=lambda r: r[0] or datetime.max.replace(tzinfo=zone))
    W, top, row_h = 640, 56, 84
    H = top + row_h * len(rows) + 8
    out = [f'<svg class="viz" viewBox="0 0 {W} {H}" role="img" aria-labelledby="tl-t tl-d" xmlns="http://www.w3.org/2000/svg">',
           '<title id="tl-t">When today\'s stories broke</title>',
           f'<desc id="tl-d">Timeline of the {len(rows)} stories in this post, by the time each source published, in India time.</desc>',
           f'<text class="viz-kicker" x="0" y="20">WHEN TODAY\'S STORIES BROKE · IST</text>',
           f'<line class="viz-rule" x1="132" y1="{top - 10}" x2="132" y2="{H - 14}"/>']
    for n, (t, e) in enumerate(rows):
        y = top + n * row_h + 14
        day = t.strftime("%a %d %b") if t else "date n/a"
        clock = t.strftime("%H:%M") if t else ""
        out.append(f'<text class="viz-time" x="116" y="{y + 4}" text-anchor="end">{esc(clock)}</text>')
        out.append(f'<text class="viz-small" x="116" y="{y + 22}" text-anchor="end">{esc(day)}</text>')
        out.append(f'<circle class="viz-dot" cx="132" cy="{y}" r="6"/>')
        lines = _wrap(e["title"], 52, 2)
        for k, line in enumerate(lines):
            out.append(f'<text class="viz-label" x="152" y="{y + 5 + k * 20}">{esc(line)}</text>')
        meta = f'{CAT_LABEL.get(e.get("category"), "")} · {e.get("publisher", "")}'.strip(" ·")
        out.append(f'<text class="viz-small" x="152" y="{y + 5 + len(lines) * 20 + 2}">{esc(meta)}</text>')
    out.append("</svg>")
    return "\n".join(out)


def _fmt(v: float) -> str:
    return f"{v:,.2f}".rstrip("0").rstrip(".") if v % 1 else f"{int(v):,}"


def bar_chart_svg(chart: dict, source_label: str) -> str:
    bars = chart["bars"][:8]
    W, left, right, top, bh, gap = 640, 190, 70, 52, 26, 14
    H = top + len(bars) * (bh + gap) + 34
    vmax = max(b["value"] for b in bars) or 1
    span = W - left - right
    unit = chart.get("unit", "")
    out = [f'<svg class="viz" viewBox="0 0 {W} {H}" role="img" aria-labelledby="bc-t" xmlns="http://www.w3.org/2000/svg">',
           f'<title id="bc-t">{esc(chart["title"])}</title>',
           f'<text class="viz-kicker" x="0" y="20">{esc(chart["title"].upper())}</text>']
    top_val = max(b["value"] for b in bars)
    for n, b in enumerate(bars):
        y = top + n * (bh + gap)
        w = max(3, span * b["value"] / vmax)
        cls = "viz-bar-hi" if b["value"] == top_val else "viz-bar"
        out.append(f'<text class="viz-label" x="{left - 12}" y="{y + bh / 2 + 5}" text-anchor="end">{esc(_wrap(b["label"], 24, 1)[0])}</text>')
        out.append(f'<rect class="{cls}" x="{left}" y="{y}" width="{w:.1f}" height="{bh}" rx="3"/>')
        out.append(f'<text class="viz-time" x="{left + w + 8:.1f}" y="{y + bh / 2 + 5}">{esc(_fmt(b["value"]))}{esc(unit if unit in ("%",) else "")}</text>')
    unit_note = f" · unit: {unit}" if unit and unit != "%" else ""
    out.append(f'<text class="viz-small" x="0" y="{H - 8}">Figures as reported by {esc(source_label)}{esc(unit_note)}</text>')
    out.append("</svg>")
    return "\n".join(out)


def flow_svg(diagram: dict, source_label: str) -> str:
    steps = diagram["steps"]
    W, bw, bh, gap, top = 640, 440, 48, 30, 44
    x = (W - bw) / 2
    H = top + len(steps) * (bh + gap) + 10
    out = [f'<svg class="viz" viewBox="0 0 {W} {H}" role="img" aria-labelledby="fl-t" xmlns="http://www.w3.org/2000/svg">',
           f'<title id="fl-t">{esc(diagram["title"])}</title>',
           '<defs><marker id="arrow" viewBox="0 0 10 10" refX="5" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">'
           '<path class="viz-arrow" d="M0 0 L10 5 L0 10 z"/></marker></defs>',
           f'<text class="viz-kicker" x="0" y="20">{esc(diagram["title"].upper())}</text>']
    for n, s in enumerate(steps):
        y = top + n * (bh + gap)
        out.append(f'<rect class="viz-box{" viz-box-hi" if n == len(steps) - 1 else ""}" x="{x}" y="{y}" width="{bw}" height="{bh}" rx="10"/>')
        out.append(f'<text class="viz-small" x="{x + 16}" y="{y + bh / 2 + 5}">{n + 1:02d}</text>')
        out.append(f'<text class="viz-label" x="{W / 2}" y="{y + bh / 2 + 6}" text-anchor="middle">{esc(_wrap(s, 44, 1)[0])}</text>')
        if n < len(steps) - 1:
            out.append(f'<line class="viz-rule" x1="{W / 2}" y1="{y + bh + 3}" x2="{W / 2}" y2="{y + bh + gap - 5}" marker-end="url(#arrow)"/>')
    out.append(f'<text class="viz-small" x="0" y="{H - 2}">Based on {esc(source_label)}</text>')
    out.append("</svg>")
    return "\n".join(out)


# ---------------------------------------------------------------- Open Graph card (PNG; social sites don't render SVG)

FONT_CANDIDATES = {
    "serif": ["C:/Windows/Fonts/georgiab.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf",
              "/System/Library/Fonts/Supplemental/Georgia Bold.ttf"],
    "sans": ["C:/Windows/Fonts/segoeui.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
             "/System/Library/Fonts/Supplemental/Arial.ttf"],
    "sans_bold": ["C:/Windows/Fonts/segoeuib.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                  "/System/Library/Fonts/Supplemental/Arial Bold.ttf"],
}


def _font(kind: str, size: int):
    from PIL import ImageFont

    for path in FONT_CANDIDATES[kind]:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default(size=size)


def og_card(path: Path, headline: str, site_name: str, date_label: str, kicker: str = "5 min read") -> None:
    from PIL import Image, ImageDraw

    W, H = 1200, 630
    bg, ink, muted, accent = (20, 20, 19), (240, 237, 230), (160, 155, 145), (232, 121, 72)
    img = Image.new("RGB", (W, H), bg)
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, 14, H], fill=accent)
    d.text((80, 70), site_name.upper(), font=_font("sans_bold", 30), fill=accent)
    d.text((80, 112), f"{date_label}  ·  {kicker}", font=_font("sans", 28), fill=muted)
    size = 74
    while size > 44:
        f = _font("serif", size)
        width_chars = max(12, int(1040 / (size * 0.52)))
        lines = textwrap.wrap(headline, width=width_chars)
        if len(lines) <= 4:
            break
        size -= 6
    lines = lines[:4]
    y = 210
    for line in lines:
        d.text((80, y), line, font=f, fill=ink)
        y += int(size * 1.18)
    d.text((80, H - 80), "Every claim linked to its source.", font=_font("sans", 26), fill=muted)
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path, "PNG", optimize=True)
