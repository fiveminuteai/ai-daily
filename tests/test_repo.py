"""Repository hygiene: clean UTF-8 everywhere, and no secrets in tracked config."""
import re

from conftest import ROOT

TEXT = {".py", ".yaml", ".yml", ".html", ".css", ".xml", ".svg", ".md", ".json", ".txt"}


def files():
    for p in ROOT.rglob("*"):
        if p.is_file() and p.suffix in TEXT and not {".git", "public", ".pytest_cache", "__pycache__"} & set(p.parts):
            yield p


def test_utf8_without_bom_or_mojibake():
    for p in files():
        raw = p.read_bytes()
        assert not raw.startswith(b"\xef\xbb\xbf"), f"BOM in {p}"
        text = raw.decode("utf-8")
        assert not re.search("\u00c2|\u00e2\u20ac|\u00c3[\u0080-\u00bf]", text), f"mojibake in {p}"


def test_no_api_keys_in_files():
    pat = re.compile(r"(AIza[0-9A-Za-z_\-]{30,}|gsk_[0-9A-Za-z]{20,}|sk-or-[0-9A-Za-z\-]{20,}|ghp_[0-9A-Za-z]{30,})")
    for p in files():
        assert not pat.search(p.read_text(encoding="utf-8")), f"possible secret in {p}"
