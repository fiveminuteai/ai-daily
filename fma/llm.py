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
    min_interval_s: float = 0.0     # pace calls to stay under a per-minute token limit (Groq free plan)
    extra: dict | None = None       # provider-specific request fields, e.g. {"reasoning_effort": "low"}
    _last_call: float = 0.0
    exhausted: bool = False         # hit a daily limit during this run; skipped from then on

    def _pace(self) -> None:
        wait = self._last_call + self.min_interval_s - time.monotonic()
        if wait > 0:
            time.sleep(wait)
        self._last_call = time.monotonic()

    @property
    def key(self) -> str | None:
        return os.environ.get(self.key_env) if self.key_env else None

    def available(self) -> bool:
        if self.local:
            try:
                return requests.get(self.base_url.rstrip("/") + "/api/tags", timeout=30).ok   # a busy Ollama can take a while to answer
            except requests.RequestException:
                return False
        return bool(self.key)

    def chat(self, system: str, user: str, temperature: float = 0.3, want_json: bool = True, careful: bool = False,
             schema: dict | None = None) -> str:
        if self.local:
            return self._ollama(system, user, temperature, want_json, schema)
        return self._openai(system, user, temperature, want_json, careful)

    def _openai(self, system, user, temperature, want_json, careful=False) -> str:
        body = {"model": self.model, "temperature": temperature,
                "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}
        if want_json:
            body["response_format"] = {"type": "json_object"}
        body.update(self.extra or {})
        if careful and "reasoning_effort" in body:
            body["reasoning_effort"] = "medium"    # fact-checking gets more thinking than drafting
            if "max_completion_tokens" in body:
                body["max_completion_tokens"] = max(body["max_completion_tokens"], 4500)   # room for the thinking
        url = self.base_url.rstrip("/") + "/chat/completions"
        headers = {"Authorization": f"Bearer {self.key}", "Content-Type": "application/json"}
        for attempt in range(4):
            self._pace()
            r = requests.post(url, json=body, headers=headers, timeout=self.timeout)
            if r.status_code == 400 and "response_format" in body:
                body.pop("response_format")   # some models reject JSON mode; the prompt still asks for JSON
                continue
            if r.status_code in (429, 500, 502, 503, 504) and attempt < 3:
                try:
                    wait = float(r.headers.get("retry-after", 0))
                except ValueError:
                    wait = 0
                low = r.text.lower().replace(" ", "")
                if r.status_code == 429 and "requesttoolarge" in low:
                    # 11 Nov 2026: "Request too large ... Limit 1000, Requested 1083" was retried for 7 minutes; it
                    # can never succeed on this model, so the chain moves straight to the next provider
                    raise LLMError(f"{self.name} request too large for its per-minute limit (HTTP 429)")
                # only an explicit per-day cap counts as daily; per-minute quota messages also say "quota"
                daily = r.status_code == 429 and ("perday" in low or "tokensperday" in low or "requestsperday" in low
                                                  or wait > 600)
                if daily:                         # a daily cap won't clear in minutes: hand over to the next provider
                    self.exhausted = True
                    raise LLMError(f"{self.name} daily limit reached (HTTP 429)")
                pause = min(90.0, max(wait + 1, 20 * (attempt + 1)))
                log.warning("%s HTTP %s, waiting %.0fs before retrying", self.name, r.status_code, pause)
                time.sleep(pause)
                continue
            if not r.ok:
                raise LLMError(f"{self.name} HTTP {r.status_code}: {r.text[:300]}")
            try:
                data = r.json()
                log.info("%s used %s tokens", self.name, (data.get("usage") or {}).get("total_tokens", "?"))
                return data["choices"][0]["message"]["content"] or ""
            except (KeyError, IndexError, ValueError) as exc:
                raise LLMError(f"{self.name} bad response: {r.text[:300]}") from exc
        raise LLMError(f"{self.name}: gave up after retries")

    def _ollama(self, system, user, temperature, want_json, schema=None) -> str:
        body = {"model": self.model, "stream": False,
                "options": {"temperature": temperature, "num_ctx": 24576},
                "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}
        if want_json:
            body["format"] = schema or "json"     # a schema becomes a grammar: the reply always has that shape
        r = requests.post(self.base_url.rstrip("/") + "/api/chat", json=body, timeout=self.timeout)
        if not r.ok:
            raise LLMError(f"ollama HTTP {r.status_code}: {r.text[:300]}")
        return r.json().get("message", {}).get("content", "")


def cloud_allowed() -> bool:
    """The free cloud models have daily caps shared with the daily post. On 6 Nov 2026 local experiments the evening
    before used up Groq's cap and the post was skipped twice. So off GitHub Actions the cloud providers are off
    unless FMA_ALLOW_PROD_KEYS=1 is set on purpose; local work uses the local model."""
    return bool(os.environ.get("GITHUB_ACTIONS")) or os.environ.get("FMA_ALLOW_PROD_KEYS") == "1"


def providers_from_config(site_cfg: dict, only: str | None = None) -> list[Provider]:
    out = []
    cloud = cloud_allowed() and site_cfg.get("cloud_models", True) is not False   # config switch (6 Nov 2026)
    if not cloud:
        log.warning("not on GitHub Actions: cloud models are off to protect the daily post's quota "
                    "(set FMA_ALLOW_PROD_KEYS=1 to use them anyway)")
    for p in site_cfg.get("providers", []):
        if only and p["name"] != only:
            continue
        if not cloud and not p.get("local"):
            continue
        out.append(Provider(name=p["name"], base_url=p["base_url"], model=p["model"],
                            key_env=p.get("key_env"), local=bool(p.get("local", False)),
                            min_interval_s=float(p.get("min_interval_s", 0)), extra=p.get("extra"),
                            # a stalled cloud call must fail inside the 40-minute job so the retry can run;
                            # a local model on a slow machine genuinely needs the long wait
                            timeout=float(p.get("timeout", 1800 if p.get("local") else 180))))
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
        self.last_raw: str = ""

    def __bool__(self) -> bool:
        return bool(self.providers)

    # Waits before trying every provider again when they all failed for a passing reason (overload, a timeout).
    # 4 Nov 2026: one Gemini "high demand" 503 after Groq's daily cap crashed the whole attempt.
    ROUND_WAITS = (60, 180, 300)
    deadline: float | None = None      # time.monotonic() after which no new call starts (pipeline.run_day sets it)

    def time_left(self) -> float:
        return float("inf") if self.deadline is None else self.deadline - time.monotonic()

    def ask_json(self, system: str, user: str, temperature: float = 0.3, careful: bool = False,
                 schema: dict | None = None) -> dict:
        """schema: a JSON schema the reply must match. Local models enforce it while generating (Ollama structured
        outputs; 6 Nov 2026: "exactly 3 reactions" was unreliable for a 7B without it). Cloud providers ignore it."""
        for wait in (*self.ROUND_WAITS, None):
            if self.time_left() <= 0:
                raise LLMError("out of time for this run")
            try:
                return self._ask_round(system, user, temperature, careful, schema)
            except LLMError as exc:
                if wait is None or all(p.exhausted for p in self.providers) or wait >= self.time_left():
                    raise
                log.warning("every provider failed (%s); trying them all again in %ss", str(exc)[:200], wait)
                time.sleep(wait)
        raise LLMError("unreachable")

    def _ask_round(self, system: str, user: str, temperature: float, careful: bool, schema: dict | None = None) -> dict:
        errors = []
        for p in self.providers:
            if p.exhausted:
                continue
            for _try in range(2):              # one retry on the same provider for a broken or cut-off reply
                try:
                    t0 = time.monotonic()
                    reply = p.chat(system, user, temperature, careful=careful, schema=schema)
                    log.info("%s answered in %.0fs", p.name, time.monotonic() - t0)
                    self.last_raw = reply
                    data = parse_json(reply)
                    self.used = f"{p.name}:{p.model}"
                    return data
                except ValueError as exc:
                    log.warning("provider %s returned unreadable JSON: %s", p.name, exc)
                    errors.append(f"{p.name}: {exc}")
                except (LLMError, requests.RequestException) as exc:
                    log.warning("provider %s failed: %s", p.name, exc)
                    errors.append(f"{p.name}: {exc}")
                    break
        raise LLMError("all providers failed: " + " | ".join(errors) if errors else "no provider available")
