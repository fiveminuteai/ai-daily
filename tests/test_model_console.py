"""Local-model calls go through the Model Console, and straight to the engine when the console is closed."""
import socket

import pytest
import requests

from fma import llm


@pytest.fixture(autouse=True)
def _fresh(monkeypatch):
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    monkeypatch.delenv("FMA_MODEL_CONSOLE", raising=False)
    monkeypatch.setattr(llm, "_console_down_until", 0.0)


def test_engine_urls_map_to_the_console_with_the_path_kept():
    c = "http://127.0.0.1:8070/c/ai-daily-blog"
    assert llm.console_url("http://localhost:11434/api/chat") == c + "/api/chat"
    assert llm.console_url("http://127.0.0.1:11434/v1/chat/completions") == c + "/v1/chat/completions"
    assert llm.console_url("http://127.0.0.1:8080/v1/chat/completions") == c + "/v1/chat/completions"
    assert llm.console_url("https://api.groq.com/openai/v1/chat/completions") is None


def test_console_can_be_switched_off(monkeypatch):
    monkeypatch.setenv("FMA_MODEL_CONSOLE", "off")
    assert llm.console_url("http://localhost:11434/api/chat") is None
    monkeypatch.delenv("FMA_MODEL_CONSOLE")
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    assert llm.console_url("http://localhost:11434/api/chat") is None


def _closed_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def test_closed_console_falls_back_to_the_engine_and_says_so(monkeypatch, caplog):
    monkeypatch.setenv("FMA_MODEL_CONSOLE", f"http://127.0.0.1:{_closed_port()}/c/ai-daily-blog")
    real, seen = requests.request, []

    def fake(method, url, **kw):
        seen.append(url)
        if ":11434" in url:              # the engine itself: answer without a real Ollama
            r = requests.Response()
            r.status_code, r._content = 200, b'{"message": {"content": "{\\"ok\\": 1}"}}'
            return r
        return real(method, url, **kw)   # the console: a real connection to a closed port

    monkeypatch.setattr(llm.requests, "request", fake)
    p = llm.Provider(name="ollama", base_url="http://localhost:11434", model="m", local=True)
    assert p.chat("s", "u") == '{"ok": 1}'
    assert seen[0].endswith("/c/ai-daily-blog/api/chat") and seen[1] == "http://localhost:11434/api/chat"
    assert sum("model console not reachable" in r.message for r in caplog.records) == 1
    p.chat("s", "u")                     # within the retry window: straight to the engine, no second warning
    assert seen[2] == "http://localhost:11434/api/chat"
    assert sum("model console not reachable" in r.message for r in caplog.records) == 1


def test_a_console_that_drops_mid_reply_is_not_retried_directly(monkeypatch):
    calls = []

    def fake(method, url, **kw):
        calls.append(url)
        raise requests.exceptions.ReadTimeout("read timed out")

    monkeypatch.setattr(llm.requests, "request", fake)
    with pytest.raises(requests.exceptions.ReadTimeout):
        llm.local_request("POST", "http://127.0.0.1:8080/v1/chat/completions", 900, json={})
    assert len(calls) == 1               # the engine may still be working on it: never sent twice
