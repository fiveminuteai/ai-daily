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


# Model Console (14 Nov 2026, Pavan approved): a local relay at D:\model-console that logs every local-model call
# (project, model, prompt, answer, timings) and passes the reply through unchanged. Calls to the local engines go
# through it first; if it can't be reached (closed, refused, connect timeout) the same request goes straight to the
# engine, so the nightly run never depends on the console being open. FMA_MODEL_CONSOLE=off turns it off.
CONSOLE_DEFAULT = "http://127.0.0.1:8070/c/ai-daily-blog"
_ENGINE = re.compile(r"^https?://(?:localhost|127\.0\.0\.1):(?:11434|8080)(/.*)?$")
CONSOLE_RETRY_S = 300.0           # after a miss, go direct for 5 minutes before trying the console again
_console_down_until = 0.0


def console_base() -> str | None:
    v = os.environ.get("FMA_MODEL_CONSOLE", CONSOLE_DEFAULT).strip()
    if not v or v.lower() in ("off", "0", "none") or os.environ.get("GITHUB_ACTIONS"):
        return None
    return v.rstrip("/")


def console_url(url: str) -> str | None:
    """The console address for a local engine URL (path kept), or None when it isn't a local engine."""
    base, m = console_base(), _ENGINE.match(url)
    return base + (m.group(1) or "") if base and m else None


def _not_reached(exc: requests.RequestException) -> bool:
    """True only when the connection itself failed, so the engine never saw the request and a retry can't double it.
    A console that dropped mid-reply is not retried directly: the engine may still be working on it."""
    if isinstance(exc, requests.exceptions.ConnectTimeout):
        return True
    if not isinstance(exc, requests.ConnectionError):
        return False
    reason = getattr(exc.args[0], "reason", None) if exc.args else None
    from urllib3.exceptions import NewConnectionError
    return isinstance(reason, NewConnectionError) or "Failed to establish a new connection" in str(exc)


def local_request(method: str, url: str, timeout: float, **kw) -> requests.Response:
    """A request to a local engine, through the Model Console when it is up, else directly."""
    global _console_down_until
    via = console_url(url)
    if via and time.monotonic() >= _console_down_until:
        try:
            return requests.request(method, via, timeout=(5, timeout), **kw)
        except requests.RequestException as exc:
            if not _not_reached(exc):
                raise
            _console_down_until = time.monotonic() + CONSOLE_RETRY_S
            log.warning("model console not reachable at %s (%s); calling the engine directly at %s",
                        via, type(exc).__name__, url)
    return requests.request(method, url, timeout=timeout, **kw)


def local_api_base(url: str) -> str:
    """For clients we can't wrap (dspy): the console address if it answers now, else the engine's own."""
    via = console_url(url)
    if via:
        try:
            requests.get(via.rstrip("/") + "/api/tags", timeout=5)
            return via
        except requests.RequestException as exc:
            log.warning("model console not reachable at %s (%s); using the engine directly at %s",
                        via, type(exc).__name__, url)
    return url


def _is_local_engine(url: str) -> bool:
    return bool(_ENGINE.match(url))


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
    # 19 Nov 2026: "local" says the model runs on this machine; "api" says how to talk to it. Ollama has its own API;
    # the 35B on llama.cpp (aicli's start-llama.ps1) speaks the OpenAI one.
    api: str = "ollama"
    _last_call: float = 0.0
    exhausted: bool = False         # hit a daily limit during this run; skipped from then on

    def _pace(self) -> None:
        wait = self._last_call + self.min_interval_s - time.monotonic()
        if wait > 0:
            time.sleep(wait)
        self._last_call = time.monotonic()

    @property
    def key(self) -> str | None:
        if not self.key_env:
            return None
        return os.environ.get(self.key_env) or ("none" if self.local else None)   # a local server needs no real key

    def available(self) -> bool:
        if self.local and self.api == "openai":
            try:              # a llama.cpp server that is up lists its model; one that is down refuses at once
                return local_request("GET", self.base_url.rstrip("/") + "/models", 10).ok
            except requests.RequestException:
                return False
        if self.local:
            try:
                return local_request("GET", self.base_url.rstrip("/") + "/api/tags", 30).ok   # a busy Ollama can take a while to answer
            except requests.RequestException:
                return False
        return bool(self.key)

    def chat(self, system: str, user: str, temperature: float = 0.3, want_json: bool = True, careful: bool = False,
             schema: dict | None = None) -> str:
        if self.local and self.api != "openai":
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
            if _is_local_engine(url):       # llama.cpp on 8080 (or Ollama's /v1): through the Model Console
                r = local_request("POST", url, self.timeout, json=body, headers=headers)
            else:
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
                if data["choices"][0].get("finish_reason") == "length":
                    # 11 Nov 2026 (research: a digest truncated at its token cap while every dashboard stayed
                    # green): a reply cut off at the limit is a failure, never half an answer to parse
                    raise LLMError(f"{self.name} reply cut off at the token limit")
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
        r = local_request("POST", self.base_url.rstrip("/") + "/api/chat", self.timeout, json=body)
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
                            api=str(p.get("api", "ollama")),
                            # a stalled cloud call must fail inside the 40-minute job so the retry can run;
                            # a local model on a slow machine genuinely needs the long wait
                            timeout=float(p.get("timeout", 1800 if p.get("local") else 180))))
    return out


def local_providers(site_cfg: dict | None = None) -> list[Provider]:
    """The configured local writers that are up right now, best first (19 Nov 2026: the 35B, then the 7B)."""
    from . import config
    return [p for p in providers_from_config(site_cfg or config.site_config()) if p.local and p.available()]


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
