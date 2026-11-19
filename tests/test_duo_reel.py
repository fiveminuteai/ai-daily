

def test_reel_effects_follow_the_switch_and_the_comment_needs_its_spoken_question():
    """19 Nov 2026 (brief B): the impact frame and the comment drop are off unless site.yaml reel_fx turns them on, and
    the comment shows the card's own question from the line that says it, never anything else."""
    from fma.duo_reel import reel_fx
    lines = [{"who": "spark", "text": "Anthropic priced at $83.", "start": 0.0, "card": False},
             {"who": "doubt", "text": "Eighty three?", "start": 2.6, "card": False},
             {"who": "spark", "text": "Will AI IPOs change your career path? Follow us for such updates.", "start": 8.4, "card": False},
             {"who": "spark", "text": "Five Minute AI.", "start": 11.0, "card": True}]
    card = {"ask": "Will AI IPOs change your career path[S6]?"}
    assert reel_fx(card, lines, {}) == {}
    assert reel_fx(card, lines, {"impact": False, "comment": False}) == {}
    assert reel_fx(card, lines, {"impact": True}) == {"fx": {"impact": True}}
    on = reel_fx(card, lines, {"impact": True, "comment": True})
    assert on["ask"] == {"text": "Will AI IPOs change your career path?", "at": 8.4}
    assert "ask" not in reel_fx({"ask": None}, lines, {"comment": True})           # no question, no comment
    assert "ask" not in reel_fx({"ask": "Would you buy in?"}, lines, {"comment": True})   # not said: left out
