"""Screenshot harness for the design passes (dev tool, not used by the daily job).

Serves nothing itself: point it at a running preview (python -m http.server -d public) and it renders each page
inside an iframe of the exact viewport size, scrolled to top / middle / bottom, using headless Edge or Chrome.

    python scripts/shots.py http://localhost:8765 <served_dir> <out_dir> /  /posts/<slug>/  /archive/
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from PIL import Image

BROWSERS = [r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files\Google\Chrome\Application\chrome.exe", "/usr/bin/chromium", "/usr/bin/google-chrome"]
SIZES = {"desktop": (1440, 900), "phone": (390, 844)}
HARNESS = """<!doctype html><html><body style="margin:0;background:#000">
<iframe id="f" src="{url}" style="width:{w}px;height:{h}px;border:0;display:block"></iframe>
<script>document.getElementById("f").onload=function(){{var d=this.contentWindow,doc=d.document.documentElement;
{theme}setTimeout(function(){{var max=doc.scrollHeight-{h};d.scrollTo(0,Math.round(max*{frac}))}},300)}}</script></body></html>"""


def browser() -> str:
    for b in BROWSERS:
        if Path(b).exists():
            return b
    raise SystemExit("no Edge/Chrome found")


def shoot(base: str, served: Path, out: Path, paths: list[str], themes=("dark", "light")) -> list[Path]:
    out.mkdir(parents=True, exist_ok=True)
    made = []
    for path in paths:
        name = path.strip("/").replace("/", "_") or "home"
        for theme in themes:
            for size, (w, h) in SIZES.items():
                for pos, frac in (("top", 0), ("mid", 0.5), ("bottom", 1)):
                    th = f'try{{d.localStorage.setItem("theme","{theme}")}}catch(e){{}}doc.dataset.theme="{theme}";'
                    page = HARNESS.format(url=base + path, w=w, h=h, frac=frac, theme=th)
                    hp = served / "_harness.html"
                    hp.write_text(page, encoding="utf-8")
                    png = out / f"{name}-{theme}-{size}-{pos}.png"
                    win_w = max(w, 520)       # headless windows can't go narrower; the iframe keeps the real width
                    # the harness is served by the same preview server, so the iframe is same-origin
                    try:
                        subprocess.run([browser(), "--headless=new", "--disable-gpu", "--hide-scrollbars",
                                        "--force-device-scale-factor=1", "--virtual-time-budget=2500",
                                        f"--window-size={win_w},{h}", f"--screenshot={png}", base + "/_harness.html"],
                                       capture_output=True, timeout=40)
                    except subprocess.TimeoutExpired:
                        pass          # headless Edge sometimes writes the file and then fails to exit
                    if png.exists():
                        Image.open(png).crop((0, 0, w, h)).save(png)
                        made.append(png)
    return made


if __name__ == "__main__":
    base, served, out, *paths = sys.argv[1:]
    for p in shoot(base.rstrip("/"), Path(served), Path(out), paths or ["/"]):
        print(p)
