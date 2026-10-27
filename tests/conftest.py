"""Shared fakes: no test touches the network or a real model."""
from __future__ import annotations

import json
import re
import shutil
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

NOW = datetime(2026, 10, 27, 1, 0, tzinfo=timezone.utc)


class FakeResponse:
    def __init__(self, status=200, content=b"", headers=None, json_data=None):
        self.status_code = status
        self.content = content if isinstance(content, bytes) else content.encode()
        self.text = self.content.decode("utf-8", "replace")
        self.headers = headers or {"content-type": "text/html"}
        self._json = json_data
        self.ok = status < 400

    def json(self):
        return self._json if self._json is not None else json.loads(self.text)

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def close(self):
        pass


class FakeHttp:
    """Maps URL prefixes to responses. Unknown URLs return 404."""

    def __init__(self, routes: dict):
        self.routes = routes
        self.calls: list[str] = []

    def _find(self, url):
        self.calls.append(url)
        for prefix, resp in self.routes.items():
            if url.startswith(prefix):
                return resp() if callable(resp) else resp
        return FakeResponse(404, b"not found")

    def get(self, url, **kw):
        return self._find(url)

    def head(self, url, **kw):
        return self._find(url)


class FakeChain:
    """Returns queued JSON replies in order, like a model would. Fact-check prompts are answered automatically:
    every claim supported, with a real quote from the prompt's sources as evidence, except ids listed in `flags`."""

    def __init__(self, replies: list[dict], flags: dict | None = None):
        self.replies = list(replies)
        self.flags = flags or {}
        self.prompts: list[str] = []
        self.used = "fake:model"

    def __bool__(self):
        return True

    def _check_reply(self, user: str) -> dict:
        ids = re.findall(r"^(C\d+): ", user, flags=re.M)
        src = user.split("\n\nSOURCES\n", 1)[1]
        first_text = [ln for ln in src.splitlines() if ln.strip() and not ln.startswith("[S")][0]
        evidence = " ".join(first_text.split()[:6])
        return {"checks": [{"id": i, "evidence": evidence, "supported": i not in self.flags,
                            "reason": self.flags.get(i, "ok")} for i in ids]}

    def ask_json(self, system, user, temperature=0.3, careful=False):
        self.prompts.append(user)
        if user.startswith("Fact-check each claim"):
            return self._check_reply(user)
        if user.startswith("READERS:"):          # editor pass: neutral scores, keeps the canned replies in order
            return {"scores": []}
        if not self.replies:
            raise RuntimeError("no more replies")
        r = self.replies.pop(0)
        if isinstance(r, Exception):
            raise r
        return r


def rss(items: list[tuple[str, str, datetime, str]]) -> bytes:
    body = "".join(
        f"<item><title>{t}</title><link>{u}</link><pubDate>{d.strftime('%a, %d %b %Y %H:%M:%S +0000')}</pubDate>"
        f"<description><![CDATA[<p>{s}</p>]]></description></item>" for t, u, d, s in items)
    return f'<?xml version="1.0"?><rss version="2.0"><channel><title>x</title>{body}</channel></rss>'.encode()


ARTICLE_A = """<html><body><nav>menu</nav><article><h1>Acme releases Nova-2</h1>
<p>Acme said on Monday that Nova-2 scores 87.5% on the MMLU benchmark, up from 81.2% for Nova-1.</p>
<p>The company said the model costs $2 per million tokens and is available to developers in 40 countries starting today.</p>
<p>Chief scientist Maria Lopez said: "We built Nova-2 to be cheaper and more careful."</p>
<p>The release includes a smaller version called Nova-2 Mini for phones and laptops, which runs without an internet connection.</p>
</article><footer>legal</footer></body></html>"""

ARTICLE_B = """<html><body><article><h1>EU fines DataCorp</h1>
<p>The European Commission fined DataCorp 300 million euros on Monday for training models on user photos without consent.</p>
<p>Regulators said DataCorp must delete the affected training data within 90 days under the AI Act and privacy law.</p>
<p>DataCorp said it would appeal the decision and that it disagreed with the Commission's reading of the rules.</p>
</article></body></html>"""

ARTICLE_C = """<html><body><article><h1>Robots learn to fold laundry</h1>
<p>Researchers at Stanford University trained a robot arm to fold shirts using 1,200 hours of video demonstrations.</p>
<p>The team reported a success rate of 72% on unseen shirts, compared with 41% for the previous best method.</p>
<p>The paper says the approach still struggles with thin fabrics and the robot needs about two minutes per shirt.</p>
</article></body></html>"""


def para(seed: str, cite: str, n: int) -> str:
    """Filler sentences built only from words that appear in the fake sources, so they verify."""
    base = [f"The company said the model is available to developers starting today {cite}.",
            f"The release includes a smaller version for phones and laptops {cite}.",
            f"It runs without an internet connection {cite}."]
    return " ".join(base[i % len(base)] for i in range(n))


