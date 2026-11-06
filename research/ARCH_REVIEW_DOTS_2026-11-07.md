

# BATCH b1_validator_writer (dots) 11-07 02:03



## Findings

### FILE pack_validator.py

**1. medium — pack_validator.py:294 — dialogue `tone` is required by the schema and the error message but is never validated**
The AUD-03 message says "needs speaker, text, **tone** and time_range", but the guard only tests `speaker`, `text` and `time_range`. A line with no `tone` key passes.
- Failing input: `{"speaker":"S1","text":"hi","time_range":[1.0,2.0]}` (no `tone`) → no error, although `tone` is mandatory per the owner spec ("dialogue: Character line, speaker ID, tone, and time_range") and `writer_prompts` stage 3.
- Fix: add `and _nonempty_str(x.get("tone"))` to the condition at line 294.

**2. medium — pack_validator.py:224 + :257 — `_positions()` reads a `facing` key that the schema does not carry; the "eyeline" half of S55-6 cannot fail for conformant data**
`_positions` builds `(screen, facing)`, but ANCH-01 (line 257) requires `id, screen, **depth**`, and the spec/example use `screen`/`depth` (never `facing`). So for any row that passes ANCH-01, `_positions` returns `(side, None)` and the `eyeline` comparison at line 642 (`if a and b and a != b`) never fires — a check that cannot fail.
- Failing input: two consecutive conformant rows `character_positions:[{"id":"CHAR-X","screen":"left","depth":"mid"}]` → `[{"id":"CHAR-X","screen":"right","depth":"far"}]`; the screen flip is caught but the second-axis change is silently ignored.
- Fix: read the field the schema actually carries (`depth`) and compare depth values, or add `facing` to the required `character_positions` keys and compare it.

**3. medium — pack_validator.py:836 — VM-01 checks only the primary `narration`; `narration_by_lang` entries are never checked for a NARRATOR voice id**
The elevenlabs narration check inspects `track["narration"]` only. In multilingual rows the per-language narrations live in `narration_by_lang` and are never tested against `voice_map.NARRATOR.<lang>`, even though the same check runs for dialogue (including `dialogue_by_lang`) at lines 843-852.
- Failing input: multilingual row with `narration_by_lang: {"hi": {"text":"...","language":"hi","time_range":[1,2]}}` and no `voice_map.NARRATOR.hi` → no VM-01 error, while the identical omission on the primary `narration` would error.
- Fix: loop over `narration_by_lang` entries and apply the same `voice_map.NARRATOR.<lang>` presence check.

**4. medium — pack_validator.py:821 — when `voice_engine` is absent the validator skips all voice checks, but the owner default is elevenlabs**
`_check_voice` returns immediately when `engines is None`, and `_validate_story` only validates `voice_engine` when the key is present. The owner specifies elevenlabs as the default engine for all languages, so VM-01/VM-02 should still apply to a `voice_map` that the bible always carries; instead a pack with no `voice_engine` key gets no voice validation at all.
- Failing input: a pack with dialogue lines and a `voice_map` but no `voice_engine` key → a missing per-language voice id is never flagged.
- Fix: treat `engines=None` as the elevenlabs default (e.g. default to `{}` so `engine_for` returns "elevenlabs") instead of returning early.

**5. low — pack_validator.py:469 + :483 — multilingual rows are forced to have narration in every language, while single-language rows allow `narration: null`**
ML-03 requires every `*_by_lang` key present on a multilingual row, and the `narration_by_lang` loop (line 488) requires `text` + `time_range` for every language, so a multilingual shot with no narration cannot be represented. Single-language rows allow `narration: null`. Contradictory rules.
- Failing input: a 2-language story with an action shot that legitimately has no narration → `narration_by_lang: {}` or omitted triggers ML-03/ML-01.
- Fix: allow `narration_by_lang` to be absent (or accept null entries) when a shot has no narration, mirroring the single-language `narration: null`.

**6. low — pack_validator.py:843 — for the primary language, dialogue lines are checked twice (duplicate errors)**
`lines` collects both `track["dialogue"]` and `dialogue_by_lang[primary]`, which the spec says are duplicates, so an invalid primary-language line produces two identical errors.
- Fix: for the primary language, check only `dialogue_by_lang[primary]` (skip `track["dialogue"]`) when it is present.

**7. low — pack_validator.py:315 — `mouth_state` values are validated but coverage is not**
The loop checks each value is in `MOUTH_STATES` but never verifies there is one entry per second of the shot, which the spec requires ("one entry per second").
- Fix: check that `mouth_state` contains an entry for every integer second `0..floor(editorial_duration_sec)`.

