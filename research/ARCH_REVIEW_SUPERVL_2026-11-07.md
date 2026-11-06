

# BATCH b1_validator_writer (supervl) 11-07 02:03

Grouped by file, with concrete failing inputs and one-line fixes.

=== FILE pack_validator.py ===

**High** — pack_validator.py:493-498 — ML-06 (narration beyond shot duration) is only checked inside `narration_by_lang`. For single-language packs (no `narration_by_lang`), the primary `narration.time_range` is added to the timing comparison but its end is never compared against `editorial_duration_sec`, so a 20 s narration on a 7 s shot passes.
Failing input: a shot with `editorial_duration_sec: 7.0` and `narration: {text, language: "en", time_range: [0.5, 20.0]}`, `output_languages=["en"]` — no ML-06 is raised.
Fix: after the `narration_by_lang` block, add an ML-06 check for `primary` narration `time_range[1] > editorial + TIME_TOL`.

**Medium** — pack_validator.py:294 — `_check_audio` validates dialogue entries for `speaker`, `text`, and `time_range`, but never checks the required `tone` field (spec Col 6: speaker, text, tone, time range).
Failing input: `dialogue: [{"speaker": "S1", "text": "Namaste", "time_range": "0.5-1.0s"}]` (no `tone`) — passes AUD-03 but should fail.
Fix: add `and _nonempty_str(x.get("tone"))` to the dialogue entry condition.

**Medium** — pack_validator.py:469-472 — when any `*_by_lang` key is present, all three (`narration_by_lang`, `dialogue_by_lang`, `captions_by_lang`) are required (ML-03), so a shot with multilingual narration but no dialogue/captions is falsely rejected.
Failing input: a shot with `narration_by_lang` for en/hi/mr but no `dialogue_by_lang`/`captions_by_lang` keys, `output_languages=["en","hi","mr"]` — ML-03 wrongly reports missing keys.
Fix: only require `*_by_lang` keys that are actually present; treat absent/null `dialogue_by_lang` and `captions_by_lang` as optional (empty dialogue is valid).

**Medium** — pack_validator.py:262 — `exited_character_status` entries check `isinstance(x.get("off_stage_shots"), int)`, which accepts `bool` because `isinstance(True, int)` is true, letting a boolean slip through as a shot count.
Failing input: `exited_character_status: [{"id": "C1", "left_after_shot": 1, "off_stage_shots": true, "released": false}]` — passes the type check though `true` is not a shot count.
Fix: use `isinstance(x, int) and not isinstance(x, bool)` (same pattern as `lattice_n` at line 553).

**Low** — pack_validator.py:256-258 — `character_positions` validates that `screen` and `depth` keys exist but not that they are non-empty strings, so empty values pass.
Failing input: `character_positions: [{"id": "C1", "screen": "", "depth": ""}]` — passes but should fail.
Fix: add `_nonempty_str(x.get("screen")) and _nonempty_str(x.get("depth"))` to the `all(...)` condition.

=== FILE writer_prompts.py ===

No verifiable defects in the provided source (all numeric limits are imported from `h3/shot_table_spec.py`, which is not included, so constants like `CAPTION.max_words` cannot be confirmed or contradicted here).

=== FILE OWNER_MASTER_PROMPT_V4_2026-11-07.txt ===

Spec text only; no code defects. Note: the owner decision (bottom margin 896) contradicts the spec text (MarginV = 467), but neither is implemented in the reviewed code, so there is no actionable code defect.

FINAL:
1. High — pack_validator.py:493-498 — primary (single-language) narration `time_range` is never checked against `editorial_duration_sec` (ML-06 only covers `narration_by_lang`), allowing narration to exceed the shot length.
2. Medium — pack_validator.py:294 — dialogue entries are not validated for the required `tone` field.
3. Medium — pack_validator.py:469-472 — all three `*_by_lang` keys are required when any one is present, falsely rejecting shots with narration but no dialogue/captions.
4. Medium — pack_validator.py:262 — `off_stage_shots` type check accepts `bool` via `isinstance(x, int)`.
5. Low — pack_validator.py:256-258 — `character_positions` checks key presence but not that `screen`/`depth` are non-empty strings.


# BATCH b2_write_pack_lang (supervl) 11-07 02:07

=== FILE write_pack.py ===

