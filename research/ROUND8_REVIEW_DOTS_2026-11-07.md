

# BATCH r8_cue_layer (dots) 11-07 15:53



=== FILE caption_cues.py ===
low, caption_cues.py:114, build_cue_list raises TypeError/ValueError/KeyError on non-dict cues or cues missing t0/t1/text, violating the module's "Never raises on junk cues" spec. Fix: filter spoken to only valid dicts with numeric t0/t1 and text key before sorting.

=== FILE test_caption_cues.py ===
no findings

FINAL:
1. low, caption_cues.py:114, build_cue_list raises on junk cues (non-dict, missing t0/t1/text) violating the module's "Never raises on junk cues" spec. Fix: filter spoken to valid dicts with numeric t0/t1 and text key before sorting.


# BATCH r8_engine (dots) 11-07 15:57



## Reasoning

I reviewed the two provided files (`captions.py` and `test_captions_engine.py`) line by line against the owner spec and the listed round-1/round-2 fixes. The other files mentioned in the fix list (app.js, pipeline.js, server.py, pipeline.py, h3 router.py, schema_and_linter.py, compile_h3_sing8.py, h3_author, v4_to_h3, voice_manifest, gate_d_audio, render_controller, voice_engine, write_pack, pack_validator, run_registry, retry_policy, story_state) were **not provided**, so those fixes cannot be verified here.

**captions.py** — The public `build_ass` entry point correctly wraps `_build` in a try/except that catches `_Junk` and generic `Exception`, returning a minimal ASS + FAIL entry (never raises on junk input). All trust-boundary validations (`_dims`, `_validate_core`, `_clean_cues`, `_cards`, `_family`, `_find_font`) guard against non-objects, bad numeric ranges, empty strings, and missing keys. The `_cards` function correctly refuses to split cues that already carry aligned `words` (line 223), so karaoke timing cannot be corrupted by card-splitting. The face-avoidance while-loop has a proper `else` clause and a `lo` bound that prevents infinite loops. The `_escape` function strips backslashes from user text before ASS tags are injected, preventing tag injection. The style and dialogue format strings have the correct field counts. No logic errors, no crashes on bad input, no spec violations (no ElevenLabs/Colab/ffmpeg calls, no model calls).

**test_captions_engine.py** — All six tests are structured so that they **can** fail (they assert specific word counts, time values, tag contents, and entry presence). No test is a tautology. The one caveat is that `test_short_cue_is_not_split...` (6 words, expects 1 row) and `test_long_cue_is_split...` (13 words, expects [5,5,3]) both depend on the core's `captions.max_words` being exactly 6; if the core config changes, one of them could fail. That is a test/config coupling, not a code defect, and is marked unverified since `load_core()`'s output was not provided.

No regressions, no wrong/incomplete fixes, no JS/server contract issues (these are pure-Python files), and no tests that cannot fail were found.

=== FILE captions.py ===
no findings

=== FILE test_captions_engine.py ===
no findings

FINAL: no real defects found


# BATCH r8_post_voice (dots) 11-07 16:06



Based on my review of the two provided files (`post.py` and `test_post_voice.py`), I found no concrete defects. The remaining files referenced in the prompt were not provided, so their round-2 fixes cannot be verified.

**post.py**: The voice resolution logic (lines 488-490) is correct for all expected inputs. The ffmpeg graph construction, error handling, and refuse/write flow are sound. The default language "hi" at line 324 matches the render_controller round-2 fix. No crashes on bad input; `run_post()` wraps everything in a try/except.

**test_post_voice.py**: All tests have real assertions that can fail. No tests are vacuous. The loudness tolerance (±3 LU) is reasonable for synthetic clips.

**Unverified**: The round-2 fixes in `gate_d_audio` (per-language PLAN-01 guard, TIME-01 on bad range, empty BGM tracks, reel id sanitized) could not be checked because `h3/gate_d_audio.py` was not provided. If `build_vo_stem_filter`, `build_voice_branch`, `shot_has_speech`, or `vo_fit_check` changed their return structures or signatures, `post.py` lines 501, 522, 545-546 might break — but `run_post()`'s outer try/except would convert any such breakage into a POST FAIL entry rather than a crash.

FINAL: no real defects found in the provided files


# BATCH r8_gate_d (dots) 11-07 16:10



## ROUND 3 review — `gate_d_audio.py` and `test_gate_d_captions.py`

