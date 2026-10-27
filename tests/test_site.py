from fma.site import render_text, split_headline

NUM = {"S1": 1, "S2": 2}


def test_citations_shown_once_per_run_of_same_source():
    html = str(render_text("One fact[S1]. Two fact[S1]. Other[S2].", NUM))
    assert html.count('href="#src-S1"') == 1 and html.count('href="#src-S2"') == 1
    assert "[S" not in html


def test_citation_links_can_point_to_another_page():
    assert 'href="posts/x/#src-S1"' in str(render_text("Fact[S1].", NUM, "posts/x/"))


def test_text_is_escaped():
    assert "&lt;script&gt;" in str(render_text("<script>x</script>[S1].", NUM))


def test_split_headline():
    assert split_headline("Acme releases Nova-2 as the EU fines DataCorp") == ("Acme releases Nova-2", "as the EU fines DataCorp")
    assert split_headline("Anthropic files to go public, OpenAI ships GPT-6.1") == ("Anthropic files to go public,", "OpenAI ships GPT-6.1")
    assert split_headline("Short one") == ("Short one", "")
    assert split_headline("Anthropic files S-1 revealing $3.1 billion monthly compute spend") == (
        "Anthropic files S-1 revealing $3.1 billion monthly compute spend", "")
