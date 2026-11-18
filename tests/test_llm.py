

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


def test_a_local_openai_style_server_is_used_and_checked_the_openai_way(monkeypatch):
    """19 Nov 2026: the 35B (llama.cpp) is local but speaks the OpenAI API; the 7B (Ollama) keeps its own."""
    from fma import llm
    calls = []

    class R:
        ok, status_code, headers, text = True, 200, {}, ""
        def json(self):
            return {"choices": [{"message": {"content": '{"ok": 1}'}, "finish_reason": "stop"}], "usage": {}}

    monkeypatch.setattr(llm, "local_request", lambda method, url, timeout, **kw: calls.append((method, url, kw)) or R())
    monkeypatch.setenv("FMA_MODEL_CONSOLE", "off")
    p = llm.Provider(name="llama", base_url="http://127.0.0.1:8080/v1/", model="qwen3.6-35b-a3b",
                     key_env="LLAMA_LOCAL_KEY", local=True, api="openai",
                     extra={"chat_template_kwargs": {"enable_thinking": False}})
    monkeypatch.delenv("LLAMA_LOCAL_KEY", raising=False)
    assert p.key == "none" and p.available()
    assert calls[-1][:2] == ("GET", "http://127.0.0.1:8080/v1/models")
    assert p.chat("s", "u") == '{"ok": 1}'
    method, url, kw = calls[-1]
    assert url.endswith("/v1/chat/completions") and kw["json"]["chat_template_kwargs"] == {"enable_thinking": False}


def test_the_config_lists_the_35b_first_then_the_7b():
    from fma import config
    from fma.llm import providers_from_config
    local = [p for p in providers_from_config(config.site_config()) if p.local]
    assert [(p.model, p.api) for p in local] == [("qwen3.6-35b-a3b", "openai"), ("qwen2.5:7b", "ollama")]
