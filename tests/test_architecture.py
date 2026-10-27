from datetime import timedelta

from conftest import NOW, FakeHttp, FakeResponse

from fma.feeds import fetch_hf_models
from fma.models import Item, Story
from fma.rank import guess_category
from fma.verify import Verifier
from fma.visuals import compare_svg, flow_svg

HINTS = {"architecture": ["mixture-of-experts", "attention", "MoE", "long-context"], "research": ["paper"],
         "models": ["model"]}


def item(title, cat="research", src="arxiv-ai"):
    return Item(source_id=src, source_name=src, title=title, url=f"https://x/{title}", published=NOW, category=cat)


def test_papers_about_model_design_are_architecture():
    assert guess_category(Story([item("Sparse attention for long-context reasoning")]), HINTS) == "architecture"
    assert guess_category(Story([item("A survey of robot grasping")]), HINTS) == "research"
    assert guess_category(Story([item("New on Hugging Face: org/model", cat="architecture", src="hf-models")]), HINTS) == "architecture"


def test_hf_models_skips_old_quantised_and_unpopular():
    data = [{"id": "lab/Big-MoE-1", "createdAt": (NOW - timedelta(days=2)).isoformat(), "likes": 900, "pipeline_tag": "text-generation"},
            {"id": "someone/Big-MoE-1-GGUF", "createdAt": (NOW - timedelta(days=1)).isoformat(), "likes": 900},
            {"id": "lab/Old-Model", "createdAt": (NOW - timedelta(days=30)).isoformat(), "likes": 5000},
            {"id": "lab/Tiny", "createdAt": (NOW - timedelta(days=1)).isoformat(), "likes": 3}]
    http = FakeHttp({"https://hf": FakeResponse(200, json_data=data)})
    items = fetch_hf_models({"id": "hf-models", "name": "HF", "url": "https://hf", "category": "architecture"}, http, now=NOW)
    assert [i.url for i in items] == ["https://huggingface.co/lab/Big-MoE-1"]
    assert items[0].title == "New on Hugging Face: lab/Big-MoE-1 (text generation)"


SRC = [{"id": "S1", "story": 1, "title": "Big-MoE-1 model card", "url": "https://huggingface.co/lab/Big-MoE-1",
        "publisher": "Hugging Face", "published": "2026-10-26T00:00:00+00:00",
        "text": "Big-MoE-1 uses a mixture-of-experts layer with 64 experts, of which 4 are active per token. "
                "It replaces full attention with sliding-window attention and supports a 1M token context."}]


def test_compare_diagram_keeps_verified_design_and_whitelisted_baseline():
    v = Verifier(SRC)
    d = v.diagram({"title": "How Big-MoE-1 differs", "source": "S1", "kind": "compare",
                   "steps": ["64 experts, 4 active per token", "Sliding-window attention", "1M token context"],
                   "baseline": ["Dense feed-forward layer", "Self-attention over all tokens", "Fixed context window"]})
    assert d["kind"] == "compare" and len(d["baseline"]) == 3
    svg = flow_svg(d)
    assert "STANDARD TRANSFORMER" in svg and "Sliding-window attention" in svg
    assert "STANDARD TRANSFORMER" in compare_svg(d, W=360)


def test_compare_diagram_rejects_invented_baseline_and_unverified_blocks():
    v = Verifier(SRC)
    d = v.diagram({"title": "x", "source": "S1", "kind": "compare",
                   "steps": ["64 experts, 4 active per token", "Sliding-window attention", "1M token context"],
                   "baseline": ["Quantum attention", "Magic layer"]})
    assert d["kind"] == "flow"                       # baseline not from the allowed list -> plain flow
    assert Verifier(SRC).diagram({"title": "x", "source": "S1", "kind": "compare",
                                  "steps": ["128 experts", "Sliding-window attention", "1M token context"],
                                  "baseline": ["Dense feed-forward layer", "Fixed context window"]}) is None
