

# BATCH r4b_director (dots) 11-07 09:27



## ROUND 3 REVIEW — `write_pack.py` + `pack_validator.py`

The other files named in the round-2 fix list (`app.js`, `pipeline.js`, `server.py`, `pipeline.py`, `h3/router.py`, `schema_and_linter.py`, `compile_h3_sing8.py`, `h3_author`, `v4_to_h3`, `voice_manifest`, `gate_d_audio`, `render_controller`, `voice_engine`, `run_registry`, `retry_policy`) were **not provided**, so those fixes could not be verified. Only the two files above were checkable.

---

### HIGH

**pack_validator.py:1021-1028 (validate_pack) — reads raw model envelopes as parsed stage data**
`write_pack.run_staged` writes `stage_1_raw.json` / `stage_2_raw.json` as the **model envelope** (`{"type":"result","is_error":...,"result":"<text with json block>","via":...,"model":...}`), not as parsed stage data. `validate_pack` globs `stage_1*.json` / `stage_2*.json` and passes them straight to `validate_stage("story"/"bible")`. The envelope has no `story_gate_checks` → 7× `STORY-01/02/03` false errors; no bible sections → `BIBLE-01/03/05/06/08` false errors. Same root cause makes `_peek_output_languages` (976-985) and `_peek_voice_engines` (988-997) return `None` for every staged pack, so `ML-03`/`ML-04` and the `VA-*` voice checks are silently skipped there.
Concrete failing input: any staged pack folder → `python director/pack_validator.py <pack>` exits 1 with `ERROR STORY-01 story_gate_checks: missing story_gate_checks object`.
One-line fix: in `validate_pack`, validate `story_plan.json` as the story data (it carries `story_gate_checks`, `output_languages`, `voice_engine`) and skip or envelope-extract the `*_raw.json` files (or have `run_staged` write a parsed `stage_1.json`/`stage_2.json`).

---

### LOW

**write_pack.py:392-394 (episodes_from) — bool episode slips through**
`isinstance(v, int)` is `True` for `bool`. A stage-1 episode block element `{"episode": true}` (or a bare `true`) passes the filter, `sorted(set(found))` yields `[True]`, and the stage is named `f"3e{True}"` = `"3eTrue"`; `seconds.get(True)` also silently matches key `1`.
One-line fix: change line 384 to `isinstance(e.get("episode"), int) and not isinstance(e.get("episode"), bool)` and line 392 to the same guard on `v.get("episode")`.

**pack_validator.py:650 — "eyeline" label is actually the facing direction**
`_positions` returns `(_side(screen), _side(facing))`, but the flip message labels index `[1]` as `"eyeline"`. Detection is correct; only the owner-facing text names the wrong anchor axis.
One-line fix: rename the tuple label from `"eyeline"` to `"facing"`.

**pack_validator.py:847 vs 463 — `narration_by_lang` lookup inconsistent**
`_check_languages` (463) uses `_by_lang(r, k)` which falls back to the row level outside `audio_and_dialogue_track`; `_check_voice` (847) iterates `_d(track.get("narration_by_lang"))` directly. A multilingual row that places `narration_by_lang` on the row (not in the track) passes `ML-*` but skips the `VM-01` narrator-voice check.
One-line fix: at line 847 use `_by_lang(r, "narration_by_lang")` instead of `track.get(...)`.

---

### Unverified
- `write_pack.py:102/295` — envelope `is_error` vs `retry_policy.answer_kind(result, finish_reason)`: whether a provider that omits `finish_reason` but returns non-empty text would be marked errored by `answer_text` after the retry policy accepted it. Depends on `retry_policy.answer_kind`, which was not provided.
- Whether the pipeline gate uses `validate_pack` (CLI) or in-process `validate_stage` — this determines the real-world severity of the HIGH finding above.

---

