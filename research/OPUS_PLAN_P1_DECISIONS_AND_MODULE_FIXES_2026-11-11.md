# P1: Owner decisions and Step 0 job cards

## (A) OWNER DECISIONS

| ID | Decision | Recommended answer | Why | Blocks |
|---|---|---|---|---|
| D1 | Default image mode: "S" (start only) or "SE" (start + end) | **SE is the default.** S stays behind `SHOT_MODE_S_ALLOW=1`. When S is not allowed, `route_shot` turns S into SE and REF_S into REF_SE (references kept, h3_mode Ref2VA). The SHOT-008 A/B test (~1-4 Colab units) waits for your separate go and for you to say who pays. | S has no compile workflow today: `compile_h3_sing8.py:147` knows only FL2VA and Ref2VA. With S as default, `shot_mode.py:17-22` would raise on every plain shot (E1). | S-06, S-07 |
| D1b | REF_SE workflow: does a reference shot with S off go to Ref2VA (refs) or FL2VA (A/B pictures)? | Ref2VA. This is unproven: the step 8 offline trace must show that Wan2GP accepts it. | Ref2VA has no Picture 1/2 alignment header (`compile_h3_sing8.py:88-125`). | S-06 (h3_mode value only) |
| D2 | Linter rule SX-01 (a sound cue in all 7 action sentences, `schema_and_linter.py:112`, rule 27) or cue words out of the visual sentence (problems 26, 27) | **Amend SX-01.** Cues leave the action sentences and go into `overall_soundscape` as 7 stage-tagged noun phrases ("At the anticipation, a soft dry rustle."). SX-01 then counts tagged cue sentences in the soundscape. `v4_to_h3.py:160` stops gluing ", with ". | The glue ("with a veil snaps") and the cobras both come from cues inside visual sentences. Rule 50(6) keeps only script-cue hits anyway. | Step 7 cards (not Step 0) |
| D3 | Mouth sentence wording (problem 28) | **One sentence per shot, names from the blocking sheet:** "A speaks with moving lips; B and C keep their lips completely closed." / "A and B keep their lips completely closed." / "A keeps their lips closed." It **replaces** MOUTH_LOCK_SENTENCE (`schema_and_linter.py:117`) and the `_mouth` rule (`v4_to_h3.py:189-190`); it is not added next to them. | Two mouth sentences today, with gender ("his") and a contradiction (rule 34). | S-05 (string constants), step 7 |
| D4 | SFX policy | **Confirm rule 50(6)**: keep only script-cue hits that match `sound_cues` in blocking.json, mute model tones and mumble, beds 22 dB under voice. | Already decided (reverse-engineering §A). Only the wiring is left. | Clip QA / gate_d cards (later) |
| D5 | The -14 LUFS no-duck file (`score/stem_builder.py:503`) | **Confirm it is an audition file, not a deliverable.** Rename the output `*_audition_noduck`. No other code change. | Logs 11-09 17:23 and 17:55. The delivery path reads -16 only from core.json (`build_final_reel.py:231-237`). | Problem 42 card (later) |
| D6 | Watermark tool (problem 24) | **Stay manual, with a recorded command and a refusal when 0 input files are found.** Choose a detector later. | The detector missed 4 of 20 images. Writing a tool now would be speculative. | Problem 24 card (later) |
| D7 | Source-fidelity definition (problem 16) | **Pass = 100 % of blocking cast members and events cite a source line id, and 0 contradictions are flagged by a model that is not the writer.** You spot-check 3 shots. | The writer grades itself today (V7/Q11). | source_check card (later) |
| D8a | Amend blot rule 51: caption_fields replaces CAPTION_FIXES | **Approve.** Spelling-only caption changes become `caption_text` + `caption_diff_approved` per (line, lang). | Rule 51 names CAPTION_FIXES, so code alone cannot retire it. | S-04 wiring (step 6) |
| D8b | Amend rule R28: script size | **Approve "run.py ≤ 7 MB, every upload part ≤ 3 MB".** | R28 says "under 12 MB", but an 11.3 MB script hung (C4, MISTAKES §5 pt 7). | S-08 (default constants) |
| D9 | Per-reel waivers | **`<reel>/waivers.json` signed by you: {reel, codes, owner, date, reason}. Reel 2 starts with none.** | `build_final_reel.py:32` hard-codes reel 1's waiver, which would silently apply to reel 2. | S-17 |
| D10 | Disk minimum for preflight | **`min_free_gb` becomes a required argument, value 5 GB** (the same as the warn level in `tools/README.md:70`). You free D: from ~3 GB to ≥ 5 GB. | The current default of 10 GB fails every run on this PC; lowering it silently would hide the problem. | S-08 |
| D11 | Delivery crop and Ableton mix intake: in code or manual | **In code**, in `build_final_reel --mix <lang>=<wav>`: crop and scale before the ASS burn, length checked against the lock, `rN` naming, never overwrite. | v8b was finished by hand; captions are burned on the wrong aspect in the code path. | Step 11 card |
| D12 | Spend ledger for Kimi (2 USD cap) | **Reuse voice_cast's Ledger** (reserve before the call, append-only). Add a key-check call before each stage. | The OpenRouter key expired unseen once (W4). | Writer wrapper card (later) |
| D13 | Owner-accept record for clip QA | **`clip_qa.json` → `owner_accept: [{shot, code, date, note}]`.** Codes come from clip_gates: TAIL_SNAP, END_MISMATCH, SCENE_CUT, NEW_CLASS, FLICKER. | Your "keep shot 7" decision on 11-09 has no record today. | S-16 |
| D14 | Lock margin | **`margin_frames=0` when the input is `editorial_by_lang.needed_sec`** (it already includes TAIL 0.10 s). The function default stays 6. | Otherwise the margin is counted twice (Opus bug 5). | Lock writer (step 4) |
| D15 | Where keyframe B lands | **New finding:** in our pinned Wan2GP, the end-image position is not a setting. It is `video_length - tail_trim - 1` (`wgp.py:8318`, `tail_trim = discard + auto` at `wgp.py:8262`, H3 sets the flag at `minimax_h3_handler.py:767`). So B lands on the last rendered frame, 24-47 frames after a dynamic cut. **Recommend:** the lock records `end_frame_position = trim_out_frame - 1` now. The step 8 offline trace tests `sliding_window_discard_last_frames = pf - trim_out`. Until that is proven, B is drawn as the pose at the clip end. | Bug 3 assumed a settable `image_end_frame_position`. It is not one. | Step 7/8; S-01 stores the field either way |
| D16 | Accept a beat error of ±½ frame (problem 5) | **Accept ≤ 1000/48 = 20.833 ms.** | This is the physical limit at 24 fps on an absolute grid (no drift). | S-01 (assert) |
| D17 | Shot length limits under H3 handle rules | **Accept.** A middle shot must be 45-258 edit frames (1.875-10.75 s), a first shot ≤ 266, a last shot ≤ 337. The lock raises "split or extend the shot" outside these. `MAX_SHOT_SEC` 15 (`shot_table_spec.py:9`) is not reachable for middle shots. | Derived from `v4_to_h3._plan_handles` (see the hand-checked values below). | S-01 |
| D18 | Coder start time | **Haiku jobs start after the weekly Claude limit resets on 2026-11-12 15:30**, or you name another coder. | Log 11-10 03:16; reverse-engineering §D. | All cards |
| D19 | Blocking.json schema | **Approve the schema in the blocking part of the plan before any sheet-driven card.** | Not needed for Step 0. | Blocking cards (other part) |
| D20 | Housekeeping | Rotate the OpenRouter key. Commit the 61 KB chumpy wheel (recommended: yes, hash-checked). Keep or discard `loop_p0`. | Handoff §7. | Commit step |

