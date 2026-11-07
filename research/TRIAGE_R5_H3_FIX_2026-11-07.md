# TRIAGE R5 H3 FIX (2026-11-07)

Scope: six defects from the R5 review, fixed by agent R5F. Test file: h3/tests/test_r5_fixes.py (6 tests).
Suite: h3 582 pass (baseline 576 + 6 new). Director not touched, not run.

| # | Item | Verdict | File:line (after fix) | Test |
|---|---|---|---|---|
| 1 | check_music_presence compares `v >= speech_gate_db` before isfinite; string levels raise TypeError; sorted(bgm_db) unfiltered | REAL, fixed. Added `_is_db` (finite real, not bool). Speech windows and bgm floor filter on it. Error codes unchanged. If no finite BGM level remains, returns BGM_SILENT_FLOOR. | h3/gate_d_audio.py:270, 284, 294 | test_r5_music_presence_string_levels_do_not_raise_type_error |
| 2 | voice_ids_for reads `dialogue` only; multilingual tracks lose speakers | REAL, fixed. Uses dialogue_by_lang[lang] when that dict has the language, else old behaviour. | h3/voice_manifest.py:50 | test_r5_voice_ids_use_dialogue_by_lang_for_the_language |
| 3 | Shot with editorial length 0 still added to `existing` for vo_fit_check (VO_OVERFLOW_ERROR) | REAL, fixed. Appended only when ed > 0. vo_files and vo_clips unchanged. | h3/gate_d_audio.py:716 | test_r5_zero_editorial_shot_is_not_fit_checked |
| 4 | Bool pixel_frames counted as 1 frame / 1 second in totals | REAL, fixed. _num rejects bool; pixel_frames int check rejects bool. | h3/render_controller.py:274, 307 | test_r5_bool_pixel_frames_do_not_count_as_frames |
| 5 | lint_story: compiled_map.get(sid) raises TypeError for unhashable sid | REAL, fixed. Lookup only for str sid. Duplicate-id scan (h3/schema_and_linter.py ~961-967) already guards with isinstance str; left unchanged as instructed. | h3/schema_and_linter.py:982 | test_r5_list_shot_id_is_linted_not_a_type_error |
| 6 | NO_VO_FILES raised for any language with no VO files, even with no speech | REAL, fixed. any_speech flag set in the shot loop; error only when a shot had speech in the language and no VO file exists. | h3/gate_d_audio.py:711, 720 | test_r5_foley_only_reel_has_no_no_vo_files_error |

Notes:
- Two existing tests pinned the old NO_VO_FILES behaviour and were updated to the new rule: h3/tests/test_gate_d_audio.py (test_language_with_no_vo_and_no_captions_fails_only_itself) and h3/tests/test_voice_gate_d.py (test_en_h3_plan_needs_no_vo_files_and_warns_about_render_once).
- Not changed (owner decisions): empty BGM tracks rule in validate_bgm_manifest; execution_profile missing or non-dict in lint_story; non-dict shot rows in lint_story.
