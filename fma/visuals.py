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


WIDE, NARROW = 640, 360     # two layouts: desktop column and phone width, so text stays readable on both


def timeline_svg(entries: list[dict], tz: str = "Asia/Kolkata", W: int = WIDE) -> str:
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
    narrow = W < 500
    axis = 82 if narrow else 132          # x of the vertical line
    text_x = axis + 18
    chars = int((W - text_x) / 8.4)       # ~8.4 units per character at 15.5px
    top, row_h = 52, 84 if not narrow else 92
    H = top + row_h * len(rows) + 4
    uid = f"tl{W}"
    out = [f'<svg class="viz" viewBox="0 0 {W} {H}" role="img" aria-labelledby="{uid}-t {uid}-d" xmlns="http://www.w3.org/2000/svg">',
           f'<title id="{uid}-t">When today\'s stories broke</title>',
           f'<desc id="{uid}-d">Timeline of the {len(rows)} stories in this post, by the time each source published, in India time.</desc>',
           f'<text class="viz-kicker" x="0" y="20">WHEN TODAY\'S STORIES BROKE · IST</text>',
           f'<line class="viz-rule" x1="{axis}" y1="{top - 10}" x2="{axis}" y2="{H - 14}"/>']
    for n, (t, e) in enumerate(rows):
        y = top + n * row_h + 14
        day = (t.strftime("%d %b") if narrow else t.strftime("%a %d %b")).lstrip("0") if t else "n/a"
        clock = t.strftime("%H:%M") if t else ""
        out.append(f'<text class="viz-time" x="{axis - 16}" y="{y + 4}" text-anchor="end">{esc(clock)}</text>')
        out.append(f'<text class="viz-small" x="{axis - 16}" y="{y + 22}" text-anchor="end">{esc(day)}</text>')
        out.append(f'<circle class="viz-dot" cx="{axis}" cy="{y}" r="6"/>')
        lines = _wrap(e["title"], chars, 2)
        for k, line in enumerate(lines):
            out.append(f'<text class="viz-label" x="{text_x}" y="{y + 5 + k * 20}">{esc(line)}</text>')
        meta = f'{CAT_LABEL.get(e.get("category"), "")} · {e.get("publisher", "")}'.strip(" ·")
        out.append(f'<text class="viz-small" x="{text_x}" y="{y + 5 + len(lines) * 20 + 2}">{esc(_wrap(meta, chars + 8, 1)[0])}</text>')
    out.append("</svg>")
    return "\n".join(out)


def _fmt(v: float) -> str:
    return f"{v:,.2f}".rstrip("0").rstrip(".") if v % 1 else f"{int(v):,}"


def bar_chart_svg(chart: dict, source_label: str = "", W: int = WIDE) -> str:
    bars = chart["bars"][:8]
    narrow = W < 500
    left, right, top, bh, gap = (118 if narrow else 190), (62 if narrow else 70), 52, 26, 14
    H = top + len(bars) * (bh + gap) + (20 if chart.get("unit") not in ("", "%", None) else -gap + 4)
    vmax = max(b["value"] for b in bars) or 1
    span = W - left - right
    unit = chart.get("unit", "")
    uid = f"bc{W}"
    title_lines = _wrap(chart["title"].upper(), 40 if narrow else 70, 2)
    shift = 18 * (len(title_lines) - 1)
    top += shift
    H += shift
    out = [f'<svg class="viz" viewBox="0 0 {W} {H}" role="img" aria-labelledby="{uid}-t" xmlns="http://www.w3.org/2000/svg">',
           f'<title id="{uid}-t">{esc(chart["title"])}</title>']
    out += [f'<text class="viz-kicker" x="0" y="{20 + 18 * k}">{esc(t)}</text>' for k, t in enumerate(title_lines)]
    top_val = max(b["value"] for b in bars)
    for n, b in enumerate(bars):
        y = top + n * (bh + gap)
        w = max(3, span * b["value"] / vmax)
        cls = "viz-bar-hi" if b["value"] == top_val else "viz-bar"
        out.append(f'<text class="viz-label" x="{left - 12}" y="{y + bh / 2 + 5}" text-anchor="end">{esc(_wrap(b["label"], 13 if narrow else 24, 1)[0])}</text>')
        out.append(f'<rect class="{cls}" x="{left}" y="{y}" width="{w:.1f}" height="{bh}" rx="3"/>')
        out.append(f'<text class="viz-time" x="{left + w + 8:.1f}" y="{y + bh / 2 + 5}">{esc(_fmt(b["value"]))}{esc(unit if unit in ("%",) else "")}</text>')
    if unit and unit != "%":
        out.append(f'<text class="viz-small" x="0" y="{H - 8}">Unit: {esc(unit)}</text>')
    out.append("</svg>")
    return "\n".join(out)


