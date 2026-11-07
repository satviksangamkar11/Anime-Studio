

# BATCH r4c_director (dots) 11-07 09:51



After reviewing the two files I can see (`write_pack.py` and `pack_validator.py`) against the round-2 fix list, I find no real defects in either. The remaining files mentioned in the fix list (ui/static/app.js, pipeline.js, server.py, pipeline.py, h3/router.py, schema_and_linter.py, compile_h3_sing8.py, h3_author, v4_to_h3, voice_manifest, gate_d_audio, render_controller, voice_engine, run_registry, retry_policy) are not present in this review context, so their fixes are **unverified**.

In `write_pack.py`: the resume guard (raw+val both present → StageFailed), the single-flight `run_stage` retry loop, `episodes_from` mixed-type handling (bool exclusion via `not isinstance(e.get("episode"), bool)`, dict/int/other branching, `int(n)` fallback), `merge_episodes` renumbering with `source_id` preservation, `canonical_bible` ordering, `legacy_fields` derivation, `apply_captions` single/multi-language paths, `refuse_finished` before any model call, `checked_call` wrapping non-ValueError into StageFailed, and the `gate`/`with_language` merge logic for stage 5 are all correct and consistent.

In `pack_validator.py`: the `STORY-04` output_languages/output_language check, `BIBLE-01..08` canonical layout and style-lock rules, `ROW-01..04` column completeness, `ANCH-01/02`, `AUD-01..05` audio track rules, `ML-01..08` multilingual checks (including bool exclusion from int checks via `not isinstance(..., bool)`), `S55-1..6` Step 5.5 self-checks, `VM-01/02` and `VA-01/02` voice rules, `_story_file`/`_peek_output_languages`/`_peek_voice_engines` file discovery, and the legacy vs V4 dispatch in `validate_pack` are all correct.

No regressions, spec violations, crash-on-bad-input paths, or JS/server contract mismatches were found in the visible code.

