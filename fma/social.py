"""Ready-to-paste social posts for each day's post: texts for X, LinkedIn and Instagram, and a portrait image card
for Instagram. Everything here is built from the post's verified fields only (headline, "what happened" bullets),
so a social post never says more than the checked post does."""
from __future__ import annotations

import re
from pathlib import Path

from .verify import CITE_RE
from .visuals import TOPIC_RGB, _font

X_LIMIT = 280
X_URL_LEN = 23           # X counts every link as 23 characters, whatever its length
HASHTAGS_LINKEDIN = "#AI #ArtificialIntelligence #MachineLearning #DataEngineering"
HASHTAGS_INSTAGRAM = "#ai #ainews #artificialintelligence #tech #technews"     # five at most (Instagram, Dec 2025)


def plain(text: str) -> str:
    """Post text as plain characters: no [S1] markers, and the non-breaking hyphen and narrow space some fonts
    and apps draw as boxes replaced by ordinary ones."""
    text = CITE_RE.sub("", text).replace("‑", "-").replace(" ", " ").replace(" ", " ")
    return re.sub(r"\s+([.,;:!?])", r"\1", re.sub(r"\s+", " ", text)).strip()


def x_length(text: str) -> int:
    """Length as X counts it: each URL is 23 characters."""
    return len(re.sub(r"https?://\S+", "x" * X_URL_LEN, text))


# 8 Nov 2026 (growth plan): Instagram counts sends per reach as its strongest signal for showing a Reel to people
# who don't follow us, and caps hashtags at five (Dec 2025). So each caption asks for a send, and its hashtags
# name the story's players instead of a fixed list.
SEND_LINES = ["Know someone who follows AI? Send this to them.",
              "Send this to the friend who keeps up with AI.",
              "Send this to your group chat's AI person."]
TOPIC_TAGS = [(r"\bopenai|chatgpt|gpt-?\d", ["#openai", "#chatgpt"]), (r"\banthropic|claude\b", ["#anthropic", "#claude"]),
              (r"\bgoogle|gemini|deepmind", ["#google", "#gemini"]), (r"\bnvidia\b", ["#nvidia"]),
              (r"\bmicrosoft|copilot\b", ["#microsoft"]), (r"\bmeta\b|\bllama\b", ["#meta"]),
              (r"\bapple|siri\b", ["#apple"]), (r"\bamazon|alexa|aws\b", ["#amazon"]), (r"\bxai\b|\bgrok\b", ["#xai"])]
BASE_TAGS = ["#ai", "#ainews"]
FILL_TAGS = ["#tech", "#technews", "#artificialintelligence"]
MAX_TAGS = 5


def reel_hashtags(section: dict) -> str:
    """Five at most: #ai #ainews, the story's companies, then general tech tags to fill."""
    text = (section.get("title", "") + " " + plain(section.get("card", {}).get("hook", ""))).lower()
    tags = list(BASE_TAGS)
    for pat, add in TOPIC_TAGS:
        if re.search(pat, text):
            tags += [t for t in add if t not in tags]
    tags = tags[:MAX_TAGS]
    tags += [t for t in FILL_TAGS if t not in tags][:MAX_TAGS - len(tags)]
    return " ".join(tags)


def send_line(section: dict) -> str:
    import zlib
    return SEND_LINES[zlib.crc32(plain(section.get("card", {}).get("hook", "")).encode()) % len(SEND_LINES)]


def reel_caption(section: dict, site: dict) -> str:
    """Caption for one story's Reel, from its fact-checked card only."""
    card = section["card"]
    domain = re.sub(r"^https?://|/$", "", site["base_url"])
    lines = "\n".join(f"• {plain(p)}" for p in card["points"])
    take = ""
    if card.get("take"):
        take = f"\n\n{'Do this' if card.get('take_kind') == 'do' else 'Our read'}: {plain(card['take'])}"
    if card.get("ask"):
        take += f"\n\nYour take: {plain(card['ask'])} Tell us in the comments."
    return (f"{plain(card['hook'])}\n\n{lines}{take}\n\n{send_line(section)}\n\n"
            f"Full story, every claim sourced: link in bio ({domain})\n\n{reel_hashtags(section)}")


def share_texts(post: dict, site: dict) -> dict[str, str]:
    url = f"{site['base_url']}posts/{post['slug']}/"
    head = plain(post["headline"])
    bullets = [plain(b) for b in post["what_happened"]]

    # X: the headline, as many bullets as fit, the link
    x = f"{head}\n\n{url}"
    for n in range(len(bullets), 0, -1):
        trial = f"{head}\n\n" + "\n".join(f"• {b}" for b in bullets[:n]) + f"\n\n{url}"
        if x_length(trial) <= X_LIMIT:
            x = trial
            break

    lines = "\n".join(f"• {b}" for b in bullets)
    linkedin = (f"Today in AI: {head}\n\n{lines}\n\n"
                f"Every claim is linked to its source. The full five-minute read:\n{url}\n\n{HASHTAGS_LINKEDIN}")
    # Instagram doesn't make links in captions clickable, so point to the profile link instead
    domain = re.sub(r"^https?://|/$", "", site["base_url"])
    instagram = (f"{head}\n\n{lines}\n\n"
                 f"Full five-minute read, every claim sourced: link in bio ({domain})\n\n{HASHTAGS_INSTAGRAM}")
    return {"x": x, "linkedin": linkedin, "instagram": instagram, "url": url}


