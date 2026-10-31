import json
import re

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


def test_middle_initial_does_not_split_a_sentence():
    assert split_sentences("Frederick P. Brooks wrote it [S1]. It aged well [S1].") == \
        ["Frederick P. Brooks wrote it [S1].", "It aged well [S1]."]


def test_title_case_headline_is_sentence_cased_but_names_still_checked():
    v = Verifier(SOURCES)
    h, problems = v.headline("Acme Releases Nova-2 For Phones And Laptops")
    assert h == "Acme releases Nova-2 for phones and laptops" and not problems
    _, problems = v.headline("Acme Releases Nova-2 With Globex")
    assert problems and "Globex" in problems[0]


def test_number_shorthand_is_a_unit_not_a_name():
    v = Verifier(SOURCES)
    assert v.sentence("DataCorp was fined 300 M euros [S2].", "x", [])
    assert v.sentence("DataCorp was fined 300 B euros [S2].", "x", []) is None
    assert v.sentence("Nova-2 Mini weighs 3B parameters [S4].", "x", [])


def test_checker_evidence_must_be_in_the_source():
    from fma.verify import corpus, evidence_found
    c = corpus(SOURCES[1])
    assert evidence_found("fined DataCorp 300 million euros on Monday", c)
    assert evidence_found("The European Commission fined DataCorp ... within 90 days under the AI Act", c)
    assert not evidence_found("DataCorp agreed to pay the fine immediately", c)


def test_evidence_tolerates_small_differences_but_not_scattered_words():
    from fma.verify import corpus, evidence_found
    c = corpus(SOURCES[1])
    assert evidence_found("“The European Commission fined DataCorp 300 million euros on Monday”", c)
    assert evidence_found("Commission fined DataCorp 300 million euros Monday for training models on photos", c)
    assert not evidence_found("DataCorp fined the European Commission over Monday photos in court", c)


def test_evidence_joined_out_of_order_and_markdown_links():
    from fma.verify import evidence_found, norm
    c = norm("Genie 4 allows free-form edits, like changing the weather in real time. It can maintain a consistent "
             "scene for up to two minutes, double its predecessor's limit. Unrelated filler text follows here. "
             "Our model is now available at [ModelScope](https://modelscope.cn/models/x/unlimited-ocr-2). Thanks.")
    assert evidence_found("It can maintain a consistent scene for up to two minutes, double its predecessor’s limit. "
                          "It also allows free‑form edits, like changing the weather in real time.", c)
    assert evidence_found("It can maintain a consistent scene for up to two minutes, double its predecessor’s limit. "
                          "Genie 4 allows free‑form edits, like changing the weather in real time.", c)
    assert evidence_found("Our model is now available at ModelScope.", c)
    assert not evidence_found("It can maintain a scene. Our model is now sold exclusively at ModelScope stores worldwide.", c)


def test_ordinary_word_starting_a_sentence_is_not_a_name():
    from fma.verify import check_sentence, corpus
    cor = {"S1": corpus({"title": "OCR", "text": "OCR systems read pages one at a time and memory grows."})}
    assert check_sentence("Traditional OCR systems read pages one at a time [S1].", ["S1"], cor, set()) == []
    assert check_sentence("Zorblax OCR systems read pages one at a time [S1].", ["S1"], cor, set()) != []


def test_evidence_stitched_from_two_sentences_out_of_order():
    from fma.verify import evidence_found, norm
    c = norm("Thrive Holdings has acquired security company ADT for $10 per share, the companies announced on Thursday. "
             "Beyond equity, the total enterprise value of the deal is $15.3 billion, ADT said. "
             "“We’re going to invest to continue being the leader,” he said. Other text follows.")
    assert evidence_found("Thrive Holdings has acquired security company ADT for $10 per share... total enterprise value "
                          "of the deal is $15.3 billion, the companies announced on Thursday", c)
    assert evidence_found("We’re going to invest to continue being the leader,\" and \"the deal is $15.3 billion", c)
    assert not evidence_found("Thrive Holdings has acquired ADT for $10 per share, and plans to fire half of ADT staff "
                              "within a year to cut costs sharply", c)


# ---------------------------------------------------------------- headline and "why it matters" in the model check

def _checked(chain):
    from fma.verify import llm_check
    post, report = verify_draft(good_draft(), SOURCES)
    return llm_check(chain, post, SOURCES, report)


def test_headline_is_model_checked_against_lead_story_sources_only():
    from conftest import FakeChain
    chain = FakeChain([])
    _, report = _checked(chain)
    assert not report["headline_problems"]
    prompt = next(p for p in chain.prompts if "[headline]" in p)
    claims, src = prompt.split("\n\nSOURCES\n", 1)
    assert len(re.findall(r"^C\d+: ", claims, flags=re.M)) == 1    # the headline is checked on its own
    headers = {ln.split("]")[0] + "]" for ln in src.splitlines() if ln.startswith("[S")}
    assert headers == {"[S1]", "[S4]"}                         # story 1's sources, not S2/S3 from other stories