I could only inspect the two files pasted below; every other file named in the round-2 fix list (app.js, pipeline.js, server.py, pipeline.py, h3 router, schema_and_linter, compile_h3_sing8, h3_author, v4_to_h3, voice_manifest, gate_d_audio's neighbours, render_controller, voice_engine, write_pack, pack_validator, run_registry, retry_policy) was **not** supplied, so those fixes are **unverified**.

### Verified-correct round-2 fixes in `gate_d_audio.py`
- per-language PLAN-01 guard (689‑694) — correct; a disallowed engine gets a PLAN-01 report and no mix.
- TIME-01 on bad range (685‑687, `same_timing_problems` 710‑746) — correct; non-dict `*_by_lang`, non-positive `editorial_duration_sec`, and cross-language range drift are all flagged, and `parse_time_range` failures are caught.
- empty BGM tracks = no BGM (522, 218) — correct; `tracks: []` → `bgm_path=None`, non-empty requires exactly one track.
- reel id sanitised (670‑671) — correct.
- `_editorial_len` zero/negative → 0.0 (649‑652) — correct.

### Findings

**[medium] gate_d_audio.py:112** — `check_narration_density` divides by `(e - s)` with no guard. A speech item whose `time_range` collapses to a point (e.g. `"3.0-3.0"` with non-empty text) makes `e - s == 0` and raises `ZeroDivisionError`. This is **not** caught by the per-language wrapper at 702, which only catches `ValueError, KeyError, TypeError, AttributeError`, so it propagates out of `plan_language_outputs` and crashes the whole pipeline on malformed owner input.
- Failing input: `shots[0].audio_and_dialogue_track.narration = {"text": "hello", "time_range": "3.0-3.0"}` → `plan_language_outputs(...)` raises `ZeroDivisionError`.
- Fix: `words = sum(n * _overlap(s, e, 0.0, win) / (e - s) for s, e, n in items if e > s)`.

**[low] gate_d_audio.py:689** — `engine_for(voice_engines, lang)` runs *before* the `try` at 695. If `voice_engines` is a dict that does not contain `lang`, the behaviour depends on an unverified helper (return‑None → safe PLAN‑01; raise → uncaught crash). Unverified which it does; if it raises, `plan_language_outputs` crashes for that story.

**[low] test_gate_d_captions.py:133‑143** — `test_gate_d_refuses_a_wrong_script...` depends entirely on the private `_story()`/`_run()` helpers in `h3.tests.test_gate_d_audio` (imported at 135). The "hi → CAPTION_SCRIPT" and "en → ok" branches are only as good as that fixture's narration/hook structure; if `_story()` ships no English narration the second `assert out["ok"]` cannot hold. Unverified without that module.

**[low] test_gate_d_captions.py:96** — `assert "fontsdir=" in gd.build_subtitles_filter(...)` is a constant substring that `build_subtitles_filter` (462) hardcodes itself; it cannot fail unless the function is edited, so it guards nothing about the actual path value.

**[unverified] gate_d_audio.py:424‑426 / core/captions.py** — the positional/keyword contract of `_engine_build_ass` (and whether `load_core()`'s `safe_zone_frac` / `play_res` match the owner's "captions bottom margin 896, top 360, sides 160") is not checkable without `core/captions.py` and `h3/shot_table_spec.py`. The test's `0.575 * play_res[1]` centre vs. a 9:16 1080×1920 frame (bottom margin 896 ⇒ y ≤ 1024 = 0.533h) does not obviously line up; unverified.

### Files with no real defects
- `gate_d_audio.py`: apart from the division guard above, the mix/mux numbering (sfx_ref, vo_refs, bgm_idx vs. `build_final_mux_argv` input ordering), the h3 vs. elevenlabs branch selection, the BGM/VO/caption gate ordering, and the loudness parsing are all consistent. No other concrete defect found.
- `test_gate_d_captions.py`: every assertion is falsifiable except the constant-substring check noted above; no tautological or impossible-to-fail tests beyond that.

---

FINAL:
1. **[medium] gate_d_audio.py:112** — unguarded `(e - s)` division in `check_narration_density` raises `ZeroDivisionError` on a point `time_range` (e.g. `"3.0-3.0"`); not caught by the 702 wrapper, so `plan_language_outputs` crashes. Fix: `... for s, e, n in items if e > s`.
2. **[low] gate_d_audio.py:689** — `engine_for(voice_engines, lang)` executes before the `try`; unverified whether a missing language key raises (would be uncaught).
3. **[low] test_gate_d_captions.py:133‑143** — correctness of the "hi fails / en passes" caption-script assertions rests on the unverified `_story()`/`_run()` fixture.
4. **[low] test_gate_d_captions.py:96** — `"fontsdir=" in ...` is a hardcoded constant, a near-tautological assertion.
5. **[unverified] gate_d_audio.py:424‑426** — `_engine_build_ass` call contract and the caption band vs. owner margins (896/360/160) cannot be confirmed without `core/captions.py`.