### Verified clean (no findings in these sections)
`parse`, `parse_story`, `parse_bible`, `parse_captions`, `episodes_from`, `merge_episodes`, `apply_captions`, `legacy_fields`, `run_stage` retry/repair loop, `run_single`, `run_staged` stage routing (`stage_setting`, `call_for`), `refuse_finished`, `checked_call`, `answer_text`, `envelope`/`envelope_check`, `call_path`/`call_nvidia`/`call_openrouter`/`call_claude`, `resolve_route`, `stage_errors`, `with_language`, `shot_language_errors`, `caption_language_errors`, `voice_setting`; and in the validator: `_check_rows`, `_check_audio` (tone required, non-empty sfx, mouth closed), `_check_languages` (ML-01..08), `_check_voice` (VM-01/02, VA-01/02, VE-05), `self_check` (S55-1..6, REEL-01), `_validate_story`, `_validate_bible`, `repair_loop`, `_legacy_checks`, `_load`, CLI. The round-2 fixes that live in these two files (tone required, ML-06 narration-vs-shot-length, bool-not-int on `lattice_n`/`off_stage_shots`/episodes, non-empty screen/depth) are present and consistent.

---

FINAL:
1. HIGH — pack_validator.py:1021-1028 `validate_pack` reads `stage_1_raw.json`/`stage_2_raw.json` model envelopes as parsed stage data → false STORY-01/02/03 and BIBLE-01/03/05/06/08 errors on every staged pack; `_peek_output_languages`(976)/`_peek_voice_engines`(988) likewise return None for staged packs.
2. LOW — write_pack.py:392-394 bool episode value passes `isinstance(int)` and produces a `3eTrue` stage name.
3. LOW — pack_validator.py:650 flip message labels the facing axis as "eyeline".
4. LOW — pack_validator.py:847 vs 463 `narration_by_lang` lookup inconsistency (track-only vs `_by_lang` row fallback) skips VM-01 for row-level blocks.
5. Unverified — write_pack.py:102/295 envelope `is_error` vs `retry_policy.answer_kind` consistency (depends on unprovided `retry_policy`).


# BATCH r4b_h3 (dots) 11-07 09:37



## Findings

### 1. HIGH — gate_d_audio.py:694 (also :733, :170)
`_plan_one_language` identifies shots with `sid = s["id"]` (and `shots[ci]["id"]`, `closing_shot.get('id')`), but the h3 shot schema key is **`shot_id`** (`schema_and_linter.SHOT_KEYS`; an `id` key would be flagged as an extra top-level key SC-01 by `_check_keys`). Every SPEC story passes shots with `shot_id` only, so `s["id"]` raises `KeyError` on the first shot. `plan_language_outputs` catches it (line 832) and converts it into a `PLAN-01` error for **every** language → Gate D always fails, no mix/mux argv is ever planned, and `vo_files` is never populated.
**Fix:** `sid = s.get("shot_id") or s.get("id")` (and the same at lines 733 and `where = f"shot {closing_shot.get('shot_id') or closing_shot.get('id')}"`).

### 2. MEDIUM — gate_d_audio.py:544 vs :716-719
`write_captions()` exists but is never called. `_plan_one_language` only calls `build_ass(...)[1]` (warnings) and discards the text. The mux argv is built with `burn_captions=True` (default) and `ass_path=plan["caption_path"]` (`export/<reel>_<lang>.ass`), and `build_subtitles_filter` references that path — but nothing writes it, so the final render's subtitle filter points at a missing `.ass`. The plan also does not carry `face_boxes`/`fonts_dir`, so a downstream writer cannot reproduce it either.
**Fix:** in `_plan_one_language`, write the file: `warnings.extend(write_captions(plan["caption_path"], cues, face_boxes, fonts_dir, lang))` (and store `face_boxes`/`fonts_dir` in the plan if the render step is expected to do it).

### 3. LOW — gate_d_audio.py:262-267 vs :668
Policy set in round 2 is "empty BGM tracks = no BGM": `_bgm_track` returns `[], None` for `{"tracks": []}`. But the public `read_bgm_manifest`/`validate_bgm_manifest` still emit `BGM_MANIFEST_EMPTY` for an empty tracks list. So the same manifest file is "no BGM" through `_bgm_track` and "error" through `read_bgm_manifest`.
**Fix:** treat an empty `tracks` list as valid (no BGM) in `validate_bgm_manifest`, or map `BGM_MANIFEST_EMPTY` to "no BGM" in `_bgm_track`.