**8. low — pack_validator.py:496 — the primary `narration.time_range` is not bounded by the shot duration**
ML-06 (line 493) bounds `narration_by_lang` time ranges against `editorial`, but the primary `narration` is only added to the timing-equality set (line 496) with no equivalent bounds check, so primary narration can extend past the shot.
- Fix: apply the same `rng[1] <= editorial + TIME_TOL` check to the primary `narration.time_range`.

### FILE writer_prompts.py
No findings — pure prompt text, no I/O, no model calls; the language/shape rules it emits are consistent with the validator.

=== FINAL:
1. pack_validator.py:294 — dialogue `tone` is mandatory in the spec and the error message but is never validated (missing validation at a trust boundary).
2. pack_validator.py:224/257 — `_positions()` reads `facing` while ANCH-01 requires `depth`, so the S55-6 "eyeline" flip check cannot fail for any spec-conformant row (dead check / contradictory rules).
3. pack_validator.py:836 — VM-01 never checks `narration_by_lang` entries for a `voice_map.NARRATOR` id, only the primary `narration` (missing validation).
4. pack_validator.py:821 — absent `voice_engine` skips all voice checks although the owner default is elevenlabs, so the default engine's VM-01/VM-02 never run (spec contradiction / missing validation).
5. pack_validator.py:469/483 — multilingual rows must have non-empty narration in every language while single-language rows allow `narration: null` (contradictory rules).


# BATCH b2_write_pack_lang (dots) 11-07 02:14



## Findings

### FILE write_pack.py

**[HIGH] write_pack.py:167 — the no-paid-calls gate returns True for any model with empty / non-numeric pricing**
- Why: `openrouter_is_free` ends with `return all(float(v or 0) == 0 for v in entry.get("pricing", {}).values() if isinstance(v, (str, int, float)))`. When `pricing` is missing, `{}`, or holds only non-numeric values, the generator is empty and `all([])` is `True`, so the model is treated as free and sent. This is the exact gate meant to enforce "no paid calls".
- Failing input: an OpenRouter entry `{"id": "some/paid-model", "pricing": {}}` (or `{"pricing": {"prompt": null}}`) → `openrouter_is_free` returns True → `call_openrouter` sends the call → a paid call is made.
- One-line fix: `prices = [v for v in (entry.get("pricing") or {}).values() if isinstance(v, (str, int, float))]; return bool(prices) and all(float(v or 0) == 0 for v in prices)` (align with `retry_policy.is_free_model`).

