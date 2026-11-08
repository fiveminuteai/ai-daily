"""The Reel's cover (8 Nov 2026, Pavan: "an attractive thumbnail with a catchy heading pulls more people").

Instagram shows a Reel on the profile grid and in feeds by its cover. Before this it took the frame at 3.5 s, which
on a duo Reel is one caption word. Now every Reel gets a designed still (reels/src/Cover.tsx): the card's cover
headline (written by the Reel desk, fact-checked like the hook) with its key words lit up, the cast, and the guest's
punchline in a speech bubble. Saved next to the video as reels/NN.jpg; fma/instagram.py sends it as cover_url."""
import json
import shutil
import subprocess
import uuid
from pathlib import Path

from .social import plain

BUBBLE_MAX = 42          # characters: a bubble longer than this covers the cast


def headline(card: dict) -> tuple[str, str]:
    """The cover headline and the words to light up: the card's cover line, or its hook when it has none."""
    title = plain(card.get("cover") or card.get("hook") or "").strip().rstrip(".")
    hi = (card.get("cover_hi") or "").strip() if card.get("cover") else ""
    return title, hi if hi and hi.lower() in title.lower() else ""


def bubble(card: dict) -> str | None:
    """The guest's punchline for the speech bubble: the last line if it is short, else the shortest that fits."""
    said = [plain(ln["text"]).strip() for ln in ((card.get("duo") or {}).get("lines") or []) if ln.get("who") == "guest"]
    if not said:
        return None
    if len(said[-1]) <= BUBBLE_MAX:
        return said[-1]
    fits = sorted((s for s in said if len(s) <= BUBBLE_MAX), key=len)
    return fits[0] if fits else None


def props(post: dict, sec: dict, guest: str) -> dict:
    from .duo_reel import CAT_NAMES
    card = sec.get("card") or {}
    title, hi = headline(card)
    return {"title": title, "hi": hi, "bubble": None if guest == "solo" else bubble(card), "guest": guest,
            "label": CAT_NAMES.get(sec.get("category", ""), "").upper()}


def render_cover(post: dict, sec: dict, out: Path, guest: str = "solo", lines: list | None = None) -> Path:
    """Draw the cover with Remotion and save it as a JPEG (what Instagram's cover_url takes). Raises on failure."""
    from PIL import Image
    from .duo_reel import REELS, remotion_ready
    if not remotion_ready():
        raise RuntimeError("Remotion is not installed")
    p = props(post, sec, guest)
    if not p["title"]:
        raise ValueError("no headline for the cover")
    job = REELS / "public" / "jobs" / uuid.uuid4().hex[:10]
    job.mkdir(parents=True)
    try:
        (job / "props.json").write_text(json.dumps(p, ensure_ascii=False), encoding="utf-8")
        png = job / "cover.png"
        r = subprocess.run([shutil.which("npx"), "remotion", "still", "src/index.ts", "Cover", str(png.resolve()),
                            f"--props={job / 'props.json'}", "--log=error"],
                           cwd=REELS, capture_output=True, text=True, timeout=300)
        if r.returncode != 0 or not png.exists():
            raise RuntimeError(f"remotion still failed: {(r.stderr or r.stdout)[-500:]}")
        out.parent.mkdir(parents=True, exist_ok=True)
        Image.open(png).convert("RGB").save(out, "JPEG", quality=90, optimize=True)
        return out
    finally:
        shutil.rmtree(job, ignore_errors=True)
