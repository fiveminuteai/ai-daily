# 7B vs 35B on Five Minute AI's duo work: result (19 Nov 2026)

Asked by Pavan through the aicli session (14 Nov): compare qwen2.5:7b with Qwen3.6-35B (qwen3.6-35b-a3b) on the
duo Reel work, at least 3 samples per story per model, a blind A/B read with criteria written first, and a
recommendation with the config change, **not applied**.

**How it was run:**
- `docs/pilots/compare_models.py` under the shared heavy-job lock (`compare_locked.py`). Local models only, no cloud
  keys in the process.
- 6 stories (11-12 Nov), 3 samples each, so 18 per model. The same prompts and code checks as the nightly shadow
  test: the rules, the code fact-checker on Spark's lines, and the length cap.
- The 7B ran 15 Nov 04:19-05:23 (64 min); the 35B ran 16 Nov 23:36-23:55 (19 min, its server already loaded).
- **The memory wait:** the 35B half waited about two days for memory; the machine rarely had the 13 GB free that
  starting the 35B needs.

## Code checks
| | 7B (Ollama) | 35B (llama.cpp) |
|---|---|---|
| Scripts that passed every check | 2 of 18 | **6 of 18** |
| Passed with every fact confirmed by the code checker | 0 | **2** |
| Unfinished (gave up within the retries) | 4 | 3 |
| Median time per script | 108 s | **65 s** |
| Most common failure | facts unsupported (9) or unsure (9) | facts unsupported (9) or unsure (6) |

## Blind read
- **Setup:** criteria in `fma-compare/CRITERIA.md`, written 15 Nov before any sample was seen. One script per model
  per story (its best of three), shown as A and B in a fixed shuffled order. All scored in
  `fma-compare/BLIND-SCORES.md` before `BLIND-KEY.json` was opened.
- **Result: the 35B won all six stories, 55 points to 39.**
- **Notable on the 7B side:**
  - one script carries leaked model markup ("}]<tool_call> system {") in a line meant to be spoken;
  - one repeats a single joke formula four times ("More X, less Y");
  - one reads out "CursorBench 4.0" and "/swarm";
  - one guest joke misreads its own line (a lower valuation called "more debt").
- **The 35B's best lines** stay in character:
  - "My calculator just filed for retirement" (Anthropic's IPO price);
  - "Scientific research? I'm the primary exhibit" (Rex, Gemini 4 Carbon);
  - "Is that a model or a cardboard box?"

## Verdict, by the rules set before reading
- **35B preferred.**
- It wins 6 of 6 stories (the bar was 4).
- Its pass rate is higher (6 against 2; the bar was "no lower").
- Its median time is 65 s (the bar was under 10 minutes).

## Recommendation
Make the 35B the local writer: the nightly shadow test, local runs, and any future local backup writer.

**This does not touch the daily post.** It runs on GitHub Actions with Groq, then Gemini, and cannot reach a model on
the laptop.

## The exact change (not applied)
1. **`config/site.yaml`, the local provider.** It still names qwen2.5:14b, which is not installed, so it is stale
   anyway. Replace:
   ```yaml
     - {name: ollama, base_url: "http://localhost:11434", model: "qwen2.5:14b", key_env: null, local: true}
   ```
   with:
   ```yaml
     # 35B on this laptop through llama.cpp (aicli's start-llama.ps1), OpenAI-style API; won the 19 Nov comparison
     - {name: llama, base_url: "http://127.0.0.1:8080/v1/", model: qwen3.6-35b-a3b, key_env: LLAMA_LOCAL_KEY,
        local: true, api: openai, timeout: 900,
        extra: {chat_template_kwargs: {enable_thinking: false}, max_tokens: 1500}}
   ```
2. **`fma/llm.py`, so `local: true` can also mean an OpenAI-style server.** Today `local` means Ollama's own API.
   - Add `api: str = "ollama"` to `Provider`, and pass `api=p.get("api", "ollama")` in `providers_from_config`.
   - In `chat()`, use `_openai` when `self.api == "openai"`, even if `local`.
   - In `available()`, check `GET {base_url}models` for `api == "openai"` instead of `/api/tags`.
   - Default `LLAMA_LOCAL_KEY` to "none".
   - With the Model Console change (199b7f0, still unpushed) these calls also show up in the console, with the
     direct fallback.
3. **`fma/shadow.py` and the nightly tuning script:** switch the shadow test's default from `qwen2.5:7b` to the
   provider above.
4. **Before step 3, the tuned prompts.** `data/tuned/local.json` holds prompts picked by scoring the 7B, and
   `duo_desk.tuned()` applies them to any local model. Key that file by model name, so the 35B starts from the
   built-in prompts this comparison used. Then run one judge-only tuning pass on the 35B (see the 15 Nov answer on
   training carry-over).
5. **Memory:** the 35B needs 13 GB free to start, which this machine rarely had in the last week. Starting it stays
   with aicli's `start-llama.ps1`, so it is not a child of any FMA job. Whatever uses it waits for an idle slot.

**Raw samples and logs:** `C:\Users\saipa\Personal\Projects\AI\fma-compare\`.
