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
        """The item to cite first: a primary source if one exists, else the strongest item. Once article text has
        been fetched, an item with too little readable text (a JavaScript-built page, say) never leads if another
        item about the same event has a full article."""
        readable = [i for i in self.items if len(i.text) >= 600]
        if any(i.text for i in self.items) and readable:
            pool = [i for i in readable if i.primary] or readable
            return max(pool, key=lambda i: (i.weight, len(i.text)))
        prim = [i for i in self.items if i.primary]
        pool = prim or self.items
        return max(pool, key=lambda i: (i.weight, len(i.text or i.summary)))

    @property
    def title(self) -> str:
        return self.lead.title

    @property
    def publishers(self) -> set[str]:
        return {i.outlet or i.source_name for i in self.items}
