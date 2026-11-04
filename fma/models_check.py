"""List the models each configured provider's key can use, and probe a few with a one-token call.

Run by the "Check models" workflow, where the keys are. Prints model ids, HTTP status and the rate-limit
headers a provider sends back; never the key. Used to pick fallback models with their own daily quotas
(4 Nov 2026: Groq's daily tokens ran out and Gemini was overloaded, so the post was skipped)."""
from __future__ import annotations

import sys

import requests

from . import config
from .llm import providers_from_config

LIMIT_HEADERS = ("x-ratelimit-limit-requests", "x-ratelimit-limit-tokens", "x-ratelimit-remaining-requests",
                 "x-ratelimit-remaining-tokens", "retry-after")


def main(probe: list[str]) -> int:
    for p in providers_from_config(config.site_config()):
        if p.local or not p.key:
            print(f"== {p.name}: no key here, skipped")
            continue
        headers = {"Authorization": f"Bearer {p.key}"}
        base = p.base_url.rstrip("/")
        try:
            r = requests.get(base + "/models", headers=headers, timeout=30)
            ids = sorted(m.get("id", "") for m in r.json().get("data", [])) if r.ok else []
            print(f"== {p.name}: HTTP {r.status_code}, {len(ids)} models")
            for i in ids:
                print("   ", i)
        except (requests.RequestException, ValueError) as exc:
            print(f"== {p.name}: model list failed: {type(exc).__name__}")
            ids = []
        for model in [p.model] + [m for m in probe if m.split(":", 1)[0] == p.name]:
            model = model.split(":", 1)[-1]
            body = {"model": model, "max_tokens": 1, "messages": [{"role": "user", "content": "Say ok"}]}
            try:
                r = requests.post(base + "/chat/completions", json=body, headers=headers, timeout=60)
                limits = {h: r.headers[h] for h in LIMIT_HEADERS if h in r.headers}
                note = "" if r.ok else " " + r.text[:160].replace("\n", " ")
                print(f"   probe {model}: HTTP {r.status_code} {limits}{note}")
            except requests.RequestException as exc:
                print(f"   probe {model}: failed: {type(exc).__name__}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
