def test_playbook_is_up_to_date():
    """docs/PLAYBOOK.md is generated from the prompts in the code; regenerate it with `python -m fma.playbook`."""
    from fma import playbook
    assert playbook.OUT.read_text(encoding="utf-8") == playbook.build(), "run: python -m fma.playbook"