## (B) STEP 0 JOB CARDS

Every card gets `checklists/<ID>.md` (rule 55) and needs owner approval before it starts.

Common rules for all cards:
- Edit tool only, no heredocs.
- No reel 1 file is read for writing; fixtures use synthetic data or reel 2 data.
- No network, Colab, ElevenLabs, renderer or paid call; tests inject fakes.
- Run commands from `D:\aai work\anime_studio_merge`.

**Run order:**
- **Wave A (parallel):** S-01, S-03, S-04, S-05, S-06, S-08, S-09, S-10, S-13, S-14, S-15, S-16, S-17.
- **Wave B:** S-02 (after S-01), S-07 (after S-06), S-11 (after S-10). **Wave C:** S-12 (after S-10 and S-11).
- **Shared files:** no two cards edit the same file. S-01 only reads `h3/v4_to_h3.py`. S-09 also edits `tools/secret_scan.py`.

**Problems are only advanced here, not closed.** Under your rule ("a tool nobody calls is not closed"), no problem number closes in Step 0. Each card names the wiring step that closes it. The bug ids listed per card do close, each proven by its named tests.

---

**S-01 | timeline_lock_core**
- **Files:** `director/timeline_lock_core.py`, `director/test_timeline_lock_core.py`
- **Change:**
  1. Lattice range. `lattice_frames(n)` accepts only 6 ≤ n ≤ 20; take the constants from `h3.shot_table_spec` (put the repo root on sys.path the way `pack_validator.py:33` does). Replace the faulty `if min_frames <= 5: return 22` (line 19-20): `fit_lattice` returns `max(107, 17*ceil((m-5)/17)+5)` and raises `ValueError("... > 345 frames: split the shot")` above 345.
  2. Float rounding. Replace `frames = math.ceil(product) + margin_frames` (line 48) with `math.ceil(product - 1e-9) + margin_frames`. `margin_frames` must be an int ≥ 0 (bool refused).
  3. Silent shots. Add a keyword argument `min_seconds=None`. An empty `seconds_by_lang` is allowed only when `min_seconds` is given. `need = max(voice need, ceil(min_seconds*fps - 1e-9))`; the margin applies to voice only.
  4. Beat choice. `choose(need, bpm, start_in_act_frames, snap)`: when `bpm is None or not snap`, return method "free" with frames = need. Otherwise use `beat_candidate` only. **Delete `bar_candidate` and the bar path in `choose` (lines 54-78, 140-157).** Reason: when a shot starts on the grid, the bar cut is one of the beat candidates, so beat gives the same or fewer spare frames. When the start is off the grid (after a free shot), bar inherits that offset, up to half a beat, which breaks D16.
  5. `plan_shots(shots, voice_seconds, margin_frames=6, fps=24)`:
     - Drop the made-up `head_handle`/`tail_handle` (lines 164-165, 195, 205-206).
     - Shot keys: `id`, optional `bpm`, `snap` (default False, as rule 47 says), `cue`, `min_seconds`.
     - The act resets when `(bpm, cue)` differs from the previous shot (replaces line 184).
     - A shot missing from `voice_seconds` without `min_seconds` raises `ValueError(f"{id}: no voice seconds and no min_seconds")` (replaces the KeyError at line 189-190).
     - Pixel plan: new `plan_pixels(ids, edit_frames)`. Lazily import `h3.v4_to_h3 as v`. Build rows `{"id", "episode": 1, "editorial_duration_sec": ed/fps}` and call `v.fit_lattice(rows)`; raise on any problem. Then for each row: `inc, out = v._seam_defaults(i==0, i==last, ed, pf)` and `plan, p = v._plan_handles(sid, pf, ed, inc, out, n)`; raise if `p`. A one-shot list raises (`fit_lattice` skips it at `v4_to_h3.py:325-328`). This leaves one lattice picker (problem 3).
     - Output keys per shot: `id, start_frame, edit_frames, method ("beat"|"free"), beats, error_ms, spare, bpm, snap, cue, act_start_frame, lattice_n, pixel_frames, trim_in_frame, trim_out_frame, head_handle, tail_handle, incoming_seam, outgoing_seam, end_frame_position (= trim_out_frame - 1)`.
