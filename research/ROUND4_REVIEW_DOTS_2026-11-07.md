

# BATCH r4_director (dots) 11-07 08:34



## Findings

After reviewing the four provided files against the round-2 fix list and owner spec, I found one real defect and a few minor issues.

---

### HIGH

**write_pack.py:237** — The `check` lambda in `call_path` passes the envelope JSON string to `retry_policy.answer_kind()` instead of the parsed text and finish_reason. `answer_kind()` checks `if text and text.strip()` — the envelope is always a non-empty JSON string, so it always returns `None`. This means the retry policy's empty-answer / cut-off detection is completely bypassed: empty or truncated model answers are never retried, they flow through as "success" and then crash later in `answer_text()` with a `ValueError` that stops the run.

- **Failing input**: A model returns an empty body. `stream_chat()` returns `("", "stop")`. `envelope()` produces `{"is_error": true, "result": "", ...}`. `call_with_retry` calls `check(envelope_json_string)` → `answer_kind(json_string)` → `None` (because the JSON string is non-empty). The call is treated as successful. Then `answer_text()` raises `ValueError("the model call failed or was cut off")`.
- **One-line fix**: Parse the envelope inside the check —
  ```python
  def _check_envelope(raw):
      try:
          data = json.loads(raw)
      except (ValueError, TypeError):
          return retry_policy.FATAL
      return retry_policy.answer_kind(data.get("result") or "", data.get("finish_reason"))
  ```
  and pass `check=_check_envelope` to `call_with_retry`.

---

### MEDIUM

**write_pack.py:282** — Operator precedence in `answer_text()` is correct but dangerously misleading. `"result" not in answer and not answer.get("is_error")` reads as `"result" not in (answer and not answer.get("is_error"))` to a casual reader. It happens to work because Python's `and` has higher precedence than `or`, but the next maintainer will likely "fix" it into a crash.

- **One-line fix**: Add explicit parentheses — `("result" not in answer) and (not answer.get("is_error"))`.

---

### LOW

**run_registry.py:377** — The file-path validator `":" in f` rejects legitimate Unix file names that contain a colon (e.g. `notes:2026.md`). This is a side effect of using `:` to catch Windows drive-letter paths.

- **One-line fix**: Only reject `:` when the path looks like a Windows drive path — `re.match(r"^[A-Za-z]:[\\/]", f)` instead of `":" in f`.

---

### UNVERIFIED

- **pack_validator.py:844** — `engine_for(engines, narr["language"])` is called with whatever `narr["language"]` is, without verifying it is a string first. If `voice_engine.engine_for()` does not handle non-string input gracefully, a malformed language value (e.g. a number) would crash `_check_voice` at a trust boundary. I do not have `voice_engine.py` to confirm.
- **write_pack.py:877** — `stage_setting(stage_model, name, model if v == via else None) or DEFAULT_MODEL[v]`: if `stage_model` table contains an explicit empty-string value for a stage, `"" or DEFAULT_MODEL[v]` silently falls back to the default. `parse_stage_map` rejects empty values, so this is currently unreachable, but it is a latent footgun.

---

FINAL:
1. **HIGH** `write_pack.py:237` — `check` lambda passes envelope JSON to `answer_kind` instead of parsed text; empty/cut-off answers are never retried.
2. **MEDIUM** `write_pack.py:282` — misleading operator precedence in `answer_text()` guard.
3. **LOW** `run_registry.py:377` — `":" in f` rejects valid Unix file names containing colons.
4. **UNVERIFIED** `pack_validator.py:844` — `engine_for` may receive a non-string language at a trust boundary.
5. **UNVERIFIED** `write_pack.py:877` — empty-string stage-model value would silently fall back to default (currently unreachable).


# BATCH r4_h3 (dots) 11-07 08:42



## ROUND 3 review — provided files only

I checked the five files you supplied. The round-2 fixes inside them (non-object `timing_and_lattice`/`episode_plan` guards, per-language PLAN-01, TIME-01, empty-BGM=no-BGM, reel-id sanitisation, default language `hi`) are correct and do not break anything I can see. The UI / `server.py` / `pipeline.js` / `compile_h3_sing8.py` / `run_registry` were **not provided**, so those round-2 fixes are **unverified**.

Real defects found:

---