def good_draft() -> dict:
    a = "[S1]"
    return {
        "headline": "Acme releases Nova-2 as the EU fines DataCorp",
        "dek": "Acme released Nova-2, the European Commission fined DataCorp, and a Stanford University robot learned to fold shirts [S1][S2][S3].",
        "tags": ["acme", "regulation"],
        "what_happened": [
            "Acme said Nova-2 scores 87.5% on the MMLU benchmark [S1].",
            "The European Commission fined DataCorp 300 million euros [S2].",
            "Researchers at Stanford University trained a robot arm to fold shirts [S3].",
        ],
        "sections": [
            {"story": 1, "title": "Acme releases Nova-2", "category": "models",
             "paragraphs": ["Acme said on Monday that Nova-2 scores 87.5% on the MMLU benchmark, up from 81.2% for Nova-1 [S1]. "
                            "The company said the model costs $2 per million tokens [S1]. " + para("a", a, 12),
                            para("b", a, 14)]},
            {"story": 2, "title": "The EU fines DataCorp", "category": "policy",
             "paragraphs": ["The European Commission fined DataCorp 300 million euros on Monday [S2]. "
                            "Regulators said DataCorp must delete the affected training data within 90 days [S2]. "
                            "DataCorp said it would appeal the decision [S2]. " +
                            " ".join(["Regulators said DataCorp must delete the affected training data under the AI Act and privacy law [S2]."] * 8)]},
            {"story": 3, "title": "Robots learn to fold laundry", "category": "research",
             "paragraphs": ["Researchers at Stanford University trained a robot arm to fold shirts using 1,200 hours of video demonstrations [S3]. "
                            "The team reported a success rate of 72% on unseen shirts, compared with 41% for the previous best method [S3]. " +
                            " ".join(["The paper says the approach still struggles with thin fabrics [S3]."] * 10)]},
        ],
        "why_it_matters": [
            {"text": "The release includes a smaller version for phones and laptops, which runs without an internet connection [S1].", "speculative": False},
            {"text": "Cheaper models that run on phones could make AI tools more common at work [S1].", "speculative": True},
        ],
        "quote": {"text": "We built Nova-2 to be cheaper and more careful.", "speaker": "Maria Lopez", "source": "S1"},
        "chart": {"title": "MMLU scores", "unit": "%", "source": "S1",
                  "bars": [{"label": "Nova-2", "value": 87.5}, {"label": "Nova-1", "value": 81.2}]},
        "diagram": None,
    }


def replies(d: dict, n_stories: int = 3) -> list[dict]:
    """Turn a whole-post draft into what the model returns in section-by-section mode:
    one reply per story, then the headline/dek/why reply."""
    out = []
    for i in range(n_stories):
        if i < len(d["sections"]):
            s = d["sections"][i]
            sec = {"title": s["title"], "category": s["category"], "paragraphs": s["paragraphs"],
                   "bullet": d["what_happened"][i] if i < len(d["what_happened"]) else ""}
            if i == 0:
                sec.update(quote=d.get("quote"), chart=d.get("chart"), diagram=d.get("diagram"))
            out.append(sec)
        else:
            out.append({})
    out.append({"headline": d["headline"], "dek": d["dek"], "tags": d["tags"], "why_it_matters": d["why_it_matters"]})
    return out


@pytest.fixture
def fake_web():
    feed = rss([
        ("EU fines DataCorp over photo training", "https://news.example/eu-datacorp", NOW - timedelta(hours=8), "Fine."),
        ("Robots learn to fold laundry", "https://news.example/robots", NOW - timedelta(hours=10), "Robots."),
        ("Old story from last week", "https://news.example/old", NOW - timedelta(days=6), "Old."),
    ])
    lab = rss([("Acme releases Nova-2", "https://acme.example/nova-2", NOW - timedelta(hours=5), "Acme's new model.")])
    return FakeHttp({
        "https://feed.example/rss": FakeResponse(200, feed, {"content-type": "application/rss+xml"}),
        "https://lab.example/rss": FakeResponse(200, lab, {"content-type": "application/rss+xml"}),
        "https://acme.example/nova-2": FakeResponse(200, ARTICLE_A),
        "https://news.example/eu-datacorp": FakeResponse(200, ARTICLE_B),
        "https://news.example/robots": FakeResponse(200, ARTICLE_C),
    })


@pytest.fixture
def project(tmp_path):
    """A throwaway copy of the project config with a one-feed source list."""
    (tmp_path / "config").mkdir()
    shutil.copy(ROOT / "config/site.yaml", tmp_path / "config/site.yaml")
    import yaml
    srcs = yaml.safe_load((ROOT / "config/sources.yaml").read_text(encoding="utf-8"))
    srcs["sources"] = [{"id": "test", "name": "Test News", "kind": "rss", "url": "https://feed.example/rss",
                        "weight": 1.0, "category": "products"},
                       {"id": "lab", "name": "Acme", "kind": "rss", "url": "https://lab.example/rss",
                        "weight": 1.5, "category": "models", "primary": True}]
    (tmp_path / "config/sources.yaml").write_text(yaml.safe_dump(srcs), encoding="utf-8")
    (tmp_path / "content/posts").mkdir(parents=True)
    (tmp_path / "content/reports").mkdir(parents=True)
    (tmp_path / "data").mkdir()
    return tmp_path
