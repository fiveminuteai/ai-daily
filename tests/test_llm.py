

def test_cloud_models_switch_turns_off_cloud_providers():
    from fma.llm import providers_from_config
    cfg = {"providers": [{"name": "groq", "base_url": "x", "model": "m", "key_env": "K"},
                         {"name": "ollama", "base_url": "y", "model": "q", "key_env": None, "local": True}],
           "cloud_models": False}
    assert [p.name for p in providers_from_config(cfg)] == ["ollama"]


def test_request_too_large_moves_on_at_once(monkeypatch):
    """11 Nov 2026: a 429 "Request too large" was retried for 7 minutes; it can never pass on that model."""
    import pytest as _p
    from fma import llm
    calls = []

    class R:
        status_code, headers, ok = 429, {}, False
        text = "Request too large for model `qwen/qwen3.8-27b` on tokens per minute (TPM): Limit 1000, Requested 1083"

    monkeypatch.setattr(llm.requests, "post", lambda *a, **k: calls.append(1) or R())
    monkeypatch.setattr(llm.time, "sleep", lambda s: None)
    monkeypatch.setenv("FAKE_KEY", "k")
    p = llm.Provider(name="groq", base_url="https://x/", model="m", key_env="FAKE_KEY")
    with _p.raises(llm.LLMError, match="too large"):
        p._openai("s", "u", 0.3, True)
    assert len(calls) == 1 and not p.exhausted


def test_a_reply_cut_off_at_the_token_limit_is_a_failure(monkeypatch):
    import pytest as _p
    from fma import llm

    class R:
        status_code, headers, ok, text = 200, {}, True, ""

        def json(self):
            return {"choices": [{"finish_reason": "length", "message": {"content": '{"a": 1'}}], "usage": {}}
    monkeypatch.setattr(llm.requests, "post", lambda *a, **k: R())
    monkeypatch.setenv("FAKE_KEY", "k")
    p = llm.Provider(name="groq", base_url="https://x/", model="m", key_env="FAKE_KEY")
    with _p.raises(llm.LLMError, match="cut off"):
        p._openai("s", "u", 0.3, True)