**severity: medium — v4_to_h3.py:644-645 / schema_and_linter.py:173 / render_controller.py:549 / gate_d_audio.py:813**
`v4_to_h3` writes `voice_engine` onto the **story** top level (`story["voice_engine"]`), but every consumer reads it from the **registry**: `voice_mode(reg)` in schema_and_linter, `reg.get("voice_engine")` in render_controller `_gate_d_result`, and `engine_for(voice_engines, …)` in gate_d_audio. A converted story therefore has `registry["voice_engine"] == None`, so `voice_mode()` is always False (linter treats the story as pure Foley, VA-* checks are dead) and every language renders with ElevenLabs — the off-by-default English H3 second render can never be produced. Impact of whether `run_registry`/the UI copies it into the registry is **unverified**.
One-line fix: write it into `registry` in `v4_to_h3` (or read it from `story` level in the three consumers).

**severity: medium — schema_and_linter.py:396-398 (`resolve_keyframes`)**
When `fl2va_keyframes.picture_1_path` is absent the function returns `picture_1: None` immediately and never looks at `reuse_upstream_b_id`, so the reuse branch is unreachable without a placeholder path. The schema makes both `picture_1_path` and `reuse_upstream_b_id` optional, so a hand-authored CHAINED shot that sets only `reuse_upstream_b_id` gets spurious `KF-06` (line 640, which reads the raw `k.get("picture_1_path")`) and `CN-09` (line 676) errors. (`v4_to_h3` avoids this by always setting `picture_1_path` directly, so the converter output is fine.)
One-line fix: in the `own is None` branch, if `reuse_upstream_b_id` is set and `upstream_shot_or_None` exists, return its `picture_2_path` with `reused: True`.

**severity: low — schema_and_linter.py:718-721**
`_check_sound_plan` SD-01 documents "non-empty **single sentence** of at least 40 characters" but only tests `len(soundscape) < 40`; a multi-sentence shot soundscape of 1–4 sentences passes SD-01 (only SX-01 on the compiled line would notice). Docstring/code mismatch.
One-line fix: add a sentence-count check (or align the docstring).

**severity: low — gate_d_audio.py:222 / voice_manifest.py:90**
`vo_fit_check` does `float(it["editorial_duration_sec"])`; the `voice_manifest` CLI path builds entries with `shot.get("editorial_duration_sec")` (None when absent) and calls `vo_fit_check` unwrapped, so a shot that has narration text but no `editorial_duration_sec` crashes with `TypeError`. (The render path passes pre-converted floats, so it is safe.)
One-line fix: guard `ed` in `vo_fit_check` or skip/`VO_UNREADABLE` when it is not a number.

**severity: low — render_controller.py:328-333, 622**
The `--allow-partial` writing loop has no `try/except`, and `main` catches `(OSError, ValueError, KeyError, TypeError)` — not `AttributeError`. If `_write_shot` (or a compile call it makes) raises `AttributeError` after some shots were already written, the program tracebacks instead of reporting exit 1, leaving partial outputs on disk.
One-line fix: wrap the partial loop, and add `AttributeError` to `main`'s except tuple.

---

FINAL:
1. medium — v4_to_h3.py:644-645 writes `voice_engine` to story level; schema_and_linter.py:173, render_controller.py:549, gate_d_audio.py:813 read it from the registry → English H3 voice unreachable (unverified whether another module bridges it).
2. medium — schema_and_linter.py:396-398 `resolve_keyframes` ignores `reuse_upstream_b_id` when `picture_1_path` is absent → false KF-06/CN-09 on valid hand-authored CHAINED shots.
3. low — schema_and_linter.py:718-721 SD-01 docstring promises a single-sentence check; code only checks length.
4. low — gate_d_audio.py:222 / voice_manifest.py:90 `vo_fit_check` crashes on `None` `editorial_duration_sec` in the voice-manifest CLI path.
5. low — render_controller.py:328-333, 622 `--allow-partial` unwrapped; `AttributeError` not caught by `main`.


# BATCH r4_ui (dots) 11-07 09:03



**1. medium** – `pipeline.py:684-686` (summary loop)  
Every shot without an episode is skipped by `continue`, so `total_seconds` misses their duration.  
*Failing input:* a pack with three shots (two in episode 1, one with `episode: null`), each 10 s → summary reports 20 s instead of 30 s.  
*Fix:* move `total_seconds += max(sec, 0.0)` before the `if ep is None: continue` and remove the duplicate inside the episode block.

