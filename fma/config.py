"""Paths and config loading."""
from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = ROOT / "config"
CONTENT_DIR = ROOT / "content"
POSTS_DIR = CONTENT_DIR / "posts"
REPORTS_DIR = CONTENT_DIR / "reports"
DATA_DIR = ROOT / "data"
SITE_DIR = ROOT / "site"
OUT_DIR = ROOT / "public"


def load_yaml(name: str) -> dict:
    with open(CONFIG_DIR / name, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def site_config() -> dict:
    return load_yaml("site.yaml")


def sources_config() -> dict:
    return load_yaml("sources.yaml")