def instagram_card(path: Path, post: dict, site_name: str, date_label: str, topics: list[str] | None = None) -> None:
    """A 1080x1350 portrait card (Instagram's tallest feed size): the headline and the three "what happened" bullets."""
    from PIL import Image, ImageDraw

    W, H, M = 1080, 1350, 84
    bg, ink, ink2, muted, accent = (11, 16, 34), (237, 240, 250), (195, 202, 226), (149, 160, 196), (255, 184, 107)
    img = Image.new("RGB", (W, H), bg)
    glow = Image.new("RGB", (W, H), bg)
    gd = ImageDraw.Draw(glow)
    for k in range(18, 0, -1):
        c = tuple(int(bg[j] + (TOPIC_RGB["models"][j] - bg[j]) * 0.20 * (1 - k / 18)) for j in range(3))
        gd.ellipse([W - 560 - k * 18, -420 - k * 14, W + 300 + k * 18, 320 + k * 14], fill=c)
    img = Image.blend(img, glow, 1.0)
    d = ImageDraw.Draw(img)
    cols = [TOPIC_RGB[t] for t in (topics or []) if t in TOPIC_RGB] or list(TOPIC_RGB.values())
    seg = W / len(cols)
    for n, c in enumerate(cols):
        d.rectangle([int(n * seg), 0, int((n + 1) * seg), 12], fill=c)

    def wrap(text: str, font, max_w: float) -> list[str]:
        # a number stays on the line with the word after it ("29 October", "40 percent")
        words = re.sub(r"(\d) (?=\S)", "\\1\u00a0", text).split(" ")
        lines, cur = [], ""
        for word in words:
            trial = f"{cur} {word}".strip()
            if d.textlength(trial.replace("\u00a0", " "), font=font) <= max_w or not cur:
                cur = trial
            else:
                lines.append(cur)
                cur = word
        return [ln.replace("\u00a0", " ") for ln in lines + ([cur] if cur else [])]

    d.text((M, 78), site_name.upper(), font=_font("sans_bold", 30), fill=accent)
    d.text((M, 120), date_label, font=_font("sans", 28), fill=muted)

    head = plain(post["headline"])
    bullets = [plain(b) for b in post["what_happened"]]
    top, bottom = 200, H - 150                      # room between the date line and the footer
    # shrink the headline first, then the bullets, until everything fits
    for hs, bs in ((88, 40), (82, 38), (76, 36), (72, 34), (66, 33), (60, 32), (56, 31), (52, 30), (48, 29), (44, 28), (40, 27), (36, 26)):
        hf, bf = _font("serif", hs), _font("sans", bs)
        hl = wrap(head, hf, W - 2 * M)
        bl = [wrap(b, bf, W - 2 * M - 44) for b in bullets]
        need = len(hl) * hs * 1.12 + 56 + sum(len(x) * bs * 1.38 + 30 for x in bl)
        orphan = len(hl) > 1 and " " not in hl[-1]      # one lonely word on the headline's last line
        if need <= bottom - top and not orphan:
            break
    y = top + int(max(0, bottom - top - need) * 0.35)   # leftover space mostly below, so the block sits high
    for line in hl:
        d.text((M, y), line, font=hf, fill=ink)
        y += int(hs * 1.12)
    y += 56
    bullet_cols = [TOPIC_RGB[t] for t in (topics or []) if t in TOPIC_RGB] or [accent]
    for n, lines in enumerate(bl):
        c = bullet_cols[n % len(bullet_cols)]
        d.rounded_rectangle([M, y + int(bs * .32), M + 14, y + int(bs * .32) + 14], radius=4, fill=c)
        for line in lines:
            d.text((M + 44, y), line, font=bf, fill=ink2)
            y += int(bs * 1.38)
        y += 30

    d.line([M, H - 128, W - M, H - 128], fill=(36, 48, 88), width=2)
    d.text((M, H - 98), "Every claim linked to its source", font=_font("sans", 28), fill=muted)
    d.text((M, H - 60), "Full read: link in bio", font=_font("sans_bold", 28), fill=accent)
    cx, cy, r = W - M - 40, H - 72, 38             # the brand mark, as on the site
    d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=accent, width=7)
    d.pieslice([cx - r + 3, cy - r + 3, cx + r - 3, cy + r - 3], start=-90, end=-30, fill=accent)
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path, "PNG", optimize=True)