FINAL:
No real defects found in the visible files. The remaining round-2 fixes (UI, server, pipeline, router, schema/linter, compile, and several h3/* modules) are unverified because those files were not provided for review.


# BATCH r4c_h3 (dots) 11-07 09:55



## Round 3 Review Findings

After checking each round-2 fix against the files provided, here are the concrete defects found.

---

### 1. `same_timing_problems` false positive when a language has no time ranges
**Severity:** medium
**File:** `gate_d_audio.py:873-875`

When a shot has `narration_by_lang` (or `dialogue_by_lang`/`captions_by_lang`) where one language has a valid `time_range` and another language has no `time_range` at all (or no entry), `per_lang` for the missing language is an empty list. The comparison `len({tuple(v) for v in keys.values()}) > 1` then reports a false `TIME-01` error, because `()` differs from `((s,e),)`. The real issue (missing `time_range`) should be reported by the schema linter as `SC-02`, not by the timing comparison.

**Failing input:** A shot with `narration_by_lang = {"hi": {"text": "hello", "time_range": "0.5-1.5s"}, "en": {"text": "hello"}}` (missing `time_range` for `en`).

**One-line fix:** Skip languages with no ranges in the comparison: only include langs where `per_lang[lang]` is non-empty.

---

### 2. `lint_story` running total treats bool `editorial_frames` as 1
**Severity:** low
**File:** `schema_and_linter.py:983-985`

`isinstance(ed, int)` is `True` for `bool` values. If a shot has `editorial_frames: true`, `running += True` adds 1 instead of 0, corrupting the episode total and potentially causing a spurious `TM-05` mismatch. The shot already gets a `TM-02` error from `_check_timing` (which uses `_is_count` that excludes bools), so this is a secondary corruption.

**Failing input:** A shot with `"timing_and_lattice": {"editorial_frames": true, ...}`.

**One-line fix:** Use `_is_count(ed)` instead of `isinstance(ed, int)`.

---

### 3. `_check_pure_foley` crashes on non-dict `voice_anchor`
**Severity:** low
**File:** `schema_and_linter.py:883-887, 894-895`

`(chars.get(cid) or {}).get("voice_anchor")` returns the raw value if it is truthy. If `voice_anchor` is a non-dict (e.g., a string), then `a.get("audio")` raises `AttributeError`. This is caught by `_run` and reported as `SC-03`, which is misleading — the real problem is a malformed `voice_anchor` block.

**Failing input:** A character with `"voice_anchor": "some_string"` instead of an object.

**One-line fix:** Add `isinstance(a, dict)` guard before calling `.get()` on `a`.

---

### 4. `_lang_track` crashes on non-dict `narration_by_lang`
**Severity:** low
**File:** `gate_d_audio.py:620-621`

`(trk.get("narration_by_lang") or {}).get(lang)` — if `narration_by_lang` is a non-dict truthy value (e.g., a string or list), the `or {}` does not trigger, and `.get(lang)` raises `AttributeError`. This propagates to the outer `except` in `plan_language_outputs` and is reported as `PLAN-01` with a confusing message. The schema linter catches this as `SC-02` for the `narration` field but not for `narration_by_lang`.

**Failing input:** A track with `"narration_by_lang": "not_a_dict"`.

**One-line fix:** Add `isinstance` checks: `nbl = trk.get("narration_by_lang"); if isinstance(nbl, dict): ...`

---

### 5. `check_opening_hook` / `_speech_items` uncaught exceptions
**Severity:** low
**File:** `gate_d_audio.py:108-119, 90-103`

`check_opening_hook` calls `_speech_items(trk)` and `parse_time_range(c["time_range"])` without try-except. A malformed `narration` (non-dict), bad `time_range` string, or non-dict items in `dialogue` list will raise `ValueError`/`AttributeError` that propagates to `_plan_one_language`'s outer `except` and is reported as a generic `PLAN-01` instead of a specific rule code.

**Failing input:** An opening shot with `"audio_and_dialogue_track": {"narration": "not_a_dict"}`.

**One-line fix:** Wrap the body of `check_opening_hook` in try-except that converts exceptions to `OPENING_HOOK_NO_VOICE` / `OPENING_HOOK_NO_SFX` errors, or validate inside `_speech_items`.

---

### 6. `parse_loudness_text` crashes on non-string `measured_text[lang]`
**Severity:** low
**File:** `gate_d_audio.py:380-389, 772-775`

If `measured_text[lang]` is not a string (e.g., a number or dict), `p.findall(text)` raises `AttributeError`. This is caught by the outer `except` in `plan_language_outputs` and reported as `PLAN-01`, which is confusing. The function should handle non-string input gracefully.

**Failing input:** `measured_text = {"hi": 123}`.

**One-line fix:** Return `{"integrated_lufs": None, "true_peak_dbtp": None}` when `text` is not a string.

---

FINAL: 6 findings (0 high, 1 medium, 5 low)

The most important is **#1** (`same_timing_problems` false positive), because it can block valid multi-language stories at Gate D with a misleading `TIME-01` error that sends the author down the wrong path. The remaining five are defensive-coding gaps at trust boundaries that produce confusing error messages rather than crashes, and should be hardened but are not blocking.


# BATCH r4c_ui (dots) 11-07 10:03



## Findings

After reviewing the round-2 fixes in `pipeline.py` and `server.py` (the only two files provided), all five verifiable fixes are correct and introduce no regressions:

- **X-UI header** (`server.py:1808`): POST guard checks `X-UI: 1` correctly.
- **record_spend after start** (`server.py:1257-1259`): spend is recorded only after `_start()` succeeds; Popen failure leaves the preview token unused.
- **Episode sort on mixed types** (`pipeline.py:703-706`, `server.py:748-750`): both lambdas correctly partition numbers before strings/None, and handle bools separately.
- **Shot seconds zero/negative → 0** (`pipeline.py:96-103`): `shot_seconds` returns `max(0.0, float(v))` with bool guard; redundant `max(sec, 0.0)` at line 695 is harmless.
- **Gate scoping by story+pack** (`pipeline.py:611-615`, `record_gate` at 214-215, `scoped_approvals` at 193-197): all correct; legacy records without story/pack never match.

One real defect found:

---

### LOW — `server.py:737`

**What's wrong:** `read_pack` builds the row `seconds` field with a type guard that returns the *raw value* (bool, None, string) when `editorial_duration_sec`/`seconds` is not a plain int/float. This is inconsistent with `pipeline.py`'s `shot_seconds` (which returns `0.0` for non-numeric input) and can leak non-numeric values into the UI's `shots` array.

**Concrete failing input:** A shot row `{"id": "S01", "editorial_duration_sec": true}` → row `seconds` becomes `True` instead of `0`. A row with `"seconds": null` → `seconds: null`. The UI may display "True"/"null" or fail on arithmetic.

**One-line fix:** Replace the inline expression with `max(0, num(secs))` (the `num()` helper already used two lines below at 744) or call `_pipeline().shot_seconds(s)` for consistency.

---

### Unverified (no source available)

- `h3/router.py` RF-03 ref-list fix
- `schema_and_linter.py` non-object `timing_and_lattice` / `episode_plan`
- `compile_h3_sing8.py` exception wrapping
- All earlier round-2 fixes in `h3_author`, `v4_to_h3`, `voice_manifest`, `gate_d_audio`, `render_controller`, `voice_engine`, `director/write_pack`, `pack_validator`, `run_registry`, `retry_policy`
- `ui/static/app.js` `loadStory` array guard and `loadDetail` single-flight
- `_per_language` reason filtering at `pipeline.py:848` (`f" {lang}: "` format assumption)
- JS/server contract mismatches (no `app.js` available)

---

FINAL:

1. **LOW** — `server.py:737` — `read_pack` returns raw bool/None/string for invalid shot seconds instead of 0.0, inconsistent with `pipeline.py:96-103`. Fix: use `max(0, num(secs))` or `_pipeline().shot_seconds(s)`.


# BATCH r4c_tests (dots) 11-07 10:14



I reviewed the three Round-4 regression-test artifacts against the Round-2 fix list and the OWNER spec. Most fixes are only observable through these tests, so I report what the artifacts actually let me confirm. Source files were not provided, so anything not pinned by a test is marked unverified rather than guessed.

=== FILE test_r4_fixes.py (triage R4-DIR) ===
- **low** — L71-77 `test_bool_episode_number_is_not_an_episode`: the `except ValueError: return` means the test passes vacuously if `episodes_from` *rejects* a bool episode instead of *filtering* it. The "bool is not an episode → eps == [2]" contract is only verified when episodes_from succeeds. Fix: drop the try/except and assert `eps == [2]` unconditionally, or assert the return value inside the except branch.
- **medium (unverified)** — L26-29 `test_envelope_check_classifies_empty_and_cut_off_answers`: only `envelope("", stop)`, `envelope("", length)`, and `envelope("text", stop)` are covered. A non-empty *truncated* answer `envelope("text", length)` is never tested, so a finish-reason-first implementation (return EMPTY_CUT_OFF for any `"length"` finish) would misclassify valid truncated answers and trigger needless model switches/retries. Fix: add `assert envelope_check(envelope("text","length","nvidia","m")) is None`.
- **low (unverified)** — L80-84 `test_row_level_narration_by_lang_needs_a_narrator_voice`: this is the only test that places `narration_by_lang` at the row top level instead of under `audio_and_dialogue_track`; every other test nests it. If the schema requires the nested location, this feeds malformed input and reports VM-01 (voice) instead of a structural error, masking the real problem. Fix: move the block under `audio_and_dialogue_track` to match the schema used elsewhere.

=== FILE test_r4_fixes.py (triage R4-H3) ===
- **low** — L1-2 docstring claims "the CLI --allow-partial path is covered by the AttributeError handler in render_controller.main", but the only `rc.main` test at L20-31 passes `--dry-run`, not `--allow-partial`. The handler's behavior on the actual `--allow-partial` path is therefore untested. Fix: add a `--allow-partial` invocation (or correct the docstring's coverage claim).

=== FILE test_r4_fixes.py (triage R4-UI) ===
- no findings. The unhashable-episode, zero-seconds, and string-takes tests are sound and consistent with the described fixes (zero/negative seconds clamp to 0 for summation while the `seconds>0` check still flags them; `takes_of` must coerce strings before the 1–10 range check, which the string test pins). Minor note only: the takes boundary is exercised with ints (0, 5, 11) and one string ("3"); negative/float/string-out-of-range inputs are covered only indirectly.

=== Unverified Round-2 fixes (no source available; cannot confirm or deny) ===
- h3 router ref-lists / RF-03 non-dict keyframes; schema_and_linter non-object timing_and_lattice & episode_plan; compile_h3_sing8 compile_episode exception wrapping; h3_author / v4_to_h3 trim-handles-seams + author lint/repair + cache; voice_manifest build_manifest/VO_UNREADABLE; gate_d_audio PLAN-01/TIME-01/BGM/`check_music_presence` -inf handling; voice_engine; director write_pack `call_path`/`ModelGaveUp`/EMPTY vs EMPTY_CUT_OFF; pack_validator tone/ML-06/screen/depth; run_registry h3-voice-only-for-en + U+0933 Marathi detection; story_state resume; render_controller default language hi.
- Owner-spec invariants with **no regression test at all**: captions bottom 896 / top 360 / sides 160; sound cue in all 7 action sentences; UI binds 127.0.0.1; approvals scoped by story+pack; Gate A blocked on validator errors; "code never calls ElevenLabs/Colab/ffmpeg/model by default" gating; "video rendered ONCE, shared, mouth closed" vs render_controller's default-language-hi.

FINAL:
1. **low**, test_r4_fixes.py (R4-DIR) L71-77 — `test_bool_episode_number_is_not_an_episode` early-returns on ValueError, so it cannot fail if the fix rejects bool episodes rather than filtering them; the intended `eps == [2]` behavior is unverified. Fix: assert `eps == [2]` unconditionally (remove the swallow).
2. **medium (unverified)**, test_r4_fixes.py (R4-DIR) L26-29 — `envelope_check` is never tested with a non-empty truncated (`length`) answer; a finish-reason-first implementation would misclassify it as EMPTY_CUT_OFF and cause needless model switches. Fix: add the `envelope("text","length") → None` assertion.
3. **low**, test_r4_fixes.py (R4-H3) L1-2 vs L20-31 — the docstring claims `--allow-partial` coverage but the only `rc.main` test uses `--dry-run`; the actual `--allow-partial` AttributeError path is untested. Fix: add a `--allow-partial` test variant.
4. **medium (unverified)** — multiple owner-spec invariants (caption margins 896/360/160, 7 action-sentence sound cues, UI 127.0.0.1 bind, story+pack-scoped approvals, Gate A blocked on validator errors) have zero regression tests, so any regression there is undetected. Fix: add one targeted test per invariant.
5. **low (unverified)** — render_controller's "default language hi" fix vs the "video rendered ONCE (shared pure-Foley, mouth closed)" spec: if the default language drives a language-specific render it contradicts the single-shared-render contract; if it only sets captions/voice default it is fine. Untested either way. Fix: assert the shared render output is language-independent at the default, or document the scope.