- **Tests:**
  - Rewrite every test that asserts 22/39/56/73/90, a bar result, or handle arguments: `test_lattice_frames_valid`, `test_fit_lattice_values`, `test_bar_*`, `test_choose_tie_goes_to_bar`, `test_choose_fewer_spare`, `test_choose_picks_beat_when_fewer_spare_than_bar`, `test_plan_shots_single_free_shot_pixel_73`, `test_plan_shots_tail_handle_changes_pixels`, `test_plan_shots_pixel_frames_lattice`, `test_plan_shots_missing_id_keyerror`.
  - New tests:
    - `test_fit_lattice_clamps_107`: 1→107, 107→107, 108→124
    - `test_fit_lattice_raises_above_345`: 346 raises, 345→345
    - `test_edit_frames_no_float_overshoot`: for n in 1..2000, `edit_frames_for_shot({'en': n/24}, margin_frames=0) == n`
    - `test_margin_negative_refused`
    - `test_min_seconds_silent_shot`: `({}, min_seconds=3.0)` → 72
    - `test_plan_three_free_shots_trims` (see the trims table)
    - `test_middle_shot_too_short_raises`: ed 44
    - `test_middle_shot_max_258`: 258 → pf 311, trims 8/266; 259 raises
    - `test_beat_error_le_half_frame`: the beat-errors table; every `error_ms ≤ 1000/48 + 1e-9`
    - `test_snap_only_groove_shots` (see the snap table)
    - `test_cue_change_resets_act`: two 128-BPM acts with cues c1 and c2; the second act's `act_start_frame` equals its own start
    - `test_end_frame_position_is_trim_out_minus_1`
    - `test_inputs_not_mutated` (kept)
- **Problems:** advances 2, 3, 4, 5, 6, 39 (all close at the step 4 lock writer and step 5 consumers). **Bugs:** O1 (lock side), O2, O3 (data), O4, O6, O7, RE-A12 (snap flag).
- **Depends on:** none. **Shared files:** read-only import of `h3/v4_to_h3.py`; that file is changed later in steps 5 and 7, so re-run this suite then.
- **Acceptance:** `python -m pytest director/test_timeline_lock_core.py -q`
- **Waits on:** D16, D17 (D14 only matters for the step 4 writer).
- **Second-attempt risk:** high (seam and handle logic; quote `_plan_handles` lines 257-299 in the spec and give the trims table).

---

**S-02 | timeline_lock_io**
- **Files:** `director/timeline_lock_io.py`, `director/test_timeline_lock_io.py`
- **Change:**
  1. Paths. `_normalise(p)` becomes `os.path.normcase(os.path.abspath(str(p))).replace("\\","/")`. This fixes the false stale where "./x" and "D:/x" differ (Opus §1 E7).
  2. Params in the hash. `write_lock(path, shots, inputs, params, fps=24)`:
     - `params` is a required dict and is stored.
     - Hash = sha256(`input_sha256(inputs)` + `json.dumps(params, sort_keys=True, ensure_ascii=False)`).
     - Schema `"version": 2`; empty `inputs` is refused.
     - **Never overwrite:** raise `FileExistsError` if the target exists.
  3. `load_lock` accepts version 2 only and checks:
     - no duplicate ids
     - `total_seconds == round(total_frames/fps, 6)`
     - `start_frame` values are cumulative
     - every shot: `107 ≤ pixel_frames ≤ 345` and `(pf-5) % 17 == 0`; `0 ≤ trim_in < trim_out ≤ pf`; `trim_out - trim_in == edit_frames`; `end_frame_position == trim_out - 1`; `error_ms ≤ 1000/(2*fps) + 1e-9`
  4. `verify_lock(path, inputs, params)` recomputes the combined hash; a params change raises `StaleLockError`.
  5. Versioning (RE-B12):
     - `next_lock_path(folder)` returns `timeline_lock_v{N+1}.json`, where N is the highest match of `^timeline_lock_v(\d+)\.json$` (0 if none).
     - `latest_lock_path(folder)` returns the highest, or raises FileNotFoundError.
     - `diff_locks(old, new)` returns `[{"id", "field", "old", "new"}]` for edit_frames, start_frame, bpm, snap, cue, plus added and removed ids.
  6. `lock_rows(lock)` returns `[(id, start_frame, edit_frames)]`: the one integer clock for build_final_reel, render_controller and cue_sheet (RE-B6).
- **Tests:**
  - `test_dot_path_equals_abs_path`: write with "./a.wav", verify with the absolute path → ok
  - `test_params_change_is_stale`: margin 6→0 → StaleLockError
  - `test_wav_byte_change_is_stale` (problem 7 proof)
  - `test_refuses_overwrite`
  - `test_next_lock_path`: empty → v1; v1, v2 present → v3; "timeline_lock_v2.json.tmp" ignored
  - `test_diff_locks_reports_shot`: S2 edit 102→110 also reports S3 start 248→256
  - `test_load_rejects_pf_22`, `test_load_rejects_trim_mismatch`, `test_load_rejects_duplicate_id`, `test_load_rejects_total_seconds_mismatch`
  - `test_lock_rows_integer_offsets`: (0, 144), (144, 144), (288, 144)
- **Problems:** advances 1, 7, 8, 39 (close when render_controller, run_colab_batch and cue_sheet call `verify_lock`). **Bugs:** O8, E7, RE-B12.
- **Depends on:** S-01 (field names). **Shared files:** none.
- **Acceptance:** `python -m pytest director/test_timeline_lock_io.py -q`
- **Waits on:** none.
- **Second-attempt risk:** medium.

---

**S-03 | wav_contract**
- **Files:** `director/wav_contract.py`, `director/test_wav_contract.py`
- **Change:**
  - `wav_name(line_id, lang)` (renamed parameter; the docstring says the id is a line id such as "SHOT-001-N", as Opus §1 W-B says) refuses:
    - Windows reserved stems: the part before the first "." casefolded in {con, prn, aux, nul, com1-9, lpt1-9}
    - a trailing "." or space
    - any character with code < 32
  - The existing path-like refusals stay.