### 4. LOW — schema_and_linter.py:903
`lint_shot` calls `shot.get("shot_id", ...)` before any guard; the per-shot check functions are wrapped in `_run` but this line is not. A non-dict shot row (a trust boundary — e.g. a test or a malformed episode) raises `AttributeError` and crashes the linter instead of reporting `SC-01`/`SC-02`.
**Fix:** at the top of `lint_shot`, `if not isinstance(shot, dict): return {"errors": [f"{sid}: SC-02 shot must be an object"], "warnings": []}`.

### 5. LOW — voice_manifest.py:49-53
`voice_ids_for` iterates `trk.get("dialogue") or []` and calls `d.get("speaker")` without checking `isinstance(d, dict)`. A non-dict entry (or a `dialogue` value that is a non-list, e.g. a dict) raises `AttributeError` inside `build_manifest` (called from the CLI and from any caller).
**Fix:** `for d in trk.get("dialogue") or []: if not isinstance(d, dict): continue`.

---

Notes: the UI/server-side round-2 fixes (`app.js` X-UI header, `loadStory` array guard, `pipeline.js` Save-story pack scoping, `loadDetail` single-flight, `server.py` record_spend timing, `pipeline.py` shot-second clamping, `h3/router.py` RF-03 ref lists, `compile_h3_sing8.py` exception wrapping) could **not** verified — those files were not included in this round. No findings in the parts of `render_controller.py`, `schema_and_linter.py`, `voice_manifest.py`, and `gate_d_audio.py` beyond those above.

FINAL:
1. HIGH — gate_d_audio.py:694 — shot id read as `s["id"]` instead of `shot_id`; KeyErrors on every real story, Gate D always fails with PLAN-01. Fix: `s.get("shot_id") or s.get("id")`.
2. MEDIUM — gate_d_audio.py:544/716 — `.ass` caption file never written although the mux argv burns it in by default. Fix: call `write_captions(...)` in `_plan_one_language`.
3. LOW — gate_d_audio.py:262 vs :668 — `read_bgm_manifest` errors on empty `tracks` while `_bgm_track` treats it as no BGM. Fix: align the two.
4. LOW — schema_and_linter.py:903 — `lint_shot` crashes on a non-dict shot instead of reporting SC-02. Fix: guard at the top.
5. LOW — voice_manifest.py:49 — `voice_ids_for` does not guard non-dict `dialogue` entries. Fix: `if not isinstance(d, dict): continue`.


# BATCH r4b_ui (dots) 11-07 09:47



After reviewing the code against the round-2 fix list and owner spec, here are the real defects found.

---

**HIGH**

**1. pipeline.py:848-852 — `_per_language` crashes on a gate_d step with `reasons: None` or missing `status`**
The expression `(gd["reasons"] if gd else [])` returns `None` when `gd` is a non-empty dict whose `"reasons"` value is `None`; iterating over `None` raises `TypeError`. Likewise `gd["status"]` at line 851 raises `KeyError` if the key is absent. A malformed H3 plan (or a future version that omits these keys) crashes the `/api/render/status` endpoint.
Concrete failing input: `plan["steps"]` contains `{"id": "gate_d", "status": "ready"}` (no `"reasons"` key) → `KeyError` at line 848.
One-line fix: change to `gd.get("reasons") or []` and `gd.get("status")`, and guard the whole block with try/except or default the step dict.

---

**MEDIUM**

**2. pipeline.py:318-321 — `gate_d_problems` crashes on the same malformed gate_d step**
`gd["status"]` and `gd["reasons"]` are accessed without `.get()`. This is called from `apply_gate` (line 643-646) which has no try/except around `gate_d_problems`, so a malformed step produces a 500 instead of a clean rejection.
One-line fix: use `gd.get("status")` and `gd.get("reasons") or []`.