**2. medium** – `server.py:798` (render_status images dict)  
The `images` object only contains `expected`; the client (pipeline.js) expects `final` to show progress.  
*Failing input:* render card shows “Images: -/123 final” instead of “Images: 5/123 final”.  
*Fix:* add a `final` count (from `facts()` or by globbing `__final.png`) to the `images` dict.

**3. medium** – `server.py:1448-1460` (author_status response shape)  
The server returns a `shots` array with per‑shot `missing`/`cache`, but the client expects top‑level `derived`, `missing` (array) and `cache`.  
*Failing input:* author panel shows “Derived by rule: - Missing: 0” and “Cache: -”; the missing‑fields table stays empty.  
*Fix:* either aggregate `derived`/`missing` from `shots` in the server response, or update the client to read `a.shots` and build the view from it.

FINAL:
1. pipeline.py summary total_seconds excludes shots without episode (medium)
2. server.py render_status missing final image count (medium)
3. server.py author_status response shape mismatch with client (medium)


# BATCH r4_tests (dots) 11-07 09:22



Based on my analysis of the test files and fix descriptions, here are my findings:

**test_r3_pack_validator.py** — no findings. The ML-01 label-mismatch test is correctly structured.

**test_r3_retry_policy.py** — no findings. The zero-attempts refusal test is valid.

**test_r3_run_registry.py** — no findings. Empty voice_engine map refusal and valid-map acceptance are correctly tested.

**test_r3_simple_language.py** — no findings. The closing-quote split test, long-sentence flag, and caption language validation tests are logically sound. (The string literal `"…” "` relies on a Unicode right-double-quote U+201D inside ASCII delimiters; if the source file is correctly encoded this is valid, but this is fragile and **unverified** as to whether the actual `simple_language.py` splitter handles the exact boundary the test intends.)

**test_r3_write_pack.py** — no findings. The StageFailed tests for unusable episode numbers and unparsable saved answers are correct.

**test_r3_gate_d_audio.py** — no findings. The non-object block cases and the `_gate_d_result` AttributeError survival test are valid.

**test_r3_render_controller.py** — no findings. Negative-frame clamping to 0 seconds is correctly tested.

**test_r3_schema_and_linter.py** — no findings. The malformed profile/registry tests (PO-01, PO-02, PO-06, PR-08, SX-01 survival) are valid.

**test_r3_v4_to_h3.py** — no findings. Infinity/NaN and scalar character_positions tests are valid.

**test_r3_voice_manifest.py** — no findings. Non-object row skipping is correctly tested.

**test_r3_fixes.py** — no findings in the individual assertions. However, the test on line 90 contains a comment referencing an "R4 fix" which is out of place for a round-3 test (cosmetic only, does not affect logic).

---

**Unverified fixes (no test coverage, cannot confirm correctness):**
- `h3 router.py` ref lists (RF-03, non-dict keyframes) — no test.
- `compile_h3_sing8.py` compile_episode wrapping TypeError/ValueError/AttributeError — no direct test (the `_gate_d_result` test in test_r3_gate_d_audio.py exercises a different module).
- `pipeline.js` Save-story keeping a pack only for the same story — no test.
- `loadDetail` single-flight with rerun — no test.
- `ui/static/app.js` sending X-UI on every request — the test checks for AbortController/120000 but does **not** verify the X-UI header itself.
- Owner-spec items "approvals scoped by story+pack", "Gate A blocked on validator errors", "UI binds 127.0.0.1" — no test coverage.

---

**Partially verified:**
- "episode sort on mixed types" — the test only uses integer episodes with an unhashable list id; mixed-type episode values (e.g., int vs string) are **unverified**.

FINAL:
1. medium, unverified — `h3/router.py` ref-list fix (RF-03, non-dict keyframes) has no test; correctness cannot be confirmed.
2. medium, unverified — `compile_h3_sing8.py` compile_episode exception-wrapping fix has no direct test.
3. medium, unverified — `pipeline.js` Save-story same-story pack guard has no test.
4. medium, unverified — `loadDetail` single-flight with rerun has no test.
5. low, unverified — `app.js` X-UI header on every request is not tested (only AbortController/timeout is checked).