- **Tests:**
  - `test_reserved_names_refused`: "CON", "nul", "Com1", "lpt9.x" raise
  - `test_line_id_ok`: "SHOT-001-N", "hi" → "SHOT-001-N.hi.wav"
  - `test_trailing_dot_space_refused`
  - `test_control_char_refused`: "a\x01"
- **Problems:** advances 12, 13 (close at step 3, voice_cast export). **Bugs:** E8 (wav).
- **Depends on:** none. **Shared files:** none.
- **Acceptance:** `python -m pytest director/test_wav_contract.py -q`
- **Waits on:** none.
- **Second-attempt risk:** low.

---

**S-04 | caption_fields**
- **Files:** `director/caption_fields.py`, `director/test_caption_fields.py`
- **Change:**
  - New `manifest_lines(rows, overrides=None)`:
    - `rows` are accepted manifest rows `{line, lang, text}`, the text after `voices.prep_text` (`voice_cast.py:103, 107-108, 208`). The coder reads `voice_cast.py:199-241` for the exact container.
    - `spoken_text` is `row["text"]`, never shots.json.
    - `overrides` maps `(line, lang)` to `{caption_text, caption_diff_approved}`.
    - An override for an unknown `(line, lang)` raises `CaptionError("unknown line ...")`.
    - Duplicate `(line, lang)` rows with different text raise.
    - Returns dicts that `caption_lines()` accepts (`id` = line, `lang`).
  - No other behaviour changes.
- **Tests:**
  - `test_spoken_text_is_manifest_text`: row text "ब्रह्मा उठे" and a different shots-style text → `spoken_text == "ब्रह्मा उठे"`
  - `test_unapproved_override_raises`
  - `test_approved_same_wordcount_used`
  - `test_unknown_override_raises`
  - `test_duplicate_row_conflict_raises`
- **Problems:** advances 14 (closes at step 6: delete `build_final_reel.py:95, 168-170`). **Bugs:** O14.
- **Depends on:** none. **Shared files:** none.
- **Acceptance:** `python -m pytest director/test_caption_fields.py -q`
- **Waits on:** D8a (for wiring only; the card can run).
- **Second-attempt risk:** low.

---

**S-05 | prompt_hygiene**
- **Files:** `h3/prompt_hygiene.py`, `h3/tests/test_prompt_hygiene.py`
- **Change:**
  1. Replace `return f"While {join_names(on_screen)} keep their lips completely closed."` (line 169) with `f"{join_names(on_screen)} keep their lips completely closed."`. Final wording per D3.
  2. Mouth and cast go into the body line, not after the music line (Opus 10b). `clean_prompt` puts them at the end of the line that starts with `integrated_multimodal_description: ` or `detailed_description: `, and raises `PromptError("no body line")` if there is none. The last line stays `non_diegetic_music: ...`.
  3. Exactly one mouth sentence (Opus 10d). Before inserting, remove `MOUTH_LOCK_SENTENCE` (import it from `h3.schema_and_linter`; no import cycle) and any sentence matching `(?i)\bmouth stays (closed|shut)\b`.
  4. `check_sound_cue`: a visible entry also counts for its plural/singular form (noun or noun+"s").
  5. Blank lines stay collapsed (problem 30, Wan2GP rule 30(2)). The docstring says this output passes the linter only after step 7 changes `schema_and_linter.py:79` to a single "\n". The docstring also says: do not wire before `v4_to_h3.py:160` is fixed (Opus 10f).
- **Tests:**
  - `test_mouth_no_while`: `(["Kama","Rati"], [])` → "Kama and Rati keep their lips completely closed."
  - `test_clean_prompt_keeps_section_order`: 5-line FL2VA fixture (header, blank, imd, soundscape, music) → 4 lines; line 2 ends with mouth + cast; last line starts "non_diegetic_music:"
  - `test_single_mouth_sentence`: input containing MOUTH_LOCK_SENTENCE → it is gone, and "lips" appears exactly once
  - `test_no_blank_line_in_output`
  - `test_visible_plural_ok`: cue "serpents hiss", visible ["serpent"] → no raise
- **Problems:** advances 26, 27, 28, 30 (close at step 7). **Bugs:** O10a/b/d/e (10c → D2; 10f → step 7).
- **Depends on:** none. **Shared files:** none (imports the linter only).
- **Acceptance:** `python -m pytest h3/tests/test_prompt_hygiene.py -q`
- **Waits on:** D3.
- **Second-attempt risk:** medium.

---

**S-06 | shot_router**
- **Files:** `director/shot_router.py`, `director/test_shot_router.py`
- **Change:**
  - New rows in `_ROUTE_TABLE`:
    - `"SE"`: image_prompt_type "SE", keyframes [A, B], strength None, gpu True, est_units 1.2, requires_owner_flag False
    - `"REF_SE"`: image_prompt_type "SE", keyframes [A, B, refs], est_units 1.4
  - Every row gets `"h3_mode"`: S → "I2VA", REF_S → "Ref2VA", REF_SE → "Ref2VA" (D1b), SE/SOFT_SE/KFI → "FL2VA", POST → None.
  - `route_shot(features, allow_s=False)`: the final `else: route = "S"` (line 121) becomes SE when `allow_s` is False; REF_S becomes REF_SE; both append the reason "S not approved: SE fallback".
  - "more than 3 moving people" is added only when `cast_count > 3` (cosmetic, F).
  - `plan_reel(shots, allow_s=False)`: a non-dict shot or a missing id/features raises `RouterError(f"shot #{i}: ...")` instead of KeyError (lines 137, 141).
  - `ROUTES` gets the new names.
- **Tests:**
  - `test_plain_shot_routes_se`
  - `test_allow_s_true_routes_s`
  - `test_close_up_ref_se_ref2va`
  - `test_missing_features_router_error`
  - `test_every_gpu_route_has_workflow`: with `allow_s=False`, every GPU route has h3_mode in {"FL2VA", "Ref2VA"}, and `needs_owner_flag == []`
  - `test_crowd_reason_only_if_over_3`