severity: high
file:line: write_pack.py:281
why: `ids = [s["id"] for s in shots]` indexes `"id"` on every shot object with no validation. Model output is untrusted, so a shot object missing `"id"` raises `KeyError` and crashes the run instead of a clean validation error.
concrete failing input: A single-call or staged answer whose ` ```json shots ` block is `[{"action": "walk", "seconds": 2}]` (a shot object with no `id` key).
one-line fix: Before building `ids`, validate each shot: `for s in shots: if not isinstance(s.get("id"), str): raise ValueError("shot missing string id")`.

severity: high
file:line: write_pack.py:339
why: `found = [v if isinstance(v, int) else v["episode"] for v in json.loads(block.group(1))]` assumes every entry in the ` ```json episodes ` block is either an int or a dict with an `"episode"` key. A malformed entry raises `KeyError` or `TypeError` and crashes stage 1.
concrete failing input: A stage 1 answer containing ````json episodes [{"title": "first"}] ```` (dict without `episode`) or `[1, "two"]`.
one-line fix: Validate each entry before use, e.g. `if isinstance(v, int): found.append(v); elif isinstance(v, dict) and isinstance(v.get("episode"), int): found.append(v["episode"]); else: raise ValueError("bad episode entry")`.

severity: medium
file:line: write_pack.py:374
why: The `len(flat) > 999` guard sits after the `return flat` early-return, so when all shot IDs are already unique the limit is never enforced and 1000+ shots pass through, breaking the SHOT-NNN id rule.
concrete failing input: 1000 shots with unique IDs (e.g. SHOT-001 … SHOT-1000) across episodes, so no id collision triggers the renumber path.
one-line fix: Move the `if len(flat) > 999: raise ValueError(...)` check before the `return flat` early return.

severity: medium
file:line: write_pack.py:172
why: `key = OPENROUTER_KEY.read_text(encoding="utf-8").strip()` raises `FileNotFoundError` when the OpenRouter key file is absent, but `call_openrouter` only catches `urllib.error.HTTPError`, so the crash propagates out of the run.
concrete failing input: Running `python write_pack.py story.md out --via openrouter --model x:free` with `OPENROUTER_KEY_FILE` pointing to a nonexistent file.
one-line fix: Wrap the key read in `try/except OSError` and raise a clear `RuntimeError` naming the missing key file.

severity: medium
file:line: write_pack.py:160
why: `openrouter_is_free` fetches the OpenRouter catalog with `urllib.request.urlopen(...)`; a network failure raises `URLError`, which is not caught in `call_openrouter` (only `HTTPError` is caught), so the run crashes instead of refusing or degrading.
concrete failing input: Running `--via openrouter` with no network access so the catalog request fails.
one-line fix: Catch `urllib.error.URLError` around the `openrouter_is_free` call in `call_openrouter` and treat the model as unavailable/refused.

severity: low
file:line: write_pack.py:220
why: `json_lines` uses `line.strip().rstrip(",")`, which strips *all* trailing commas and corrupts a JSON string value that legitimately ends with a comma (e.g. `"stop,"` becomes `"stop"`).
concrete failing input: Nemotron emits one JSON per line: `{"text": "stop,"}`.
one-line fix: Strip only a single trailing comma when the line is a list/object separator, or parse lines with a tolerant JSON parser instead of `rstrip(",")`.

=== FILE simple_language.py ===
no findings

=== FILE retry_policy.py ===
no findings