**[MEDIUM] write_pack.py:116 — `call_claude` returns raw CLI stdout instead of wrapping it in `envelope()`**
- Why: `call_nvidia` (152) and `call_openrouter` (187) both return `envelope(...)`, and the docstring at 99-102 says "Every path returns the same JSON shape". `call_claude` returns `r.stdout` (the Claude CLI's own JSON), which carries no `via`/`model`/`finish_reason`. Consequences: the run registry records `via=None, model=None` for every Claude/opus stage, `envelope_info(text).get("chars")` is None, and the `finish_reason != "stop"` cut-off detection does not apply to Claude answers (a truncated answer with `is_error: false` is treated as success).
- Failing input: `python write_pack.py story.md out --writer opus`; inspect `out/stage_*_raw.json` → no `via`/`model` keys; a truncated opus answer passes `answer_text`.
- One-line fix: `data = json.loads(r.stdout); return envelope(data.get("result") or "", "error" if data.get("is_error") else "stop", "claude", model)`.

**[MEDIUM] write_pack.py:258 + 480 — `json.JSONDecodeError` escapes the `except ValueError` handler and crashes the run**
- Why: `answer_text` does `json.loads(raw)` (258) and can raise `json.JSONDecodeError`. `run_stage.judge` (478-487) wraps `parse_fn(raw)` in `try/except ValueError`, so a `JSONDecodeError` is not caught; `run_single` calls `parse(...)` at 907 with no try at all. A corrupt/truncated raw file (process killed mid-write, or a reused folder) therefore crashes with an unhandled traceback instead of a clean stage failure.
- Failing input: a `raw_response.json` truncated mid-JSON, then `python write_pack.py story.md pack/` (reuse path) → `JSONDecodeError` propagates to `main`, which only catches `StageFailed`.
- One-line fix: in `answer_text`, `except json.JSONDecodeError as exc: raise ValueError(f"raw answer is not valid JSON: {exc}") from exc`.

**[MEDIUM] write_pack.py:119-186 — model calls never use `retry_policy`; HTTP 429/5xx/network faults crash the whole run**
- Why: `stream_chat` raises `urllib.error.HTTPError` on 429/5xx; `call_openrouter` (181) converts it to `RuntimeError`, `call_nvidia` (153) raises `RuntimeError` after all keys fail, and `URLError`/`TimeoutError` propagate unconverted. `main` (970-973) only catches `StageFailed`, so a rate limit or server error aborts the pipeline with a traceback. `retry_policy.py` (`call_with_retry`/`call_chain`) exists precisely for these free-model calls but is never imported.
- Failing input: NVIDIA returns HTTP 429 during stage 3e1 → `RuntimeError` → unhandled exit 1, no retry, no fallback to the next model.
- One-line fix: route `stream_chat` through `call_with_retry` (or `call_chain` over `FREE_CHAIN`) so 429/5xx/timeout/network faults retry with backoff and switch models instead of crashing.

**[MEDIUM] write_pack.py:574 + simple_language.py:432 — English is skipped by the writer's easy-language checks although the owner wants easy language in en/hi/mr**
- Why: `text_language_errors` returns `[]` immediately when `lang == "en"` (574), and `simple_hook` returns `None` for English (432), so neither the writer's own fallback checks nor the hook passed to the validator ever run the English tier (`STIFF-01`/`SEN-01`/`SCRIPT-01` in `simple_language.check_text`) on narration/dialogue/captions.
- Failing input: `--out-lang en` (or `en` in an `all` story) with narration `"Utilize the lever to leverage systemic leverage."` → no `STIFF-01`/`SEN-01` flag is produced; the owner's easy-language rule is unenforced for English.
- One-line fix: remove the `lang == "en"` short-circuit in `text_language_errors` and have `simple_hook` run `check_text(text, "en")` for English (the module already supports it).

**[LOW] write_pack.py:111 — `shutil.which("claude") or "claude"` is a dead fallback that raises an unhandled `FileNotFoundError`**
- Why: if `claude` is not on PATH, `which` returns `None`, the `or "claude"` yields `"claude"`, and `subprocess.run(["claude", ...])` raises `FileNotFoundError`, which is not caught anywhere up the stack.
- Failing input: `--writer opus` on a machine without the Claude CLI installed → `FileNotFoundError` traceback.
- One-line fix: `bin = shutil.which("claude"); if not bin: raise RuntimeError("claude CLI not found on PATH")`.

**[LOW] write_pack.py:167 vs retry_policy.py:205 — the two free-model checks disagree on empty pricing**
- Why: `retry_policy.is_free_model` requires `bool(prices)` (empty/unpriced ⇒ not free ⇒ refused), while `write_pack.openrouter_is_free` treats empty pricing as free (see HIGH finding). If the modules are ever integrated, the same model would be refused by one and sent by the other.
- Failing input: model with `pricing: {}` → `is_free_model` returns False, `openrouter_is_free` returns True.
- One-line fix: make `openrouter_is_free` require non-empty pricing (same one-line change as the HIGH finding).

**[LOW] write_pack.py:226 — `json_lines` crashes on a line that is only punctuation**
- Why: `json.loads(line.strip().rstrip(","))` — a line like `","` becomes `""` after `rstrip(",")`, and `json.loads("")` raises `JSONDecodeError`. This runs in the fallback path of `shots_from`/`bible_from` (only when the whole block is not valid JSON).
- Failing input: a `json shots` block written as JSON-lines containing a stray `,` line → `JSONDecodeError` crashes the parse fallback.
- One-line fix: `for line in block.splitlines(): s = line.strip().rstrip(","); if s: values.append(json.loads(s))`.

---

### FILE simple_language.py

**[MEDIUM] simple_language.py:432 — `simple_hook` returns `None` for English (see write_pack.py:574 above)**
- Same finding as the write_pack.py:574 entry; the hook that the validator calls is a no-op for `lang == "en"`, so English text is never checked through the validator path either.

---

### FILE retry_policy.py

**[LOW] retry_policy.py:205 — `is_free_model` requires non-empty pricing (contrasts with write_pack.py:167)**
- Same cross-module inconsistency as the write_pack.py:167 vs retry_policy.py:205 entry above; no independent defect in `retry_policy.py` itself.

---

## FINAL:

1. **[HIGH] write_pack.py:167** — `openrouter_is_free` returns `True` for models with empty/missing/non-numeric pricing (`all([])` is vacuously true), so the "no paid calls" gate can send a paid model. Fix: require non-empty numeric pricing and all-zero, matching `retry_policy.is_free_model`.
2. **[MEDIUM] write_pack.py:116** — `call_claude` returns raw CLI stdout instead of `envelope(...)`, breaking the documented "same JSON shape" contract; the run registry loses `via`/`model` for Claude stages and cut-off detection is bypassed for Claude. Fix: parse the CLI JSON and return `envelope(text, finish, "claude", model)`.
3. **[MEDIUM] write_pack.py:258/480** — `answer_text`'s `json.loads` can raise `json.JSONDecodeError`, which is not caught by `except ValueError` in `run_stage.judge` (nor anywhere in `run_single`); a corrupt/truncated raw file crashes the run unhandled. Fix: catch `JSONDecodeError` in `answer_text` and re-raise as `ValueError`.
4. **[MEDIUM] write_pack.py:119-186** — free-model calls never apply `retry_policy`; HTTP 429/5xx/network errors become unhandled `RuntimeError`/`URLError` that abort the whole pipeline, even though `retry_policy.call_with_retry`/`call_chain` exist for exactly this. Fix: wrap `stream_chat` in `call_with_retry`/`call_chain`.
5. **[MEDIUM] write_pack.py:574 + simple_language.py:432** — the writer's easy-language checks (and the hook passed to the validator) skip English entirely, contradicting the owner's "easy language in en/hi/mr"; `simple_language.check_text` supports English but is never invoked for it. Fix: run the English tier in `text_language_errors` and `simple_hook`.


# BATCH b3_state_ops (dots) 11-07 02:27



## Findings

### FILE run_registry.py

**[medium] run_registry.py:271-299 (update_story) and story_links.py:89-96 (link) — read-modify-write on story.json / links.json is not locked**
`update_story` reads story.json (line 278), mutates, then `_write_atomic` (line 298); `story_links.link` reads links.json (line 89) and appends (line 96). Only RUNS.jsonl appends are locked (`append_event` line 395). Two concurrent writers (e.g. `record_story_saved` and `record_transcript` both calling `update_story`) each read the same old version and each writes — one writer's change is silently lost.
- Failing input: process A runs `record_story_saved` (sets language="en"), process B runs `record_transcript` (sets source={...}) at the same instant; the second writer overwrites story.json with a version missing the other's field.
- Fix: wrap the read-modify-write in `update_story` and `story_links.link` with `_locked(story_dir / "story.json.lock")` / `_locked(story_dir / "links.json.lock")`.

**[medium] run_registry.py:89-95 (run_id) called at 536, 557, 571, 580 — run_id is generated from a stale `taken` set before the append lock is acquired**
`_run_ids(self.dir)` is read, then `run_id(...)` picks a free id, then later `append_event` acquires the lock and appends. Between the read and the lock another process can append the same id. Two writers on one story in the same minute both emit e.g. `20261107-1200-writer-super-vl`; RUNS.jsonl then holds two events with one run_id and `runs()` merges distinct runs into a single corrupted row.
- Failing input: two writers start on the same story at 12:00:00; both read `taken={}`, both generate `20261107-1200-writer-super-vl`, both append; the reader sees one run mixing both writers' steps.
- Fix: re-read `_run_ids` and regenerate (or verify uniqueness) inside the lock that `append_event` holds before writing.

**[low] run_registry.py:255-256 — detect_language cannot detect Marathi**
The regex `[\u0900-\u097F]` is the Devanagari block, shared by Hindi **and** Marathi, so any Marathi text with ≥20 Devanagari chars is labelled `"hi"`. The owner lists `en/hi/mr` as the output languages, so a Marathi source is mis-filed as Hindi at save time.
- Failing input: SOURCE.md containing Marathi text (e.g. "यह एक परीक्षण टिप्पणी है ...") → `detect_language` returns `"hi"`, never `"mr"`.
- Fix: add a Marathi signal (e.g. U+093D ऽ or ऎ/ऎ) and return `"mr"` when present, else keep the Hindi test.

**[low] run_registry.py:320-333 — read_events trusts RUNS.jsonl without validating it**
Every line is `json.loads`-ed and appended; `_checked` (field/kind/status/regex validation) is never called on read. A hand-edited or corrupted line (e.g. `"chars": -5`, `"status": "bogus"`, `"stage": "999"`) flows silently into `steps`/`runs`/`summary`/the report.
- Failing input: RUNS.jsonl contains `{"run_id":"x","kind":"analysis_done","status":"ok","stage":"999","chars":-5}` → `summary` renders it; `run_status` treats the unknown status as `"ok"`.
- Fix: run each parsed event through `_checked` in `read_events`, skipping (and warning on) invalid lines.

**[unverified] run_registry.py:416-424 — run_status judges a writer run by its analysis_done row only**
`statuses = {r.get("status") for r in (done or rows)}` uses only `analysis_done` rows when any exist, so a failed `analysis_stage` step is invisible if the analysis_done row says `"ok"`. The docstring states this is intended ("a writer run is what its analysis_done step says"), but that only holds if analysis_done genuinely aggregates stage results — which is not enforced anywhere in this module.
- Failing input (if the writer does not propagate stage failures): events = [analysis_stage failed, analysis_done ok] → `run_status` returns `"ok"`.
- Fix (if the aggregation assumption is wrong): include all rows' statuses for writer runs too, or have the writer record analysis_done with the aggregate status.

### FILE story_links.py

**[medium] story_links.py:89-96 — links.json read-modify-write is unlocked** (same class as run_registry.py:271-299)
`data = read(studio, slug)` then `data["links"].append(...)` then `rr._write_atomic(...)` with no lock; concurrent `link()` calls on one story lose entries.
- Failing input: two calls to `link()` for the same slug at the same moment → one link entry is overwritten/lost.
- Fix: guard with `_locked(story_dir / "links.json.lock")`.

### FILE secret_scan.py

**[medium] secret_scan.py:150-153 — committed blobs are read fully into memory with no size cap**
`data = run(["cat-file", "blob", f"HEAD:{rel}"], root)` (with `capture_output=True`) loads the entire blob, then `scan` → `content_findings` decodes it all. The worktree path (lines 158-162) caps at `MAX_BYTES`, but committed files have no cap, so a large committed file OOMs the scanner even though `path_findings` would flag it `P-SIZE`.
- Failing input: a 300 MB text file is committed → `gather` buffers 300 MB in `capture_output`, then `content_findings` builds a 300 MB str + line list → MemoryError / OOM kill; the intended "block big files" behaviour never completes.
- Fix: for committed files, only keep content when `len(data) <= MAX_BYTES`, else store `b""` (consistent with the worktree branch).

**[low] secret_scan.py:54-71 and 99-117 — path-based findings (P-*) can never be allowlisted**
The allowlist match is `p == rel and r == rule and lit in text`, where `text` is a line of content. Path findings (`P-STORIES`, `P-MEDIA`, `P-SIZE`, …) have no line text, so no allowlist entry can ever match them; the `STORY_EXEMPT` hard-code is the only escape.
- Failing input: an allowlist line `stories/foo/PACK.md | P-STORIES | anything` is ignored; the file is still blocked.
- Fix: allow path rules to match on `(rel, rule)` alone (skip the literal check for `P-*` rules).

### FILE story_state.py

**[unverified] story_state.py:69 — `failed |= validation` treats the mere existence of a `stage_N_validation.json` as a failure**
The validation file's content is never read (`envelope_file` is only called on raw files); any stage that has a validation file is pushed into `failed_stages` and reported as "failed its checks". This is correct only if validation files are written exclusively on failure; if the validator writes a result file on pass too, every validated stage is falsely reported as failed.
- Failing input (if validators always write a result): a pack whose stage 2 passed validation has `stage_2_validation.json` present → `_pack_info` reports stage 2 as failed.
- Fix (if the assumption is wrong): read the validation file's envelope and mark the stage failed only when it reports an error.

---

FINAL:
1. **run_registry.py:271-299 + story_links.py:89-96 — unlocked read-modify-write on story.json / links.json loses concurrent writers' changes** (medium)
2. **secret_scan.py:150-153 — committed blobs are read fully into memory; a large committed file OOMs the scanner** (medium)
3. **run_registry.py:89-95 (callers 536/557/571/580) — run_id is picked from a stale `taken` set before the append lock, so duplicate run_ids merge distinct runs** (medium)
4. **run_registry.py:255-256 — detect_language cannot detect Marathi (Devanagari text is labelled "hi")** (low)
5. **run_registry.py:320-333 — read_events passes unvalidated RUNS.jsonl lines into steps/runs/reports** (low)


# BATCH b4_h3_linter (dots) 11-07 02:49



=== FILE schema_and_linter.py ===
- severity: medium, line: 108 (used at 830), what is wrong: SFX_CUE_RE = re.compile(r"\b(?:sound|hiss|rustle|splash|wind|water|step|breath|hum|whoosh|roar|crack|thud|drip|flow|ring|voice|pop|click|tick|knock|snap|slam|scrape|tap|clink|creak|crunch|rain|spray|swish|thump|buzz|chime|bell)\w*", re.I) matches non-sound words like "window" (because \w* consumes "ow"), so a stage sentence "The window is open" would incorrectly count as having a sound cue, allowing a shot to pass SX-01 without a real sound effect. concrete failing input: a shot with motion_7_stage["2_anticipation"] = "The window is open" would have cues=7 and pass the check. one-line fix: change the regex to require a word boundary after optional inflections, e.g., r"\b(?:sound|hiss|...)(?:s|ing|ed|y|ish)?\b".
- severity: medium, line: 815-817, what is wrong: _check_workflow only validates width, height, and length of node 5; it does not check expected_latent_slots, ref_image_size, or reference_images, so a workflow with incorrect values would pass the linter. concrete failing input: a workflow with node 5 inputs expected_latent_slots=999 (while the shot has latent_slots=32) would not be caught. one-line fix: add checks comparing cond["expected_latent_slots"] to t["latent_slots"], cond["ref_image_size"] to prof["ref_image_size_policy"], and cond["reference_images"] to ref_inventory(shot)["images"].
- severity: low, line: 800 (and 803, 808, 811, 815), what is wrong: when a required node is missing, nodes["2"]["inputs"] raises KeyError which is caught by _run and reported as SC-03 instead of the appropriate WF-01/WF-02 error. concrete failing input: a workflow missing node "2" will produce an SC-03 error instead of WF-01. one-line fix: check node existence with .get() before accessing inputs and emit the correct WF error.
- severity: low, line: 606, what is wrong: list(k.get("dimensions_verified", [])) raises TypeError if dimensions_verified is not a list (e.g., an integer), which is caught as SC-03. concrete failing input: "dimensions_verified": 1440 in a shot's fl2va_keyframes. one-line fix: validate that dimensions_verified is a list before comparing.
- severity: medium, line: 836-857 (see also 848-849), what is wrong: the code does not validate that every character id in reference_audio has an entry in voice_speaker_map; a shot could list an audio ref for an unknown speaker, leading to an invalid prompt. concrete failing input: a shot with reference_audio: ["char_x"] where "char_x" is not a key in registry.voice_speaker_map. one-line fix: add a check that all audio refs correspond to speakers in voice_speaker_map.

=== FILE compile_h3_sing8.py ===
- severity: high, line: 131 (and 147-148), what is wrong: compile_comfyui_workflow always sets first_frame and last_frame from the resolved keyframes; for Ref2VA shots the linter allows missing boundary frames when reference_images are present (KF-06), but the workflow will contain "first_frame": null, "last_frame": null, which is invalid. concrete failing input: a Ref2VA shot with reference_images set and no picture_1_path/picture_2_path passes lint_shot but compile_comfyui_workflow produces an invalid workflow. one-line fix: make first_frame/last_frame optional for Ref2VA (e.g., only include them when the paths exist) or use a different conditioning node that does not require boundary frames.

=== FILE router.py ===
no findings

=== FILE shot_table_spec.py ===
no findings

FINAL:
1. high, compile_h3_sing8.py:131 – Ref2VA workflow requires boundary frames even when they are missing, producing an invalid ComfyUI payload for shots the linter allows.
2. medium, schema_and_linter.py:108 – SFX_CUE_RE matches non-sound words (e.g., “window”), so the SX-01 check can be satisfied without a real sound cue.
3. medium, schema_and_linter.py:815 – Missing validation of node 5 inputs (expected_latent_slots, ref_image_size, reference_images) in _check_workflow.
4. medium, schema_and_linter.py:836 – Missing validation that reference_audio entries correspond to speakers in voice_speaker_map.
5. low, schema_and_linter.py:800 – KeyError from missing nodes is caught and reported as SC-03 instead of the correct WF-* code, masking workflow errors.


# BATCH b5_gate_d (dots) 11-07 03:00



## Findings

### FILE gate_d_audio.py

**HIGH** — gate_d_audio.py:616 (also :637, :838)
The `*_by_lang` fields (`narration_by_lang`, `dialogue_by_lang`, `captions_by_lang`) are assumed to be dicts. A non-empty string or list value makes `(x or {}).get(lang)` / `(x or {}).items()` raise `AttributeError`. The per-language handler at line 816 catches only `ValueError, KeyError, TypeError`, and `same_timing_problems` at line 804 catches only `ValueError`, so one malformed shot row aborts `plan_language_outputs` for **every** language.
- Failing input: `{"audio_and_dialogue_track": {"narration_by_lang": "hello text"}}`
- Fix: guard with `isinstance(x, dict)` (or catch `AttributeError` alongside the others at lines 805 and 816).

**MEDIUM** — gate_d_audio.py:539 vs :711-732
`write_captions` is never called. `_plan_one_language` invokes `build_ass` (line 713) only to harvest warnings and discards the returned `.ass` text; the plan's `mux_argv` (line 762-764) references `caption_path = captions_dir/{reel}_{lang}.ass`, but nothing writes that file and the plan does not carry `lang`/`fonts_dir`/`face_boxes`, so there is no way to produce it from the plan. With `burn_captions=True` the mux step points at a missing file.
- Failing input: any language with `burn_captions=True` and non-empty cues.
- Fix: call `write_captions(plan["caption_path"], cues, face_boxes, fonts_dir, lang)` inside `_plan_one_language` (or store the written path).

**MEDIUM** — gate_d_audio.py:183-188 (only the closing shot)
`narrator_mouth_closed` + the per-second `mouth_state` map is validated only inside `check_closing_shot`. The spec requires "narrator_mouth_closed: True at the shot level plus per-second mouth_state logging" on every shot with narration (opening hook, all narration shots). A reel where shot 2 has narration and `performance_notes.narrator_mouth_closed: false` passes with no error.
- Failing input: 3-shot reel, shot 2 narration present, `performance_notes: {"narrator_mouth_closed": false}`.
- Fix: add a `check_mouth_state(track)` helper and call it in `check_opening_hook` / `check_narration_density` (or per shot in `_plan_one_language`).

**LOW** — gate_d_audio.py:171-172 combined with :184-188
For the `h3` English path `vo_files` is empty, so `check_closing_shot` returns early at line 172 (`vo_wav_path is None`) and the mouth-closed, VO-fit and tail-silence checks are skipped entirely. An h3 closing shot with `narrator_mouth_closed: false` or an in-render speech that overflows the editorial passes undetected.
- Failing input: `voice_engine={"en":"h3"}`, closing shot with `performance_notes: {"narrator_mouth_closed": false, "mouth_state": {"3": "open"}}`.
- Fix: run the mouth/performance checks for h3 too (the `vo_wav_path` guard should only skip the wav-fit/tail-silence part).

**LOW** — gate_d_audio.py:84-86 (unverified, spec conflict)
The owner decision summary says captions use "bottom margin 896, top 360, sides 160" while the merged master prompt says "MarginV = 467 … no content above y = 360". The code reads all of these from `CAPTION` in `shot_table_spec`, which is not visible here, so the actual values cannot be confirmed against either number.

**LOW** — gate_d_audio.py:529-535
`_ass_word` strips only `{`, `}`, `\`. A caption word containing a literal backslash (e.g. an asset path) silently loses characters. (Commas in the text field are OK because libass counts fields from the Format line.)

### FILE voice_engine.py

No concrete defects found. `engine_for`, `resolve_engines`, `voice_engine_problems`, `voice_map_problems`, `anchor_problems`, `speaker_map_problems`, `audio_ref_problems` all match the owner decisions (en/hi/mr default elevenlabs, h3 off-by-default for en only, h3 forbidden for hi/mr). The VE-04 warning is emitted correctly.

### FILE voice_manifest.py

**MEDIUM** — voice_manifest.py:85-86 together with gate_d_audio.py:217
`build_manifest` builds `fit_items` with `editorial_duration_sec` taken straight from `shot.get(...)` (line 62), which can be `None` or a non-numeric value. `vo_fit_check` then does `float(it["editorial_duration_sec"])` (gate_d_audio.py:217) → `TypeError`, uncaught, crashing the `voice_manifest` CLI. `same_timing_problems` validates this field but `build_manifest` never calls it.
- Failing input: `--shots` JSON containing a shot row without `editorial_duration_sec`.
- Fix: validate `editorial_duration_sec` in `build_entry` (or skip/flag the entry) before appending to `fit_items`.

**LOW** — voice_manifest.py:69
`except Exception:` around `wav_duration_sec` is a bare catch that can mask non-wav corruption as a silent `duration_sec: None`. Acceptable given the comment, but it also swallows programming errors.

**LOW** — voice_manifest.py:119,124
The CLI opens `args.shots` / `args.voice_map` without handling `FileNotFoundError`, producing a raw traceback instead of a clean error.

### Unverified (out of scope / not visible)
- "Sound cue required in all 7 action sentences (SX-01)": no `SX-01` check exists in these files; it likely lives in `pack_validator.py` / the shot-table gate. Not confirmed present or absent.
- "Easy language in en/hi/mr" simple-language validator: not present in these files.
- The caption geometry numbers (896 vs 467) and `CAPTION["margin_l"/"margin_r"/"margin_v"/"top_blocked_y"]` values cannot be checked without `shot_table_spec`.

---

FINAL:
1. HIGH — gate_d_audio.py:616 — malformed `*_by_lang` (string/list instead of dict) raises `AttributeError`; the per-language


# BATCH b6_controller (dots) 11-07 03:05



After reviewing the five files against the owner's spec and decisions, here are the concrete defects.

---

### FILE: render_controller.py

**1. severity: medium — `_qc_result` QC runs against the full episode shot list, not the selected shots**
- **line 522:** `final_qc(g["episode"]["shots"], measurers=measurers)` uses `g["episode"]["shots"]` (the full episode) instead of `g["shots"]` (the shots actually in scope).
- **Why:** For `--scope shots A,B` on an episode with shots A,B,C,D, QC checks C and D (which are not in the reel), computes reel-time offsets from the start of the episode instead of the first selected shot, and the closing-payoff check inspects shot D (the episode's last shot) rather than shot B (the reel's last shot). This produces wrong pass/fail results and can block or falsely pass a reel.
- **Failing input:** story with episode EP_01 having shots [S1,S2,S3,S4]; run with `--scope shots S1,S2`. QC evaluates all four shots, reports closing payoff on S4, and offsets assume a full-episode timeline.
- **One-line fix:** Change `g["episode"]["shots"]` to `g["shots"]` on line 522.

**2. severity: medium — `_gate_d_result` plans audio for the full episode, not the selected shots**
- **line 541:** `shots=ep["shots"]` passes the full episode shot list to `plan_language_outputs`, while every other step in `plan_pipeline` correctly uses `g["shots"]`.
- **Why:** For `--scope shots A,B`, Gate D plans voice/SFX/captions for shots C and D as well, producing an audio plan that references shots not in the reel. The resulting export/reel will have audio for missing clips or wrong timing.
- **Failing input:** same story/scope as above; Gate D generates VO and caption schedules for S3 and S4 which are never assembled.
- **One-line fix:** Change `shots=ep["shots"]` to `shots=g["shots"]` on line 541 (and use `g["episode"]["episode_id"]` / `g["episode"]` for the other references already in that block).

**3. severity: low — `_current_hashes` calls `resolve_keyframes` without exception handling, unlike `_picture_rows`**
- **line 481:** `kf = resolve_keyframes(shot, shots[k - 1] if k else None, root)` has no `try/except`, while `_picture_rows` at lines 209–212 wraps the same call in `try/except (KeyError, TypeError, AttributeError): kf = None`.
- **Why:** If a shot row that passed the linter still makes `resolve_keyframes` raise (e.g. a malformed keyframe reference the linter did not catch), `_current_hashes` crashes, taking down `_manifest_result` and the whole `plan_pipeline` dry-run. `_picture_rows` already demonstrated the same call site can raise and is defended.
- **Failing input:** a shot with `picture_1` pointing to a path that `resolve_keyframes` cannot parse (the linter may not validate the internal structure `resolve_keyframes` expects).
- **One-line fix:** Wrap the `resolve_keyframes` call at line 481 in the same `try/except (KeyError, TypeError, AttributeError): kf = None` pattern used at line 209.

**4. severity: low — `_render_result` details count includes failed renders**
- **line 515:** `"rendered": len(render_results)` counts every entry in the `render_results` dict, including shots whose value is `"failed"`, but the field is named `"rendered"`.
- **Why:** The details block misrepresents how many shots actually rendered successfully; a consumer reading `details.rendered` gets an inflated number.
- **Failing input:** `render_results = {"S1": "ok", "S2": "failed"}` → `details.rendered = 2` although only one shot rendered.
- **One-line fix:** Change to `"rendered": sum(1 for v in render_results.values() if v == "ok")`.

**5. severity: low — `plan_pipeline` default-language fallback treats an explicit empty list as "not set"**
- **line 560:** `list(languages or story.get("output_languages") or story["registry"].get("output_languages") or ["hi"])` — an empty list `[]` is falsy, so `languages=[]` silently falls back to the story/registry value or `"hi"`.
- **Why:** A caller who explicitly passes `languages=[]` (meaning "no language reels") gets a `"hi"` reel instead. The `or` chain cannot distinguish "not provided" from "provided but empty".
- **Failing input:** `plan_pipeline(story, groups, out, languages=[])` → `langs` becomes `["hi"]` instead of `[]`.
- **One-line fix:** Use `languages if languages is not None else (story.get(...) or story["registry"].get(...) or ["hi"])`.

---

### FILE: pipeline_contract.py

No findings. The step ordering, PRE_ASSEMBLY/POST_ASSEMBLY split, assembly gating logic, and `build_plan`/`assembly_allowed` are consistent and crash-free.

---

### FILE: fallback_policy.py

No **verified** findings. Two potential issues are **unverified** without the shot-table schema (`shot_table_spec.py`):
- Line 81: `max(n for n in range(6, 21) if lattice(n)["seconds"] <= SHORT_MAX_SEC)` could raise `ValueError` on an empty sequence if `lattice(6)["seconds"] > 6.0`.
- Lines 122–124: `float(narr["time_range"][0])` assumes `time_range` is a list of numbers; if the schema allows a string like `"0.0-2.0s"` this would misparse or crash.

---

### FILE: asset_manifest.py

No findings. Hashing, manifest validation, `blocking_problems`, `render_plan`, and atomic I/O are correct and contain no logic errors, unsafe paths, or spec violations.

---

### FILE: step9_qc.py

No findings. The four checks, fail-closed measurer handling, offset computation, and label-pattern matching are correct. The `cues == 0` rejection aligns with the pure-Foley sound-cue requirement; per-sentence SX-01 enforcement is a linter responsibility, not a QC one.

---

FINAL:
1. render_controller.py:522 — `_qc_result` uses full episode shots instead of selected shots (medium)
2. render_controller.py:541 — `_gate_d_result` uses full episode shots instead of selected shots (medium)
3. render_controller.py:481 — `_current_hashes` lacks exception handling for `resolve_keyframes` (low)
4. render_controller.py:515 — `_render_result` "rendered" count includes failed renders (low)
5. render_controller.py:560 — `plan_pipeline` empty-list language fallback is silently overridden (low)
