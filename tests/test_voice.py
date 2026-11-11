

def test_money_and_big_numbers_are_spelled_as_people_say_them():
    """11 Nov 2026: '3,378,378' and '$70-$78' were misread in a live Reel (checked against Kokoro's phonemes)."""
    from fma.voice import spoken
    assert spoken("sell 3,378,378 shares[S8].") == "sell 3378378 shares."
    assert spoken("$70-$78 per share") == "70 to 78 dollars per share"
    assert spoken("$1.4T valuation") == "1 point 4 trillion dollars valuation"
    assert spoken("$8 per million, not $10") == "8 dollars per million, not 10 dollars"
    assert spoken("version 2.1.312") == "version 2 point 1 point 3 1 2"


def test_no_published_duo_line_is_spoken_with_a_dollar_sign_or_a_thousands_comma():
    import json
    import re
    from pathlib import Path
    from fma.voice import spoken
    bad = []
    for f in sorted(Path("content/posts").glob("*.json")):
        for sec in json.loads(f.read_text(encoding="utf-8")).get("sections", []):
            card = sec.get("card") or {}
            for t in [card.get("hook") or "", *(card.get("points") or []),
                      *[ln["text"] for ln in (card.get("duo") or {}).get("lines", [])]]:
                if re.search(r"\$|\d,\d", spoken(t)):
                    bad.append((f.name, spoken(t)))
    assert not bad, bad[:5]
