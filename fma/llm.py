"""Model access. Every cloud provider here speaks the OpenAI chat-completions format; Ollama uses
its native API so we can set a context window big enough for the source text.

Keys are read from environment variables only."""
from __future__ import annotations

import json
import logging
import os
import re
import time
from dataclasses import dataclass

import requests

log = logging.getLogger(__name__)


class LLMError(RuntimeError):
    pass


@dataclass
class Provider:
    name: str
    base_url: str
    model: str
    key_env: str | None = None
    local: bool = False
    timeout: float = 1800.0

    @property
    def key(self) -> str | None:
        return os.environ.get(self.key_env) if self.key_env else None

    def available(self) -> bool:
        if self.local:
            try:
                return requests.get(self.base_url.rstrip("/") + "/api/tags", timeout=3).ok
            except requests.RequestException:
                return False
        return bool(self.key)

    def chat(self, system: str, user: str, temperature: float = 0.3, want_json: bool = True) -> str:
        if self.local:
            return self._ollama(system, user, temperature, want_json)
        return self._openai(system, user, temperature, want_json)

    def _openai(self, system, user, temperature, want_json) -> str:
        body = {"model": self.model, "temperature": temperature,
                "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}
        if want_json:
            body["response_format"] = {"type": "json_object"}
        url = self.base_url.rstrip("/") + "/chat/completions"
        headers = {"Authorization": f"Bearer {self.key}", "Content-Type": "application/json"}
        for attempt in range(3):
            r = requests.post(url, json=body, headers=headers, timeout=self.timeout)
            if r.status_code == 400 and "response_format" in body:
                body.pop("response_format")   # some models reject JSON mode; the prompt still asks for JSON
                continue
            if r.status_code in (429, 500, 502, 503, 504) and attempt < 2:
                time.sleep(20 * (attempt + 1))
                continue
            if not r.ok:
                raise LLMError(f"{self.name} HTTP {r.status_code}: {r.text[:300]}")
            try:
                return r.json()["choices"][0]["message"]["content"] or ""
            except (KeyError, IndexError, ValueError) as exc:
                raise LLMError(f"{self.name} bad response: {r.text[:300]}") from exc
        raise LLMError(f"{self.name}: gave up after retries")

    def _ollama(self, system, user, temperature, want_json) -> str:
        body = {"model": self.model, "stream": False,
                "options": {"temperature": temperature, "num_ctx": 24576},
                "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}
        if want_json:
            body["format"] = "json"
        r = requests.post(self.base_url.rstrip("/") + "/api/chat", json=body, timeout=self.timeout)
        if not r.ok:
            raise LLMError(f"ollama HTTP {r.status_code}: {r.text[:300]}")
        return r.json().get("message", {}).get("content", "")


def providers_from_config(site_cfg: dict, only: str | None = None) -> list[Provider]:
    out = []
    for p in site_cfg.get("providers", []):
        if only and p["name"] != only:
            continue
        out.append(Provider(name=p["name"], base_url=p["base_url"], model=p["model"],
                            key_env=p.get("key_env"), local=bool(p.get("local", False))))
    return out


def parse_json(text: str) -> dict:
    """Parse a model's JSON reply, tolerating code fences and chatter around the object."""
    text = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.M).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start >= 0 and end > start:
            return json.loads(text[start : end + 1])
        raise


class Chain:
    """Try providers in order until one answers with valid JSON."""

    def __init__(self, providers: list[Provider]):
        self.providers = [p for p in providers if p.available()]
        self.used: str | None = None

    def __bool__(self) -> bool:
        return bool(self.providers)

    def ask_json(self, system: str, user: str, temperature: float = 0.3) -> dict:
        errors = []
        for p in self.providers:
            try:
                reply = p.chat(system, user, temperature)
                data = parse_json(reply)
                self.used = f"{p.name}:{p.model}"
                return data
            except (LLMError, requests.RequestException, ValueError) as exc:
                log.warning("provider %s failed: %s", p.name, exc)
                errors.append(f"{p.name}: {exc}")
        raise LLMError("all providers failed: " + " | ".join(errors) if errors else "no provider available")