**3. server.py:422 and server.py:1550 — episode type mismatch in `scope_ids` and `export`**
`s.get("episode") == reel` compares the shot's episode value directly against an `int` (from the REEL validator). If `shots.json` stores episodes as strings (e.g. `"1"`) or as `EP_01`, the comparison fails silently, returning an empty shot list. The same pattern exists in both `scope_ids` (line 422) and `export` (line 1550). The `read_pack` and `summary` functions already handle mixed episode types, but these two paths do not.
Concrete failing input: `shots.json` has `"episode": "1"` (string), `reel=1` (int) → `picked` is empty → `bad("no shots in reel 1")` or an empty `shot_ids` list in export.
One-line fix: normalize both sides, e.g. `str(s.get("episode")) == str(reel)`.

**4. pipeline.py:807 — `render_status` crashes if `shot_table_spec` is importable but lacks `HUMAN_CHOICES`**
`_h3_ok()` only tests importability, not the presence of `HUMAN_CHOICES`. If the module is importable but the attribute is missing, `list(_h3("shot_table_spec").HUMAN_CHOICES)` raises `AttributeError` and crashes `/api/render/status`.
One-line fix: wrap the attribute access in a try/except or check `hasattr` before accessing.

**5. pipeline.py:871,878,882,885 — `_manifest_status` accesses `am.*` attributes outside any try/except**
After the initial `load_manifest` try/except (lines 865-869), the code uses `am.PLACEHOLDER_STATUS`, `am.hash_bible`, `am.hash_shot_row`, `am.blocking_problems` (partially guarded), and `am.is_stale` with no exception protection. If the `asset_manifest` module is importable but missing any of these, `_manifest_status` crashes, taking down `render_status`.
One-line fix: wrap the post-load logic in its own try/except that returns the `empty` dict with a `blocking_problems` entry.

---

**LOW**

**6. pipeline.py:138-139 — `takes_of` accepts 0, which breaks the render-stage logic**
The server validates `takes` as 1-10 (server.py:1180), but `takes_of` returns the stored value as long as it is a non-negative int. A `takes` of 0 (possible via direct JSON edit) yields `planned_clips = 0`, which makes the render stage permanently `"ready"` (line 534 condition `f["planned_clips"] > 0` is false, falls through to line 542). The stage can never reach `waiting_approval`.
One-line fix: change `t >= 0` to `1 <= t <= 10` (matching the server validation).

**7. server.py:1534 — `results_roots` assumes every element of `story_links.check()` is a dict**
The list comprehension accesses `l["resolved"]`, `l.get("kind")`, etc. If `check()` returns a list containing a non-dict (e.g. a string or `None`), this crashes with `TypeError`. The `story_links` module is internal, but the trust boundary is the module's contract.
One-line fix: add `isinstance(l, dict)` to the comprehension filter.

---

**FINAL:**
1. HIGH — pipeline.py:848-852 `_per_language` crashes on None reasons / missing status in gate_d step
2. MEDIUM — pipeline.py:318-321 `gate_d_problems` crashes on malformed gate_d step (missing keys)
3. MEDIUM — server.py:422,1550 episode type mismatch in `scope_ids` and `export` (int vs string comparison)
4. MEDIUM — pipeline.py:807 `render_status` crashes if `shot_table_spec` lacks `HUMAN_CHOICES`
5. MEDIUM — pipeline.py:871-885 `_manifest_status` accesses `am.*` attributes outside try/except
6. LOW — pipeline.py:138 `takes_of` accepts 0, breaking render-stage logic
7. LOW — server.py:1534 `results_roots` does not guard non-dict items from `story_links.check()`


# BATCH r4b_tests (dots) 11-07 09:55



The review examined the provided round‑4 regression test files against the described round‑2/round‑3 fixes. Several test suites were analysed for correctness, completeness, and ability to detect regressions. The analysis focused on concrete defects in the tests themselves (incomplete assertions, masked failures, unverified fixes) that could allow real bugs to ship. Five issues were identified, ranging from medium to low severity. No high‑severity defects were found in the limited code paths covered by the tests, but the test coverage gaps noted could hide regressions in episode sorting, model‑answer handling, and voice‑manifest error handling.

**Findings:**