- **Problems:** enabler for 20, 21, 25. **Bugs:** E1 (router half), E6, O9 (router), H7-J14.
- **Depends on:** none. **Shared files:** none.
- **Acceptance:** `python -m pytest director/test_shot_router.py -q`
- **Waits on:** D1, D1b.
- **Second-attempt risk:** low.

---

**S-07 | shot_mode**
- **Files:** `h3/shot_mode.py`, `h3/tests/test_shot_mode.py`
- **Change:**
  1. `check_pixel_frames` requires `LATTICE_N_MIN ≤ n ≤ LATTICE_N_MAX`, importing them from `h3.shot_table_spec`. This replaces `if n < 1` (lines 47-51); 22 now fails.
  2. `image_prompt_type`: a `None` mode raises `ShotModeError("POST shots never reach the batch")`.
  3. `frame_row` copies `route`, `input_video_strength` (None, or a float with 0 < x ≤ 1, else error) and `end_frame_position` (an int with 0 < efp < pixel_frames, required for SE).
  4. For route KFI, `mid` and `mid_frame` (0 < mid_frame < efp) are required, else an error.
- **Tests:**
  - `test_pf_22_refused`, `test_pf_107_and_345_ok`, `test_pf_362_refused`
  - `test_post_none_refused`
  - `test_soft_se_keeps_strength_and_end_position`: 0.6 and 151 survive
  - `test_kfi_without_mid_raises`
  - `test_router_rows_accepted`: for every `shot_router` route with `allow_s=False`, a shot built from the route (pf 192, efp 151) is accepted by `frame_row`; POST raises
  - Rewrite the existing tests that accept 22 or 39
- **Problems:** advances 3 (closes at step 8, build_h3_batch). **Bugs:** E1 (shot_mode half), O1 (shot_mode), O9 (shot_mode), O3 (carries the field).
- **Depends on:** S-06. **Shared files:** none.
- **Acceptance:** `python -m pytest h3/tests/test_shot_mode.py -q`
- **Waits on:** D1, D15 (field meaning).
- **Second-attempt risk:** low.

---

**S-08 | runner_safety**
- **Files:** `director/runner_safety.py`, `director/test_runner_safety.py`
- **Change:**
  1. `preflight(urls, disk_path, *, min_free_gb, script_path, max_script_mb=7.0, part_paths=(), max_part_mb=3.0, ...)`. `min_free_gb` and `script_path` have no default. Empty `urls` raises `ValueError`. Each part path ≤ 3 MB.
  2. A HEAD that returns 405 or 501 is retried as a GET with `Range: bytes=0-0`; 200 or 206 is ok (E8).
  3. `clip_verified(results_dir, shot_id, expected_frames, probe_frames=None, exists=None, size=None)`:
     - Skips `*.part.mp4` and `*.tmp.mp4`.
     - Requires `probe_frames(entry) == expected_frames`. The default probe is a 4-line ffprobe `nb_read_frames` call, the same as `build_final_reel.py:35-38`.
     - The injected path also runs the folder-containment check (E3).
  4. `can_stop` and `stop_decision` take `expected_frames: dict[id, int]`; a missing id raises.
- **Tests:**
  - `test_11_3mb_script_fails` (11.3 MB > 7.0)
  - `test_part_over_3mb_fails`
  - `test_script_path_required`
  - `test_empty_urls_refused`
  - `test_head_405_get_206_ok`
  - `test_wrong_frame_count_not_verified`: probe 100 vs 192
  - `test_part_file_ignored`
  - `test_injected_escape_refused`
  - Update the existing tests for the new signature
- **Problems:** advances 29, 31, 32, 33, 45 (close at step 9, run_colab_batch). **Bugs:** O11, E3, E8 (HEAD).
- **Depends on:** none. **Shared files:** none.
- **Acceptance:** `python -m pytest director/test_runner_safety.py -q`
- **Waits on:** D8b, D10.
- **Second-attempt risk:** low. Run a hostile-probe review (rule 54(7)).

---

**S-09 | precommit_check (+ secret_scan rule)**
- **Files:** `tools/precommit_check.py`, `tools/test_precommit_check.py`, `tools/secret_scan.py`, `tools/test_secret_scan.py`
- **Change:**
  1. `secret_scan.RULES` gets `("K-ELEVEN", "ElevenLabs key", re.compile(r"\bsk_[0-9a-f]{40,}\b"), None)`. The hex-only body avoids Stripe's `sk_live_`. Anthropic `sk-ant-...` is already caught by K-OPENAI (`secret_scan.py:41`).
  2. `precommit_check` deletes its own `SECRET_PATTERNS` (lines 11-16). `scan_secrets` uses `secret_scan.content_findings` and emits `"<name>:<line>: <rule>"`. One pattern list, so Google and GitHub tokens are covered.
  3. Staged mode (no argv) reads the blob with `git show :<path>`, not the working file (line 60).
  4. Files whose suffix is in `secret_scan.BLOCKED_EXT` skip content checks instead of failing "not UTF-8" (line 71).
  5. `_CONTROL_CHAR_RE` adds `\x7f`; `check_python` catches `(SyntaxError, ValueError)`.
- **Tests (build fake keys by concatenation):**
  - `test_eleven_key_found`: "sk_" + "0"*48
  - `test_anthropic_key_found`
  - `test_github_token_found`
  - `test_png_skipped`
  - `test_del_flagged`: U+007F
  - `test_nul_flagged`: U+0000 in a .py file
  - `test_staged_blob_read`: monkeypatch `subprocess.run`; the blob has a key, the working file is clean → finding
- **Problems:** advances 44, 46 (close at step 10, hook install). **Bugs:** O12, E4.
- **Depends on:** none. **Shared files:** `tools/secret_scan.py` is used only by this card.
- **Acceptance:** `python -m pytest tools/test_precommit_check.py tools/test_secret_scan.py -q`
- **Waits on:** none.
- **Second-attempt risk:** low.

---

