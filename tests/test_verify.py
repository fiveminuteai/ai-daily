from conftest import ARTICLE_A, ARTICLE_B, ARTICLE_C, good_draft

from fma.extract import html_to_text
from fma.verify import Verifier, split_sentences, verify_draft

SOURCES = [
    {"id": "S1", "story": 1, "title": "Acme releases Nova-2", "url": "https://acme.example/nova-2", "publisher": "Acme",
     "published": "2026-10-26T20:00:00+00:00", "text": html_to_text(ARTICLE_A)},
    {"id": "S2", "story": 2, "title": "EU fines DataCorp", "url": "https://news.example/eu", "publisher": "News",
     "published": "2026-10-26T17:00:00+00:00", "text": html_to_text(ARTICLE_B)},
    {"id": "S3", "story": 3, "title": "Robots learn to fold laundry", "url": "https://news.example/robots",
     "publisher": "News", "published": "2026-10-26T15:00:00+00:00", "text": html_to_text(ARTICLE_C)},
    {"id": "S4", "story": 1, "title": "Nova-2 hands-on", "url": "https://blog.example/nova", "publisher": "Blog",
     "published": "2026-10-26T21:00:00+00:00", "text": "Nova-2 Mini weighs 3 billion parameters, a reviewer found."},
]


def check(sentence):
    v = Verifier(SOURCES)
    out = v.sentence(sentence, "test", [])
    return out, v.log[-1]


def test_extract_drops_nav_and_footer():
    t = html_to_text(ARTICLE_A)
    assert "menu" not in t and "legal" not in t and "87.5%" in t


def test_true_numbers_and_names_pass():
    out, log = check("Acme said Nova-2 scores 87.5% on MMLU, up from 81.2% for Nova-1 [S1].")
    assert out and log["status"] == "ok"


def test_wrong_number_is_dropped():
    out, log = check("Acme said Nova-2 scores 89.5% on MMLU [S1].")
    assert out is None and "89.5%" in log["problems"][0]


def test_percent_written_as_word_matches():
    out, _ = check("The team reported a success rate of 72 percent on unseen shirts [S3].")
    assert out


def test_thousands_separator_and_multiplier():
    assert check("They used 1,200 hours of video [S3].")[0]
    assert check("They used 1200 hours of video [S3].")[0]
    assert check("The fine was 300 million euros [S2].")[0]
    assert check("The fine was 300 billion euros [S2].")[0] is None


def test_invented_name_is_dropped():
    out, log = check("Acme partnered with Globex on Nova-2 [S1].")
    assert out is None and any("Globex" in p for p in log["problems"])


def test_name_from_other_story_is_not_accepted():
    # DataCorp is in S2, but the sentence cites S1 and S2 belongs to a different story
    out, _ = check("Acme said DataCorp will use Nova-2 [S1].")
    assert out is None


def test_fact_in_sibling_source_is_recited():
    out, log = check("Nova-2 Mini has 3 billion parameters [S1].")
    assert out == "Nova-2 Mini has 3 billion parameters[S1][S4]."
    assert log["status"] == "repaired"


def test_uncited_sentence_is_auto_cited_only_from_evidence():
    v = Verifier(SOURCES)
    assert v.sentence("Acme released Nova-2 for 40 countries.", "x", []) == "Acme released Nova-2 for 40 countries[S1]."
    assert v.log[-1]["status"] == "repaired"
    assert v.sentence("Acme released Nova-2 in 50 countries.", "x", []) is None      # wrong number: no source fits
    assert v.sentence("This matters a lot.", "x", []) is None                        # nothing checkable: no guessing


def test_title_case_heading_is_not_mistaken_for_names():
    v = Verifier(SOURCES)
    assert v.sentence("Regulators Fine DataCorp Over Training Data [S2].", "x", [])
    assert v.sentence("Regulators Fine Globex Over Training Data [S2].", "x", []) is None


def test_uncited_sentence_is_dropped_unless_paragraph_has_citations():
    v = Verifier(SOURCES)
    para = v.paragraph("Acme released Nova-2. It scores 87.5% on MMLU [S1].", "x")
    assert para == "Acme released Nova-2[S1]. It scores 87.5% on MMLU[S1]."
    assert split_sentences(para) == ["Acme released Nova-2[S1].", "It scores 87.5% on MMLU[S1]."]


def test_ordinary_sentence_start_word_is_fine():
    assert check("Regulators said DataCorp must delete the data within 90 days [S2].")[0]
    assert check("Meanwhile, DataCorp said it would appeal [S2].")[0]


def test_hype_words_are_dropped():
    out, log = check("Acme's groundbreaking Nova-2 scores 87.5% [S1].")
    assert out is None and any("hype" in p for p in log["problems"])


def test_unknown_citation_is_dropped():
    assert check("Acme released Nova-2 [S9].")[0] is None


def test_inline_quote_must_be_verbatim_and_only_one():
    v = Verifier(SOURCES)
    assert v.sentence('Lopez said "We built Nova-2 to be cheaper and more careful" [S1].', "x", [])
    assert v.sentence('Lopez said "We built Nova-2 to be much cheaper" [S1].', "x", []) is None
    assert v.sentence('Regulators said "must delete the affected training data within 90 days" [S2].', "x", []) is None


def test_split_sentences_handles_abbreviations_and_trailing_citations():
    s = split_sentences("The U.S. Senate voted on Monday. [S1] It passed 60 to 40 [S2]. Then e.g. this happened [S3].")
    assert s == ["The U.S. Senate voted on Monday. [S1]", "It passed 60 to 40 [S2].", "Then e.g. this happened [S3]."]


def test_date_mentions_match_source_metadata():
    assert check("Acme announced Nova-2 on 26 October [S1].")[0]
    assert check("Acme announced Nova-2 on 29 October [S1].")[0] is None


def test_full_draft_keeps_good_and_drops_bad():
    d = good_draft()
    d["sections"][0]["paragraphs"].append("Acme also bought Initech for $9 billion [S1].")
    d["quote"]["text"] = "We built Nova-2 to win"
    d["chart"]["bars"].append({"label": "Nova-3", "value": 95})
    post, report = verify_draft(d, SOURCES)
    body = " ".join(" ".join(s["paragraphs"]) for s in post["sections"])
    assert "Initech" not in body and "87.5%" in body
    assert post["quote"] is None
    assert [b["label"] for b in post["chart"]["bars"]] == ["Nova-2", "Nova-1"]
    assert report["dropped"] >= 3 and report["layer1_done"]
    assert not report["headline_problems"]


def test_fabricated_headline_is_flagged():
    d = good_draft()
    d["headline"] = "Globex buys Acme for $40 billion"
    _, report = verify_draft(d, SOURCES)
    assert report["headline_problems"]


def test_section_with_too_little_verified_text_is_removed():
    d = good_draft()
    d["sections"][2]["paragraphs"] = ["Researchers at MIT built a robot [S3]. It costs $5 [S3]."]
    post, _ = verify_draft(d, SOURCES)
    assert len(post["sections"]) == 2