def flow_svg(diagram: dict, source_label: str = "", W: int = WIDE) -> str:
    steps = diagram["steps"]
    narrow = W < 500
    bw, bh, gap = (W - 8 if narrow else 440), 48, 30
    x = (W - bw) / 2
    uid = f"fl{W}"
    title_lines = _wrap(diagram["title"].upper(), 40 if narrow else 70, 2)
    top = 44 + 18 * (len(title_lines) - 1)
    H = top + len(steps) * (bh + gap) - gap + 4
    out = [f'<svg class="viz" viewBox="0 0 {W} {H}" role="img" aria-labelledby="{uid}-t" xmlns="http://www.w3.org/2000/svg">',
           f'<title id="{uid}-t">{esc(diagram["title"])}</title>',
           f'<defs><marker id="{uid}-arrow" viewBox="0 0 10 10" refX="5" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">'
           '<path class="viz-arrow" d="M0 0 L10 5 L0 10 z"/></marker></defs>']
    out += [f'<text class="viz-kicker" x="0" y="{20 + 18 * k}">{esc(t)}</text>' for k, t in enumerate(title_lines)]
    for n, s in enumerate(steps):
        y = top + n * (bh + gap)
        out.append(f'<rect class="viz-box{" viz-box-hi" if n == len(steps) - 1 else ""}" x="{x}" y="{y}" width="{bw}" height="{bh}" rx="10"/>')
        out.append(f'<text class="viz-small" x="{x + 14}" y="{y + bh / 2 + 5}">{n + 1:02d}</text>')
        out.append(f'<text class="viz-label" x="{W / 2 + (10 if narrow else 0)}" y="{y + bh / 2 + 6}" text-anchor="middle">{esc(_wrap(s, 36 if narrow else 44, 1)[0])}</text>')
        if n < len(steps) - 1:
            out.append(f'<line class="viz-rule" x1="{W / 2}" y1="{y + bh + 3}" x2="{W / 2}" y2="{y + bh + gap - 5}" marker-end="url(#{uid}-arrow)"/>')
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
    def wrap_px(text: str, font, max_w: float) -> list[str]:
        lines, cur = [], ""
        for word in text.split():
            trial = f"{cur} {word}".strip()
            if d.textlength(trial, font=font) <= max_w or not cur:
                cur = trial
            else:
                lines.append(cur)
                cur = word
        return lines + ([cur] if cur else [])

    size = 76
    while True:
        f = _font("serif", size)
        lines = wrap_px(headline, f, 1000)
        if len(lines) <= 4 or size <= 44:
            break
        size -= 4
    if len(lines) > 4:
        lines = lines[:4]
        lines[-1] = lines[-1].rstrip(" ,.;:") + "…"
    y = 210
    for line in lines:
        d.text((80, y), line, font=f, fill=ink)
        y += int(size * 1.18)
    d.text((80, H - 80), "Every claim linked to its source.", font=_font("sans", 26), fill=muted)
    # brand mark: a clock face with the first five minutes filled in
    cx, cy, r = W - 110, H - 105, 44
    d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=accent, width=7)
    d.pieslice([cx - r + 3, cy - r + 3, cx + r - 3, cy + r - 3], start=-90, end=-60, fill=accent)
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path, "PNG", optimize=True)