**S-10 | script_hook**
- **Files:** `director/script_hook.py`, `director/test_script_hook.py`
- **Change:**
  1. Public `validate_shots(shots)` extends `_validate_shots`:
     - every event is a dict with a finite numeric `t ≥ 0`
     - every line is a dict with finite `start_s ≤ end_s` and a str `text`
     - otherwise `ValueError` naming the shot id
     - remove the defaults `event.get("t", 0.0)` (line 225) and `lines[0].get("start_s", 0.0)` (line 238)
  2. A first shot with no spoken line becomes a hard fail: "H2: no spoken line in the first shot", -40 (E2).
  3. `_is_opener` matches whole tokens with `_phrase_matches` on `_tokens(line)` at position 0, instead of `lowered.startswith` (line 170).
- **Tests:**
  - `test_no_first_line_hard_fail`
  - `test_event_without_t_raises`
  - `test_non_dict_event_raises`
  - `test_it_was_a_timeline_not_opener`
  - `test_once_upon_a_time_is_opener`
  - Update the tests that relied on defaults
- **Problems:** advances 15 (closes with the writer gate in step 5). **Bugs:** E2 (hook), H7-J9a.
- **Depends on:** none. **Shared files:** none.
- **Acceptance:** `python -m pytest director/test_script_hook.py -q`
- **Waits on:** none.
- **Second-attempt risk:** low.

---

**S-11 | script_pacing**
- **Files:** `director/script_pacing.py`, `director/test_script_pacing.py`
- **Change:**
  - Call `script_hook.validate_shots` (replaces lines 12-17).
  - The return value becomes `{"pass", "problems", "warnings"}`; P4 length (lines 86-88) moves to `warnings`, as documented ("not a hard fail").
  - New argument `seconds_override: dict[id, float] | None`, used for the total, P2 and P3 (re-run on lock seconds, O18).
- **Tests:**
  - `test_58s_reel_passes_with_warning`: 1 warning
  - `test_seconds_override_changes_total`: 70 → 58 adds a warning
  - `test_nested_missing_start_s_raises`
- **Problems:** advances 15. **Bugs:** E2 (pacing), O18 (pacing part).
- **Depends on:** S-10. **Shared files:** none.
- **Acceptance:** `python -m pytest director/test_script_pacing.py -q`
- **Waits on:** none.
- **Second-attempt risk:** low.

---

**S-12 | script_inspect (+ from_pack)**
- **Files:** `director/script_inspect.py`, `director/test_script_inspect.py`
- **Change:**
  1. Insert this module's folder into sys.path at the top, so `import script_hook` and `import script_pacing` (lines 22-23) work from the repo root (O18).
  2. New `from_pack(rows, lang)`:
     - `id` = row["id"]
     - `seconds` = `editorial_duration_sec`
     - `events` = `[{"t": float(d["t0"])}]` for each `per_second_directives` entry with a non-empty `action_pose_expression`
     - `action` = the action text of the first directive
     - `lines` = `narration_by_lang[lang]` plus `dialogue_by_lang[lang]` items; `time_range` parsed with a lazy `from pack_validator import _range` (list or "1.2-1.6s" form); sorted by start
     - A missing or bad range raises `ValueError` naming the row.
  3. `main`:
     - rows that contain `audio_and_dialogue_track` are passed through `from_pack` automatically
     - `--lock <file>` passes `seconds_override = edit_frames/fps` via `timeline_lock_io.load_lock`
     - a `ValueError` prints "invalid input: <msg>" and returns 2, instead of a traceback (E2)
- **Tests:**
  - `test_from_pack_runs_inspect`: 2 synthetic reel-2 rows, no KeyError
  - `test_pack_line_at_0_7_fails_h2`: "0.7-2.0s"
  - `test_bad_schema_exit_2_no_traceback`: subprocess
  - `test_runs_from_repo_root`: subprocess, `cwd` = repo root, `python director/script_inspect.py fixture.json en` → exit 0 or 1
- **Problems:** advances 15 (closes at the step 5 writer gate). **Bugs:** E2 (inspect), O18, RE-B14.
- **Depends on:** S-10, S-11 (and S-02 for `--lock`; that test can stub `load_lock`). **Shared files:** none.
- **Acceptance:** `python -m pytest director/test_script_inspect.py -q`
- **Waits on:** none.
- **Second-attempt risk:** medium.

---

**S-13 | audio_edge**
- **Files:** `director/audio_edge.py`, `director/test_audio_edge.py`
- **Change:**
  1. Replace `idx = [i for i, v in enumerate(x) if v != 0.0]` (line 190) with a fixed gate: `apply_edges(..., noise_floor_db=-50.0)`, `gate = 10**(db/20)` (0.0031623). first/last = the first/last index with `abs(v) ≥ gate`; none → `ValueError`. Padding zeros cannot move a fixed gate, so the length is idempotent.
  2. Replace the fade conditions `abs(y[f]) > 0.02` and `abs(y[l]) > 0.02` (lines 209, 213): with `thr = voiced_threshold(y, sr)`, fade in when `rms(y[f:f+n_in]) ≥ thr` and fade out when `rms(y[l-n_out+1:l+1]) ≥ thr`.
  3. New `write_wav_mono(path, samples, sr)`: 16-bit PCM, `round(v*32767)` clamped, temp file then `os.replace`.
  4. New `fix_wav(src, dst)` returns `{pad_front_ms, pad_back_ms, faded_in, faded_out, seconds_before, seconds_after}` and refuses `dst == src`.
  5. The docstring says it runs in voice_cast export BEFORE the lock measures (O13).
- **Tests:**
  - `test_noise_floor_no_extra_pad`: 44.1 kHz, 0.001 noise for 200 ms then a 0.8 tone → length unchanged (the old code added 3528 samples = ceil(0.08×44100))
  - `test_loud_onset_on_quiet_sample_faded`: 440 Hz sine, phase 0 → `y[f] == 0.0` and the first 12 ms rms drops
  - `test_second_call_same_length`
  - `test_write_read_roundtrip`: max error ≤ 1/32767
  - `test_fix_wav_refuses_same_path`
  - Correct the stale "FAIL-until-fixed" comments (G)