def test_unsupported_headline_fails_the_gate():
    from conftest import FakeChain

    from fma.gate import run_gate
    _, report = _checked(FakeChain([], flag_text={"[headline]": "joins two different events"}))
    assert report["headline_problems"] == ["model check: joins two different events"]
    head = next(e for e in report["entries"] if e["where"] == "headline")
    assert head["status"] == "dropped"
    assert report["ok"] + report["repaired"] + report["dropped"] == report["checked"]
    fails = run_gate({"headline": "x"}, report, {}, [])
    assert any(f.startswith("headline not verified") for f in fails)


def test_why_it_matters_is_model_checked_and_unsupported_fact_dropped():
    from conftest import FakeChain
    chain = FakeChain([], flag_text={"Cheaper models that run on phones": "no source says this"})
    post, report = _checked(chain)
    joined = "\n".join(chain.prompts)
    assert "[analysis] Cheaper models that run on phones" in joined and "is our commentary" in joined
    texts = [w["text"] for w in post["why_it_matters"]]
    assert len(texts) == 1 and "smaller version" in texts[0]
    e = next(e for e in report["entries"] if e["text"].startswith("Cheaper models"))
    assert e["status"] == "dropped" and "model check: no source says this" in e["problems"]


# ---------------------------------------------------------------- verified but unused

def test_verified_but_unused_sentences_are_not_confirmed():
    from fma.pipeline import assemble
    d = good_draft()
    d["what_happened"].insert(1, "Nova-2 is available to developers in 40 countries [S1].")   # a spare bullet
    post, report = verify_draft(d, SOURCES)
    spare = next(e for e in report["entries"] if e["text"].startswith("Nova-2 is available"))
    assert spare["status"] == "ok"
    out = assemble("2026-10-27", post, SOURCES, {"byline": "x"}, "m", report)
    assert "40 countries" not in " ".join(out["what_happened"])
    assert spare["status"] == "unused"
    assert report["unused"] == out["verification"]["unused"] >= 1
    assert report["ok"] + report["repaired"] + report["dropped"] == report["checked"]
    assert report["checked"] + report["unused"] == len(report["entries"])
    for e in report["entries"]:                                 # everything still "ok" really is in the post
        if e["status"] == "ok" and e["where"] not in ("chart", "diagram"):
            assert e["text"].rstrip(".") in json.dumps(out, ensure_ascii=False).replace("\\", ""), e["text"]


# ---------------------------------------------------------------- a limit in the source stays a limit

ARS_31_OCT = ("An official extension for Anthropic's Claude model was backdoored and threatened as many as 5,000 "
              "developers' machines, multiple sources reported Friday. The malicious version, 2.1.313, subsequently "
              "affected \"at most 5,000 users,\" presumably when they either downloaded it or their systems "
              "automatically fetched and installed it.")


def test_a_ceiling_stated_as_fact_is_caught():
    from fma.verify import ceiling_dropped
    # the real 31 Oct 2026 headline and the Ars Technica text it was checked against
    assert ceiling_dropped("Anthropic's Claude VS Code extension compromised, installing SSH backdoor on thousands "
                           "of developers' machines", ARS_31_OCT)
    assert ceiling_dropped("Backdoored Claude extension hit 5,000 developers", ARS_31_OCT)


def test_a_claim_that_keeps_the_limit_passes():
    from fma.verify import ceiling_dropped
    assert not ceiling_dropped("Claude extension on Cursor backdoored, exposing up to 5,000 developers", ARS_31_OCT)
    assert not ceiling_dropped("Backdoored Claude extension put thousands of developers at risk", ARS_31_OCT)
    assert not ceiling_dropped("Claude extension on Cursor backdoored for nearly 12 hours", ARS_31_OCT)
    assert not ceiling_dropped("Acme hires 40 engineers", "Acme will spend up to $5 billion.")


def test_ceiling_headline_fails_the_gate_without_asking_the_model():
    from conftest import FakeChain

    from fma.verify import llm_check
    d = good_draft()
    capped = [dict(s, text=s["text"] + " The deal could reach up to 900 customers.") if s["id"] == "S1" else s
              for s in SOURCES]
    d["headline"] = "Acme ships Nova-2 to 900 customers"
    post, report = verify_draft(d, capped)
    chain = FakeChain([])
    _, report = llm_check(chain, post, capped, report)
    assert any("as a limit" in p for p in report["headline_problems"])
    assert not any("[headline]" in p for p in chain.prompts)
