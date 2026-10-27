from conftest import NOW

from fma.editor import apply_editor
from fma.models import Item, Story


class Chain:
    def __init__(self, reply=None, fail=False):
        self.reply, self.fail = reply, fail

    def __bool__(self):
        return True

    def ask_json(self, system, user, temperature=0.3, careful=False):
        if self.fail:
            raise RuntimeError("down")
        return self.reply


def stories():
    mk = lambda t, s: Story([Item("x", "X", t, f"https://x/{t}", NOW)], score=s)  # noqa: E731
    return [mk("Customer case study", 3.0), mk("Genie 4 world model launches", 2.5), mk("Niche paper", 2.0)]


AUD = {"description": "colleagues", "interests": ["launches"], "editor_weight": 1.5}


def test_editor_lifts_interesting_story_over_dull_but_important_one():
    out = apply_editor(Chain({"scores": [{"n": 1, "interest": 1}, {"n": 2, "interest": 9}, {"n": 3, "interest": 2}]}),
                       stories(), AUD)
    assert out[0].title == "Genie 4 world model launches" and out[0].interest == 9


def test_editor_failure_falls_back_to_importance():
    out = apply_editor(Chain(fail=True), stories(), AUD)
    assert [s.title for s in out] == ["Customer case study", "Genie 4 world model launches", "Niche paper"]


def test_missing_scores_count_as_neutral():
    out = apply_editor(Chain({"scores": [{"n": 2, "interest": 10}]}), stories(), AUD)
    assert out[0].title == "Genie 4 world model launches"