- **Problems:** advances 13 (closes at step 3, export). **Bugs:** O13, H7-J10.
- **Depends on:** none. **Shared files:** none.
- **Acceptance:** `python -m pytest director/test_audio_edge.py -q`
- **Waits on:** none.
- **Second-attempt risk:** medium.

---

**S-14 | image_gates**
- **Files:** `director/image_gates.py`, `director/test_image_gates.py`
- **Change:**
  1. `to_float01` accepts **uint8 only**; floats raise `GateError("convert to uint8 0..255 first")`. This replaces line 18-19 (E8: a float 0..1 image was divided by 255 again, so any two float images passed). `plate_composite.load_rgb` already returns uint8. Delete `test_to_float01_float_0_255_scales`.
  2. `background_lock(..., min_area_fraction=0.25)`: when `area_fraction < min`, `pass` is False with a reason. Add a `"reasons"` list. A non-finite ssim gives pass False.
  3. `dilate` clamps px to `max(mask.shape)` (H7-J11).
  4. `cast_parity` and `limb_parity` refuse bool and non-int inputs.
  5. The docstring marks 0.97 and 3/255 as uncalibrated knobs to tune on reel 2 B frames (O16).
- **Tests:**
  - `test_float_image_refused`
  - `test_small_area_fails`: 64×64 frame, comparable area 64/4096 = 0.015625 → pass False
  - `test_huge_dilate_fast`: px 10**6 on 16×16 with one True pixel → all True, under 1 s
  - `test_bool_count_refused`
- **Problems:** advances 20, 21, 25 (close at step 8, keyframe approval). **Bugs:** E8 (image), O16, H7-J11.
- **Depends on:** none. **Shared files:** none.
- **Acceptance:** `python -m pytest director/test_image_gates.py -q`
- **Waits on:** none.
- **Second-attempt risk:** low.

---

**S-15 | plate_composite**
- **Files:** `director/plate_composite.py`, `director/test_plate_composite.py`
- **Change:**
  - `_dilate_square` (lines 78-91) calls `image_gates.dilate(mask, px)` (the same Chebyshev square).
  - `_box_blur` (lines 193-203) is rewritten with an integral image (`np.cumsum`, edge padding).
  - `plan(..., max_hole_fraction=0.02)` passes the value through.
  - `hole_fraction` refuses non-ndarray input.
  - `_label_components` is kept, with the comment `# ponytail: python loop, O(HW); swap for scipy.ndimage.label if 768x1344 is slow`.
- **Tests:**
  - `test_dilate_matches_reference`: the old loop copied into the test; equal on 20 random 32×32 masks
  - `test_blur_matches_reference`: max abs difference < 1e-9
  - `test_full_frame_speed`: 1344×768, dilate 6 + blur 4 under 2 s
  - Correct the stale comments
- **Problems:** advances 20. **Bugs:** E8 (plate perf).
- **Depends on:** none (imports image_gates; its `dilate` interface does not change). **Shared files:** none.
- **Acceptance:** `python -m pytest director/test_plate_composite.py -q`
- **Waits on:** none.
- **Second-attempt risk:** low.

---

**S-16 | clip_gates**
- **Files:** `director/clip_gates.py`, `director/test_clip_gates.py`
- **Change:**
  1. `tail_spike(flow_p95, window=None, ...)`: `window = (trim_in, trim_out)` from the lock (exclusive end); analyse `flow_p95[trim_in:trim_out]`; `first_spike_index` is in clip-frame numbers; a window outside the clip raises (O15).
  2. `best_cut_frame`: a non-finite value raises (E5).
  3. `new_object_classes(counts, after_frame=12, known=())`: `after_frame` must be an int ≥ 0, else raise; `known` (classes from the blocking sheet) seeds the known set.
  4. `flicker_score` is vectorised: the mean of `|f[t+1] - 2f[t] + f[t-1]|` over the unmasked pixels.
  5. `verdict(results, owner_accept=())`:
     - keys `tail, end, cuts, new_classes, flicker, flicker_limit` are required; missing ones raise `ClipGateError` naming them
     - `end["pass"]` must be a bool (replaces `end.get("pass", True)` at line 135)
     - reasons become `{code, text}` with codes TAIL_SNAP, END_MISMATCH, SCENE_CUT, NEW_CLASS, FLICKER
     - each `owner_accept` entry `{code, date, note}` moves its code to `accepted`
     - return `{"pass", "reasons", "accepted"}`
- **Tests:**
  - `test_verdict_empty_raises`
  - `test_flicker_without_limit_raises`
  - `test_best_cut_nan_raises`
  - `test_after_frame_negative_raises`
  - `test_known_class_not_new`: "sage" in `known`, seen at frame 20
  - `test_tail_window_ignores_handle`: 200 frames of 1.0 with 5.0 at frame 180; window (8, 152) → flag False; window (0, 200) → True at 180
  - `test_owner_accept_new_class`
  - `test_flicker_vector_equals_loop`
- **Problems:** advances 37 (closes at step 10, clip_qa.py). **Bugs:** E5, O15.
- **Depends on:** none. **Shared files:** none.
- **Acceptance:** `python -m pytest director/test_clip_gates.py -q`
- **Waits on:** D13.
- **Second-attempt risk:** medium.

---

**S-17 | waivers (NEW)**
- **Files:** NEW `director/waivers.py`, NEW `director/test_waivers.py`
- **Change:**
  - `load_waivers(path, reel)` returns a `frozenset` of codes. File format: `{reel, codes, owner, date, reason}`.
  - A missing file gives `frozenset()` (everything blocks).
  - A reel mismatch, an empty owner, a date that is not `YYYY-MM-DD`, an unknown key, or a code not matching `^[A-Z_]+$` raises `ValueError`.
  - Wiring is in step 6: `build_final_reel.py:32` `WAIVED` is replaced by `load_waivers`, and the test that reel 2 with no file blocks on DEAD_AIR_PAUSE lands there.