FINAL:
1. write_pack.py:281 — unchecked `s["id"]` on untrusted model output crashes with `KeyError` when a shot lacks an id; validate shot ids before use.
2. write_pack.py:339 — `v["episode"]` on malformed ` ```json episodes ` entries crashes with `KeyError`/`TypeError`; validate each episode entry.
3. write_pack.py:374 — the 999-shot cap is bypassed when all ids are unique because the check is after the early `return flat`; move the check before it.
4. write_pack.py:172 — missing OpenRouter key file raises uncaught `FileNotFoundError`; wrap the read in `try/except OSError`.
5. write_pack.py:160 — OpenRouter catalog network failure raises uncaught `URLError`; catch it and treat the model as unavailable.


# BATCH b3_state_ops (supervl) 11-07 02:10

### run_registry.py

**medium** — run_registry.py:366-367 — `voice_engine` validation accepts `"h3"` for any language, but the owner decision restricts `h3` to English only (en/hi/mr voices are ElevenLabs added after render; `h3` is an off-by-default English-only second render). So `{"hi": "h3"}` or `{"mr": "h3"}` is wrongly accepted instead of rejected.
- Failing input: `append_event(story_dir, run, "spec_built", None, "ok", voice_engine={"hi": "h3"})` returns normally; it should raise `ValueError`.
- One-line fix: extend the condition on :366-367 with `and all(v != "h3" or k == "en" for k, v in engines.items())`.

### story_state.py

**high** — story_state.py:201 (IndexError surfaces at :117) — `summarize` can select a pack as `resume` even when every expected stage is present and OK but the pack is not finished (no `PACK.md`/`shots.json`). Then `stages_missing == []` and `failed_stages == []`, so `_next_step` indexes `resume["stages_missing"][0]` on :117 and raises `IndexError: list index out of range`, crashing the CLI/summary.
- Failing input: `stories/<slug>/` with `SOURCE.md` and a pack `pack_w_20261107_v1/` containing valid non-failed `stage_1_raw.json`, `stage_2_raw.json`, `stage_5_raw.json` but no `PACK.md`/`shots.json`, and no finished pack. `python director/story_state.py <slug>` crashes.
- One-line fix: on :201, only consider packs with work left: `newest_open = max([p for p in unfinished if p["stages_missing"] or p["failed_stages"]], key=lambda p: p["_ts"], default=None)`.

story_links.py and ops_checks.py: no real defects found (validation, locking, and caps look correct; nothing calls Colab/ElevenLabs/ffmpeg/a model). secret_scan.py: no real defects found.

FINAL:
1. high — story_state.py:201 — `resume` can target a fully-present but unfinished pack, making `_next_step` index `resume["stages_missing"][0]` on an empty list and crash `summarize` with `IndexError`; fix by filtering `unfinished` to packs with `stages_missing` or `failed_stages` at :201.
2. medium — run_registry.py:366-367 — `voice_engine` lets `"h3"` map to any language, violating the owner rule that `h3` is English-only; fix by adding `and all(v != "h3" or k == "en" for k, v in engines.items())`.


# BATCH b4_h3_linter (supervl) 11-07 02:13

=== FILE schema_and_linter.py ===

high, schema_and_linter.py:470 (also 479 and 292): `_check_timing` and `mouth_state_problems` divide by `fps` without validating it is nonzero, and `ZeroDivisionError` is not in `_run`'s caught exception tuple, so `fps = 0` crashes `lint_story` instead of logging a rule error. Concrete failing input: a profile with `"fps": 0` and any shot with valid timing. One-line fix: validate `fps > 0` (and add `ZeroDivisionError` to `_run`) before any `pf / fps` division.

high, schema_and_linter.py:181: `refuse_speech_in_source` raises `SL-04` for *any* utterances in pure-Foley mode, but the owner routes en/hi/mr voices through ElevenLabs after render, so utterances are valid source metadata that must be allowed (the H3 prompt still excludes speech). Concrete failing input: a pure-Foley shot whose `dialogue_and_lip_lock.utterances` holds an ElevenLabs Hindi line. One-line fix: remove the `if utterances and not voice: raise PromptRefused("SL-04", ...)` refusal; keep refusing speech patterns only in free text.

high, schema_and_linter.py:402-423 (called unwrapped at line 902): `lint_profile` indexes `model_sampling_av`, `base_resolution`, and `aspect_ratio` without type validation, so a malformed profile raises `AttributeError`/`ValueError` and crashes `lint_story` instead of emitting a `PO` error. Concrete failing input: a profile with `"base_resolution": "1920x1080"` or `model_sampling_av` as a string. One-line fix: validate profile structure/types before indexing and report `PO` errors rather than letting exceptions escape.

medium, schema_and_linter.py:354: `load_default_profile` builds a path from unchecked `name`, allowing directory traversal. Concrete failing input: `load_default_profile("../../../etc/passwd")`. One-line fix: restrict `name` to `ID_PATTERN` or `os.path.basename(name)` before joining.

medium, schema_and_linter.py:919: `lint_story` indexes `ep["asset_root"]` without validation, crashing on an episode missing `asset_root`. Concrete failing input: an episode dict with no `"asset_root"` key. One-line fix: validate episode structure and report a story-level error instead of indexing directly.

=== FILE compile_h3_sing8.py ===

high, compile_h3_sing8.py:184 (root cause lines 142/145): `compile_episode` calls `compile_comfyui_workflow` without `try/except`; it indexes `mode_to_lora_map` and calls `video_shift_for`, so a missing LoRA entry or shift raises `KeyError` and crashes. Concrete failing input: a profile whose `mode_to_lora_map` lacks the `route_namespace` key. One-line fix: wrap the call in `try/except` (or validate the keys first) and raise `ValueError` on missing config.

medium, compile_h3_sing8.py:171: `compile_episode` uses `next(...)` with no default, raising `StopIteration` for a missing `episode_id`. Concrete failing input: `compile_episode(story, "nonexistent", out_dir)`. One-line fix: use `next(..., None)` and raise `ValueError` when the episode is not found.

=== FILE router.py ===
no findings

=== FILE shot_table_spec.py ===
no findings

FINAL:
1. high, schema_and_linter.py:470 — `fps = 0` causes an uncaught `ZeroDivisionError` in `_check_timing`/`mouth_state_problems`, crashing `lint_story`; validate `fps > 0` (and catch `ZeroDivisionError` in `_run`).
2. high, schema_and_linter.py:181 — `refuse_speech_in_source` blocks all utterances in pure-Foley mode, contradicting the owner's ElevenLabs post-render voice route for en/hi/mr; drop the `SL-04` utterance refusal.
3. high, compile_h3_sing8.py:184 — `compile_comfyui_workflow` is called unwrapped in `compile_episode`, so a missing LoRA/shift key crashes with `KeyError`; wrap it in `try/except` and report a `ValueError`.
4. high, schema_and_linter.py:402-423 — `lint_profile` is called unwrapped at line 902 and crashes on malformed profile types instead of emitting `PO` errors; validate the profile structure first.
5. medium, schema_and_linter.py:354 — `load_default_profile` allows path traversal via unchecked `name`; restrict to `ID_PATTERN`/`basename`.


# BATCH b5_gate_d (supervl) 11-07 02:27

=== FILE gate_d_audio.py ===

**High** — `gate_d_audio.py:829` — `same_timing_problems` calls `parse_time_range(x["time_range"])` on untrusted shot data. A malformed `time_range` (e.g. `"not-a-range"` or `"5-2s"`) raises `ValueError` and crashes the entire planner before any per-language report is produced, instead of returning a recordable `TIME-01` error.  
Failing input: a shot with `"narration_by_lang": {"en": {"text": "x", "time_range": "bad"}}`.  
Fix: wrap the `parse_time_range` call in `try/except ValueError` and append a `TIME-01` error dict.

**High** — `gate_d_audio.py:648` — `_caption_cues` calls `parse_time_range(rng)` on untrusted narration/caption time ranges without catching `ValueError`. A bad range crashes `_caption_cues` and aborts that language’s plan.  
Failing input: `"narration": {"text": "hi", "language": "en", "time_range": "not-a-range"}` with `languages=["en"]`.  
Fix: catch `ValueError` around `parse_time_range(rng)` and skip/record the bad cue.

**High** — `gate_d_audio.py:733-762` — The `if not errors:` block builds the mix filter and mux argv but does not catch `ValueError` from `build_mix_filter` or `build_final_mux_argv`. An exception there crashes the whole multi-language run, violating the documented contract that a failing language gets no mix/mux and does not affect the others.  
Failing input: any edge case that makes `build_mix_filter` raise (e.g. `total <= 0` or an empty SFX clip list reaching it).  
Fix: wrap the mix/mux construction in `try/except ValueError` and append the error so the language is skipped gracefully.

**Medium** — `gate_d_audio.py:235-236` — `validate_bgm_manifest` emits `BGM_MANIFEST_EMPTY` when `tracks` is an empty list, but the owner decision makes BGM optional (default none). An explicit `{"tracks": []}` (no BGM wanted) blocks the reel.  
Failing input: `bgm_manifest={"tracks": []}`.  
Fix: remove the empty-tracks error (treat empty `tracks` as no BGM / return `None` path).

**Medium** — `gate_d_audio.py:729` — `export = f"{export_dir}/{reel}_{lang}.mp4"` interpolates unvalidated `reel` into a filesystem path, allowing path traversal (`../../../tmp/evil`).  
Failing input: `reel="../../../tmp/evil"`.  
Fix: validate/sanitize `reel` (reject `..`, `/`, `\`) before interpolating.

**Low** — `gate_d_audio.py:113` — `check_opening_hook` calls `parse_time_range(c["time_range"])` on `sfx_cues` without catching `ValueError`; a malformed cue time range crashes the opening-hook check.  
Failing input: `"sfx_cues": [{"time_range": "bad"}]` on the opening shot.  
Fix: wrap `parse_time_range` in `try/except ValueError` and treat bad cues as non-hits or record an error.

=== FILE voice_engine.py ===

no findings

=== FILE voice_manifest.py ===

**Low** — `voice_manifest.py:121` — `doc["shots"]` raises `KeyError` when the shots JSON is a dict without a `"shots"` key, crashing the CLI instead of a clean error.  
Failing input: `--shots` file containing `{"other": []}`.  
Fix: validate the doc shape (`isinstance(doc, dict) and "shots" in doc`) before indexing.

---

FINAL:
1. `gate_d_audio.py:829` — `same_timing_problems` crashes on malformed `time_range` instead of returning a `TIME-01` error (High).
2. `gate_d_audio.py:648` — `_caption_cues` crashes on malformed caption/narration `time_range` instead of reporting it (High).
3. `gate_d_audio.py:733-762` — Uncaught `ValueError` from `build_mix_filter`/`build_final_mux_argv` aborts the whole planner instead of failing just that language (High).
4. `gate_d_audio.py:235-236` — `BGM_MANIFEST_EMPTY` for `"tracks": []` contradicts the owner’s optional-BGM decision (Medium).
5. `gate_d_audio.py:729` — Unsanitized `reel` interpolated into the export path enables path traversal (Medium).


# BATCH b6_controller (supervl) 11-07 02:34

### render_controller.py

**Medium, render_controller.py:307** — `seconds` is always `None` for realistic float frame rates (e.g. 23.98) because the guard requires `isinstance(fps, int)`; a profile with `"fps": 23.98` and `"pixel_frames": 100` yields `seconds: null` instead of ~4.17. `isinstance(pf, int)` is also overly strict for JSON numbers. Fix: accept `(int, float)` for both and require `fps != 0`.

**Medium, render_controller.py:102-103** — `asset_root` is normalized but never confined to the story folder; an absolute or `..`-laden value escapes the story directory and lets `_picture_rows` read arbitrary files (e.g. `asset_root: "/etc"` with `picture_1: "passwd"`). Fix: after normalization, reject the path unless it resolves inside the story folder.

**Medium, render_controller.py:560** — `plan_pipeline` defaults `languages` to `["en"]` when no `output_languages` exists, so Hindi and Marathi reels are never planned despite the owner's en/hi/mr voice requirement. Fix: default to `["en", "hi", "mr"]` (or require explicit selection).

**Low/unverified, render_controller.py:536-537** — `_gate_d_result` unconditionally includes `en_h3` in the video plan, contradicting "rendered ONCE" and "h3 English is off-by-default second render" unless `plan_language_outputs` ignores it. (unverified — `gate_d_audio` is not shown)

### fallback_policy.py

**High, fallback_policy.py:122,126,130** — `split_shot_row` subscripts `narration["time_range"][0]`, `dlg["time_range"][0]`, and `cue["time_range"]` without validating their shape, so a row like `{"narration": {"time_range": None}}` raises `TypeError`/`KeyError` and aborts the fallback decision. Fix: validate each `time_range` is a list/tuple of two numbers before use.

### pipeline_contract.py

No findings.

### asset_manifest.py

No findings.

### step9_qc.py

No findings.

FINAL:
1. render_controller.py:307 — `seconds` is `None` for float FPS (e.g. 23.98) due to `isinstance(fps, int)`; accept `(int, float)` and `fps != 0`.
2. fallback_policy.py:122,126,130 — `split_shot_row` crashes on missing/malformed `time_range` in narration/dialogue/sfx; validate the range structure before subscripting.
3. render_controller.py:102-103 — `asset_root` escapes the story folder (absolute/`..`), enabling arbitrary file reads; confine it to the story directory.
4. render_controller.py:560 — `plan_pipeline` defaults languages to `["en"]`, dropping hi/mr reels; default to `["en", "hi", "mr"]`.
5. render_controller.py:536-537 — `en_h3` is unconditionally planned, contradicting the single-render / off-by-default h3 rule (unverified without `gate_d_audio`).
