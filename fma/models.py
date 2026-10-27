"""Plain data types shared across the pipeline."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass
class Item:
    """One thing a source published: a blog post, a paper, an HN story, a repo."""

    source_id: str
    source_name: str
    title: str
    url: str
    published: datetime | None
    summary: str = ""
    category: str = "products"
    weight: float = 1.0
    primary: bool = False
    points: int = 0          # HN points, HF upvotes or GitHub stars
    comments_url: str = ""   # HN discussion link, kept for context only
    text: str = ""           # full article text once extracted
    outlet: str = ""         # who counts as the publisher for "how many outlets covered it" (arXiv lists = one)
    strict_match: bool = False  # only cluster by URL or near-identical title (paper feeds)
    max_age_h: int = 0       # per-source freshness window; 0 = use the pipeline default


@dataclass
class Story:
    """A cluster of items about the same event."""

    items: list[Item]
    score: float = 0.0
    interest: float | None = None   # the editor pass's 0-10 rating, when it ran
    category: str = "products"

    @property
    def lead(self) -> Item:
        """The item to cite first: a primary source if one exists, else the strongest item."""
        prim = [i for i in self.items if i.primary]
        pool = prim or self.items
        return max(pool, key=lambda i: (i.weight, len(i.text or i.summary)))

    @property
    def title(self) -> str:
        return self.lead.title

    @property
    def publishers(self) -> set[str]:
        return {i.outlet or i.source_name for i in self.items}