- **Tests:** `test_missing_file_empty`, `test_reel_mismatch_raises`, `test_good_file_codes`, `test_bad_code_raises`
- **Problems:** none by number (RE-C). **Bugs:** RE-C waivers.
- **Depends on:** none. **Shared files:** none.
- **Acceptance:** `python -m pytest director/test_waivers.py -q`
- **Waits on:** D9.
- **Second-attempt risk:** low.

---

**Step 0 gate after all cards:**
```
python -m pytest director/test_timeline_lock_core.py director/test_timeline_lock_io.py director/test_wav_contract.py director/test_caption_fields.py director/test_shot_router.py director/test_runner_safety.py director/test_script_hook.py director/test_script_pacing.py director/test_script_inspect.py director/test_audio_edge.py director/test_image_gates.py director/test_plate_composite.py director/test_clip_gates.py director/test_waivers.py h3/tests/test_prompt_hygiene.py h3/tests/test_shot_mode.py tools/test_precommit_check.py tools/test_secret_scan.py -q
```
Then run `python -m pytest h3/tests -q` (S-01 imports v4_to_h3, and S-05/S-07 sit in h3).

**Not in Step 0 (these are not in the 16 modules):**
- O17 build_final_reel → step 6
- O9 compile I2VA workflow → step 7
- O10c → D2
- O5 lock input = `needed_sec` → step 4 writer
- O2 consumer half (v4_to_h3 reading the lock) → step 5

## Hand-checked values for the lock tests

**Lattice (pixel_frames = 17n + 5, n = 6..20):** 107, 124, 141, 158, 175, 192, 209, 226, 243, 260, 277, 294, 311, 328, 345. `fit_lattice`: 1→107, 107→107, 108→124, 176→192, 345→345, 346 → ValueError.

**Trims and end_frame_position.** Stage-6 span: a6 = round(5·pf/7), b6 = round(6·pf/7) − 1. trim_out is exclusive; end_frame_position = trim_out − 1.

| Case | ed | n / pf | seams | a6..b6 | trim_in | trim_out | head / tail | end_frame_position |
|---|---|---|---|---|---|---|---|---|
| first shot | 144 | 10 / 175 | INTER / DYN | 125..149 | 0 | 144 | 0 / 31 | 143 |
| middle shot | 144 | 11 / 192 | DYN / DYN | 137..164 | 8 | 152 | 8 / 40 | 151 |
| last shot | 144 | 9 / 158 | DYN / INTER | — | 14 | 158 | 14 / 0 | 157 |
| short middle | 60 | 6 / 107 | DYN / DYN | 76..91 | 23 | 83 | 23 / 24 | 82 |
| max middle | 258 | 18 / 311 | DYN / DYN | 222..266 | 8 | 266 | 8 / 45 | 265 |
| too short middle | 44 | — | — | — | raises | | | |
| too long middle | 259 | — | — | — | raises | | | |

How these were derived:
- Middle 144: n = 9 and n = 10 fail because the handle sum H = 14 and 31 is below 32. At n = 11, H = 48; the allowed tails are 28..40; the cut point nearest the middle of the span (150.5) is trim_out 152 (tail 40, head 8).
- Middle 60: within `LATTICE_CUT_BOUNDS[6]` (ed 45..75, H 32..62).
- Max middle 258: at n = 19, b6 = 280 and pf − b6 = 48 > 47, so no tail fits. At n = 18, ed must be 229..258.
- First shot at n = 9: tail = 14 < 24, so it fails.

Three-shot free fixture (voice 5.75 s, margin 6 → need 138 + 6 = 144): start_frame 0 / 144 / 288, total_frames 432, total_seconds 18.0.

**Beat errors.** One beat at 128 BPM = 11.25 frames; at 176 BPM = 90/11 ≈ 8.1818 frames. Python round() rounds halves to even.

| Case | need | start | result | error |
|---|---|---|---|---|
| 128 BPM, snap, act start 0 | 144 | 0 | k = 13, 146.25 → 146 frames | 0.25 frame = 10.4167 ms |
| next shot in the same act | 100 | 146 | target ≥ 246; k = 22, 247.5 → 248; frames = 102 | 0.5 frame = 20.8333 ms (the limit) |
| 176 BPM | 90 | 0 | k = 11, exactly 90 frames | 0 |
| 176 BPM | 91 | 0 | k = 12, 98.18 → 98 frames | 0.1818 frame = 7.5758 ms |
| 60 BPM, snap False (rule 47) | 100 | — | free, 100 frames | 0 |

Assert: every error_ms ≤ 1000/48 + 1e-9 = 20.8333 ms. At 176 BPM the worst case is 5/11 frame = 18.94 ms.

**Snap fixture (rule 47):**

| Shot | Act | snap | need | edit_frames | start_frame |
|---|---|---|---|---|---|
| g1 | 128 BPM | True | 144 | 146 | 0 |
| g2 | 128 BPM | True | 100 | 102 | 146 |
| last of act | 128 BPM | False | 50 | 50 (bpm 128 still recorded) | 248 |
| first of 60 BPM act | 60 BPM | False | 100 | 100 (act_start_frame 298) | 298 |

**Float check:** for n in 1..2000, `edit_frames_for_shot({"en": n/24}, margin_frames=0) == n`. **Silent shot:** `min_seconds` 3.0 → 72 frames.

Sources (ElevenLabs key format; there is no official length spec, so the rule uses a hex-only body of 40 or more characters to avoid Stripe's `sk_live_` prefix):
- [GitGuardian ElevenLabs detector](https://docs.gitguardian.com/secrets-detection/secrets-detection-engine/detectors/specifics/elevenlabs_api_key)
- [Semgrep on prefixed secrets](https://semgrep.dev/blog/2025/secrets-story-and-prefixed-secrets)
- [ElevenLabs key tester](https://trevorfox.com/api-key-tester/elevenlabs/)
- [ElevenLabs API keys docs](https://elevenlabs.io/docs/overview/administration/workspaces/api-keys)