1. **Medium** – `test_r4_fixes.py` (first block), lines 71‑77  
   *What is wrong:* `test_bool_episode_number_is_not_an_episode` wraps `episodes_from` in a bare `try/except`. If the function raises `ValueError`, the test passes immediately, even if the function does not actually filter boolean episode numbers. A regression that makes the function raise on valid input would be invisible.  
   *Concrete failing input:* A story JSON containing `{"episodes": [{"episode": true}, {"episode": 2}]}` where `episodes_from` incorrectly raises `ValueError` instead of returning `[2]`.  
   *One‑line fix:* Remove the `try/except` and assert `write_pack.episodes_from(text) == [2]`.

2. **Medium** – `test_r4_fixes.py` (third block), lines 15‑21  
   *What is wrong:* `test_summary_unhashable_episode_does_not_raise` verifies only the *set* of string‑converted episode numbers, not their order. The underlying episode sort in `server.py`/`pipeline.py` may use string conversion to handle mixed types, which would mis‑order numeric episodes (e.g., `1, 10, 2`). The test cannot detect this regression.  
   *Concrete failing input:* A story with episodes `1, 2, 10`; the UI would display them as `1, 10, 2` if a string‑based sort is used.  
   *One‑line fix:* Assert the exact order of `out["episodes"]` (e.g., `[1, 2, 10]`) or use a sort key that preserves numeric order, such as `key=lambda e: (isinstance(e, int), e)`.

3. **Low** – `test_r4_fixes.py` (third block), lines 45‑51  
   *What is wrong:* `test_string_takes_in_project_json_does_not_break_the_summary` only passes a numeric string `"3"`. If `project.json` contains a non‑numeric string like `"abc"`, the `int()` conversion will raise `ValueError` and crash the summary. The test does not cover this trust‑boundary input.  
   *Concrete failing input:* `project.json` with `"takes": "abc"`.  
   *One‑line fix:* Add a test with a non‑numeric string and ensure the code uses a safe conversion (e.g., `try/except` or `str.isdigit()` with a default of `0`).

4. **Low** – `test_r4_fixes.py` (second block), lines 20‑31  
   *What is wrong:* `test_main_reports_attribute_error_from_prepare_as_exit_1` verifies that `render_controller.main` exits with code 1 when `prepare` raises `AttributeError`. It does **not** directly test the `compile_h3_sing8.py` `compile_episode` wrapping fix (which should catch `TypeError`/`ValueError`/`AttributeError`). That fix remains completely unverified.  
   *Concrete failing input:* A story that causes `compile_episode` to raise one of the wrapped exceptions; if unwrapped, the pipeline crashes instead of failing gracefully.  
   *One‑line fix:* Add a direct unit test for `compile_episode` passing malformed input and expecting a handled error/exception.

5. **Low** – `test_r4_fixes.py` (third block), lines 35‑42  
   *What is wrong:* `test_zero_seconds_shot_without_episode_clears_all_have_seconds` only checks a shot with `editorial_duration_sec = 0`. The “negative seconds count as 0” part of the fix is not exercised. A regression that fails to treat negative seconds as zero would go unnoticed.  
   *Concrete failing input:* A shot with `editorial_duration_sec = -5`; the “every shot has seconds>0” check may not fail as expected.  
   *One‑line fix:* Extend the test to include a negative duration and assert the check is `False`.

**Unverified fixes (no concrete defect, but no test coverage):**  
- `schema_and_linter.py` non‑object `timing_and_lattice` and `episode_plan`  
- `run_registry` Marathi detection (U+0933) and H3‑voice‑only‑for‑en logic  
- `compile_h3_sing8` episode‑not‑found / missing‑profile‑key handling  
- UI changes (app.js X‑UI header, pipeline.js single‑flight, server POST body pack)  

These lack corresponding tests; they are not flagged as defects but would benefit from regression tests.

---

**FINAL:**  
1. Medium – `test_r4_fixes.py` (first block) 71‑77: bare `try/except` masks failures in `episodes_from`.  
2. Medium – `test_r4_fixes.py` (third block) 15‑21: missing order assertion hides episode‑sort regressions.  
3. Low – `test_r4_fixes.py` (third block) 45‑51: non‑numeric `takes` string not tested, potential crash.  
4. Low – `test_r4_fixes.py` (second block) 20‑31: `compile_episode` wrapping fix untested.  
5. Low – `test_r4_fixes.py` (third block) 35‑42: negative seconds not covered by the zero‑seconds test.
