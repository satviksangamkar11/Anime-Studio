# P3: job cards X-01 … X-24

**COMMON (copy into every X card's rule-55 checklist)**
- Repo `D:\aai work\anime_studio_merge`, branch `merge-v4-universal-2026-11-07`. Python `C:/Python314/python.exe`. Tests go next to the module (`director/test_*.py`, `h3/tests/`, `score/tests/`, `tools/test_*.py`).
- Fixtures are reel 2 text or synthetic data only. Never read, write or reference reel 1 files: `kalika_puran_bhag1`, `final_reel1_*`, `pack_opus_high_20261108_v4_deva` (rules 53(1), 54(11)).
- No Colab, ElevenLabs, renderer, Opus/Claude model call, OpenRouter or other paid call. Inject every external call as a function parameter and fake it in tests. Local `ffmpeg`/`ffprobe` on synthetic `lavfi` sources is allowed.
- Edit code with the Edit tool. No heredoc edits of code that has backslashes (rules 20, 30(6)). Add no new dependency (stdlib + numpy, which is already used by image_gates and plate_composite). jsonschema is not installed; validate in plain Python.
- Every job waits for the owner's go (rule 55(5) and the owner's 11-11 06:19 order). The supervisor shows the filled checklist before asking for the next go.
- Dependencies on other parts are named by file + function:
  - **D-LOCK**: lock writer (timeline_lock_core.plan_shots + lock CLI + timeline_lock_io params). Each lock shot carries `id, start_frame, edit_frames, pixel_frames, trim_in_frame, trim_out_frame, end_frame_position, bpm, snap, act`, and the inputs include every `<line>.<lang>.wav` plus shots.json and eleven_manifest.json.
  - **D-ROUTER**: shot_router bug 9: SE row, `route_shot(features, allow_s=False)`, KeyError becomes RouterError.
  - **D-IMG**: image_gates fixes: float images not divided by 255 twice (image_gates.py:18-19), `min_area_fraction`.
  - **D-CLIP**: clip_gates fixes: `verdict` requires every key, `tail_spike` takes a window, best_cut NaN.
  - **D-INSPECT**: `script_inspect.from_pack`.
  - **D-PROMPT**: v4_to_h3.py:160 glue removal + compile_h3_sing8/schema_and_linter format job (single `\n`, SX-01 decision).
  - **D-J8**: port of build_h3_batch.py / run_colab_batch.py.
  - **D-VOICE**: voice_cast export without atempo; manifest rows `{id:"<line>.<lang>", text, text_sha256}` (voice_cast.py:107-108).

---

## A. Blocking sheet (single source of truth)

**X-01 | blocking schema + loader**
- **Files:** `director/blocking.py` NEW; `director/test_blocking.py` NEW.
- **Change:**
  - Add `SCHEMA = "blocking/1"`, one file per shot at `<pack>/blocking/<SHOT-ID>.json`.
  - Required keys:
    - `shot_id` (`^SHOT-\d{3}$`), `plate_id` (`^PLATE-[A-Za-z0-9_-]+$`), `location_id`.
    - `kind`, one of `acting, body_action, camera_move, crowd, close_up, seam` (the same tuple as shot_router.py:11; import it, do not copy it).
    - `camera {mode: fixed|move, framing: wide|medium|close|extreme_close, move: null|str}`.
    - `light {key_dir: left|right|top|back|front, palette_id: str}`.
    - `props [{id, class, x, y, visible: [A|B]}]`.
    - `entries [{char, side: left|right|top|bottom}]`, `exits [...]`.
    - `sound_cues [{t: sec, text}]`: sounds only, as noun phrases.
    - `arc_sec >= 0`.
    - `writer_seconds > 0`.
    - `cut_to_next: match|cut`.
    - `source_refs [str]`.
    - `cast [{id, name, speaks: bool, arms: int >= 2, source_refs: [str], start: P, end: P}]`.
    - P = `{x, y, scale, facing: left|right|camera|away, pose: standing|seated|kneeling|lying|walking|flying, mouth_moves: bool}`. x and y are feet position as a fraction of the frame (−0.5..1.5, so off-frame entries are allowed). scale is figure height as a fraction of the frame (0.05..1.2).
  - Functions:
    - `validate(sheet) -> list[str]`: never raises; each problem is `"<shot_id>: BLK-S<nn> <text>"`.
    - `load_sheet(path) -> dict`: raises `BlockingError` (a ValueError subclass) with the problem list; refuses a `shot_id` that differs from the file name.
    - `load_reel(dir, shot_ids) -> {id: sheet}`: a missing file raises.
    - `distance(c) -> float = hypot((ex-sx)*9/16, ey-sy) + abs(escale-sscale)`, in frame heights (9:16 frame).
    - `is_moving(c)`: distance > 0.02, or pose/facing differs.
- **Tests:**
  - `test_valid_sheet_has_no_problems`
  - `test_missing_plate_id_reported` (BLK-S code)
  - `test_bad_pose_value_reported`
  - `test_file_name_id_mismatch_raises`
  - `test_distance_hand_checked`: (0.20,0.80,0.50) → (0.60,0.80,0.50) gives 0.4×9/16 = **0.225**.
  - `test_is_moving_pose_only` (seated→standing, distance 0 → True)
  - `test_validate_never_raises_on_garbage` (`None`, `[]`, `"x"`)
- **Closes:** foundation for 20, 21, 25, 27, 28, 37. Bug: "four sources of truth" (reverse-engineering row 10).
- **Depends on:** none.
- **Collision:** X-03 edits the same file afterwards (sequential).
- **Acceptance:** `python -m pytest director/test_blocking.py -q`
- **OWNER DECISION:** approve the blocking schema (reverse-engineering F "NEW").
- **Second-attempt risk:** low.

**X-02 | blocking lint (on the sheet, before any image)**
- **Files:** `director/blocking_lint.py` NEW; `director/test_blocking_lint.py` NEW. Tests written first by an observer and frozen (rule 54(3)).
- **Change:** `lint(sheets: list[dict], lock: dict|None = None, fps=24) -> list[str]`. Seconds = `edit_frames/fps` from `lock` when given (`timeline_lock_io.frames_for`), else `writer_seconds`. Constants are tuning knobs, each with a `# ponytail: uncalibrated` comment:
  - `MAX_SPEED_H = 0.25` (frame heights/s), `POSE_CHANGE_MIN_SEC = 1.0`, `CONT_TOL = 0.05`, `MAX_MOVING = 3`.

  | Code | Check |
  |---|---|
  | L01 | `blocking.validate` problems |
  | L02/L03 | `distance/seconds > MAX_SPEED_H` → "end not reachable in N frames"; pose change with seconds < POSE_CHANGE_MIN_SEC |
  | L04 | crossing: for two moving cast, `sign(xa-xb)` at start ≠ at end |
  | L05 | shot N end vs shot N+1 start for each common cast id: abs dx, abs dy ≤ CONT_TOL and same pose and facing, unless N `cut_to_next == "cut"` |
  | L06 | moving cast > MAX_MOVING |
  | L07 | `speaks` but `mouth_moves` false at both start and end; or `mouth_moves` without `speaks` |
  | L08 | each `sound_cues[].text` through `h3.prompt_hygiene.check_sound_cue(text, visible=[cast names + prop classes])`; PromptError becomes a problem |
  | L09 | entry char start.x in [0,1], or exit char end.x in [0,1] (must be off-frame) |

  CLI: `python director/blocking_lint.py <blocking_dir> [--lock timeline_lock.json]`. Exit 1 on any problem; prints one line per problem.
- **Tests (hand values):**
  - `test_speed_ok_5s`: 0.225 / 5.0 = 0.045 → pass.
  - `test_speed_fail_12_frames`: 0.225 / 0.5 = 0.45 > 0.25 → L03.
  - `test_pose_change_18_frames_fails` (0.75 s) and `test_pose_change_24_frames_passes`.
  - `test_crossing`: A x 0.3→0.7, B x 0.6→0.4 → L04.
  - `test_continuity_0_03_ok_0_10_fails`; `test_continuity_cut_allows_jump`.
  - `test_four_movers_fail`.
  - `test_speaker_without_mouth_fails`.
  - `test_serpents_hiss_fails`; `test_snake_visible_prop_passes`.
  - `test_entry_must_start_offscreen`.
  - `test_lock_seconds_override_writer_seconds`: writer 5 s, lock 12 frames → fail.
- **Closes:** 20, 21, 27 (at sheet level), 28 (speaking list correct); the movement half of 4/52(3).
- **Depends on:** X-01.
- **Collision:** none.
- **Acceptance:** `python -m pytest director/test_blocking_lint.py -q`
- **OWNER DECISION:** the four constants.
- **Second-attempt risk:** med (geometry edge cases; that is why the tests are frozen first).

**X-03 | blocking adapters (one sheet feeds router, prompt, gates, Flow)**
- **Files:** `director/blocking.py` (append); `director/test_blocking.py` (append).
- **Change:** add pure functions.
  - `router_features(sheet, edit_frames, fps=24)` returns:
    - `kind`, `duration_sec = edit_frames/fps`
    - `needs_end_pose = any(is_moving(c))`, `cast_count = sum(is_moving)`
    - `multi_arm = any(c.arms > 2)`, `arc_sec`
    - These are exactly the keys shot_router.py:17-24 validates.
  - `prompt_args(sheet)` returns `{cast: [names], on_screen: [names with start or end x in 0..1], speaking: [names with speaks], sound_cues: [texts], visible: names + prop classes}`. This is the signature of prompt_hygiene.clean_prompt (prompt_hygiene.py:211-218).
  - `image_expect(sheet, edit_frames, fps=24)` returns `{required_cast_count: count of cast on-screen at both start and end, entry_exit_allowed: bool(entries or exits), arms: {id: n}, posture: {id: (start.pose, end.pose)} mapped to standing|seated|None (other poses → None), displacement: {id: distance}, seconds}`.
  - `known_classes(sheet)` returns `{"person"} | {p.class for p in props}`.
  - `change_list(sheet)` returns ordered strings, one per moving cast member:
    - `"<NAME>: move from (x0,y0) to (x1,y1)"`, coordinates printed with 2 decimals, only when distance > 0.02.
    - `"<NAME>: <pose0> -> <pose1>"`, `"<NAME>: turn to face <facing>"`, `"<NAME>: mouth open"` / `"<NAME>: mouth closed"`.
    - Props whose `visible` differs: `"<class>: appears"` / `"<class>: disappears"`.
    - Always last: `"keep everything else exactly the same"`.
- **Tests:**
  - `test_router_features_kfi_case`: seated→standing, arc 2.0, edit_frames 168 → duration 7.0, needs_end_pose True, cast_count 1; shot_router.route_shot gives **"KFI"**.
  - `test_router_features_soft_se_case` (arc 1.0 → "SOFT_SE").
  - `test_prompt_args_offscreen_entry_not_on_screen`.
  - `test_image_expect_counts` (2 on-screen + 1 entering → required 2, entry_exit_allowed True).
  - `test_known_classes`.
  - `test_change_list_exact`: Shiva seated→standing only → `["SHIVA: seated -> standing", "keep everything else exactly the same"]`.
- **Closes:** 21; 27/28 inputs; 37 (known classes).
- **Depends on:** X-01, D-ROUTER (only for the router assertion; use `route_shot(features)` with its current signature if D-ROUTER is not merged yet).
- **Collision:** same file as X-01. Run after it.
- **Acceptance:** `python -m pytest director/test_blocking.py -q`
- **OWNER DECISION:** none beyond X-01.
- **Second-attempt risk:** low.

**X-04 | shot_router reads the sheet + lock (routes.json)**
- **Files:** `director/shot_router.py`; `director/test_shot_router.py` (append; Haiku finds the existing file with Glob).
- **Change:**
  - Add `plan_from_blocking(sheets: dict, lock: dict, allow_s=False) -> dict`. For each lock shot in lock order: `features = blocking.router_features(sheets[id], frames_for(lock,id))` then `route_shot(features, allow_s)`. This replaces the hand-built features (reverse-engineering row 11). A lock shot without a sheet, or a sheet without a lock shot, raises RouterError.
  - Add `H3_MODE = {"SE": "FL2VA", "SOFT_SE": "FL2VA", "KFI": "FL2VA", "REF_S": "Ref2VA", "S": "I2VA", "POST": None}`, written as `result["h3_mode"]`. This is the one table from route to h3 mode (the third-router issue, h3/router.py).
  - CLI `python director/shot_router.py --blocking DIR --lock LOCK --out routes.json` writes `{lock_sha256: lock["input_sha256"], routes}`.
- **Tests:**
  - `test_plan_from_blocking_uses_lock_seconds`: writer_seconds 3, lock 168 frames → duration_sec 7.0.
  - `test_missing_sheet_raises_router_error`.
  - `test_every_gpu_route_has_h3_mode`: every route except POST has a non-None h3_mode, and for FL2VA/Ref2VA the name is in compile_h3_sing8.py:147's known set.
  - `test_routes_json_carries_lock_sha`.
- **Closes:** 3 (one router input), 21 (routes from the script). Bug: reverse-engineering row 11, Opus bug 9 wiring.
- **Depends on:** X-03, D-ROUTER, D-LOCK.
- **Collision:** shot_router.py is also edited by D-ROUTER. Run after it.
- **Acceptance:** `python -m pytest director/test_shot_router.py director/test_blocking.py -q`
- **OWNER DECISION:** S stays off (allow_s False) until the SHOT-008 A/B test.
- **Second-attempt risk:** low.

**X-05 | prompt cast/mouth/sound inputs come from the sheet (v4_to_h3)**
- **Files:** `h3/v4_to_h3.py`; `h3/tests/test_v4_to_h3.py` (append).
- **Change:**
  - `convert_pack(..., blocking_dir=None)` (v4_to_h3.py:618). When given, load sheets with `blocking.load_reel`.
  - In the shot builder (v4_to_h3.py:574-577), set `subjects = [c["id"] for c in sheet["cast"]]` instead of `reference_anchors.character_positions`.
  - Add `"cast_lock": blocking.prompt_args(sheet)` to the returned shot dict (next to `"sound_plan"`, line 612).
  - Problem when character_positions ids ≠ sheet cast ids: `"<sid>: cast differs from blocking sheet"`.
  - `blocking_dir=None` keeps today's behaviour (other callers and tests unchanged).
  - The compiler side is D-PROMPT. compile_h3_sing8.compile_fl2va_prompt must call `prompt_hygiene.clean_prompt(text, **shot["cast_lock"])`; this card only produces `cast_lock`.
- **Tests:**
  - `test_subjects_from_blocking`.
  - `test_cast_mismatch_is_problem`.
  - `test_cast_lock_equals_prompt_args`.
  - `test_no_blocking_dir_unchanged`: the existing round-trip fixture output is byte-equal to before.
- **Closes:** 27 and 28 (inputs; final closure in D-PROMPT); 21. Bug: "subjects_present is a second cast list" (reverse-engineering row 9).
- **Depends on:** X-03; run after D-PROMPT's v4_to_h3:160 edit.
- **Collision:** v4_to_h3.py is also edited by D-PROMPT and the lock/trim job of another part (fit_lattice from lock). Strictly sequential: those first, X-05 last.
- **Acceptance:** `python -m pytest h3/tests/test_v4_to_h3.py -q`
- **OWNER DECISION:** mouth wording (problem 28) belongs to D-PROMPT; this card does not wait on it.
- **Second-attempt risk:** med (big file, collisions).

---

## B. Story writer (Opus medium via the claude CLI) and source check

**X-06 | writer_guard (limit check, spend + usage log, schema validation)**
- **Files:** `director/writer_guard.py` NEW; `director/test_writer_guard.py` NEW; `.gitignore` (add `ledgers/`).
- **Change:**
  - `cli_ready(which=shutil.which, run=subprocess.run)`: raises `WriterUnavailable` if `claude` is not on PATH or `claude --version` returns non-zero. This is free and makes no model call. The CLI uses the subscription and has no key: write_pack strips ANTHROPIC_API_KEY (write_pack.py:366).
  - `scan_stream(stdout) -> {limit_error, is_error, cost_usd, num_turns, usage}`:
    - `limit_error` is the first `{"type":"system","subtype":"api_retry"}` whose `error` is in `LIMIT_ERRORS = {"rate_limit","authentication_failed","billing_error","account_on_hold","oauth_org_not_allowed"}`.
    - The rest come from the last `{"type":"result"}`: `is_error`, `total_cost_usd`, `num_turns`, `usage`.
    - Field names per https://code.claude.com/docs/en/headless (api_retry table; result carries `total_cost_usd`, a client-side estimate).
  - Reuse `voice_cast.Ledger` (voice_cast.py:112-165) in integer **cents**: `Ledger(LEDGERS/"writer_spend.jsonl", cap_cents)`.
  - `guarded_call(stage, prompt, call_fn, ledger, est_cents, usage_path)`:
    - `ledger.reserve(f"{stage}:{uuid4().hex[:8]}", est_cents)`, then `stdout = call_fn(prompt, max_budget_usd=est_cents/100)`, then `scan_stream`.
    - `ledger.settle(id, ceil(cost_usd*100) if cost_usd is not None else est_cents, confirmed=False)`.
    - Append a usage row `{t, stage, num_turns, usage, cost_usd, is_error, limit_error}`.
    - If `limit_error`: raise `WriterLimit` (no retry, no repair). If `is_error`: raise RuntimeError.
  - Cap from env `WRITER_CAP_CENTS`. Unset or 0 refuses every call (fail-closed).
  - Validation:
    - `validate_pack(rows, blocking_dir) -> list[str]`, stdlib only.
    - Each row has `id`, `time_range`, `audio_and_dialogue_track`, `per_second_directives`.
    - Directives have numeric `t0 < t1`, are contiguous (`next.t0 == prev.t1` within 0.05), start at 0, and each carries `source_refs: [str]`.
    - Every row id has a blocking file, and `blocking.validate` problems are included.
- **Tests:**
  - `test_over_cap_refuses_before_call`: cap 200, committed 100, est 150 → SystemExit; fake call count **0**.
  - `test_settle_rounds_cost_up`: cost 0.734 → **74** cents.
  - `test_rate_limit_event_raises_writer_limit` (stream fixture with an api_retry event).
  - `test_is_error_result_raises`.
  - `test_unset_cap_refuses`.
  - `test_cli_ready_missing_binary`.
  - `test_validate_pack_gap_in_events` (t1 2.0, next t0 2.5 → problem).
  - `test_validate_pack_missing_blocking`.
- **Closes:** 18 (now in code), 46 (writer half: expired or limited access seen at once). Bug: reverse-engineering row 15 (no spend counter, no key check, no output contract).
- **Depends on:** X-01.
- **Collision:** none.
- **Acceptance:** `python -m pytest director/test_writer_guard.py -q`
- **OWNER DECISION:** cap in cents and per-stage estimate; whether a one-line probe call before stage 1 is allowed (default: no probe; the limit is detected from the first stream).
- **Second-attempt risk:** low.

**X-07 | write_pack wiring: guard every Claude stage, targeted repair, writer gate**
- **Files:** `director/write_pack.py`; `director/test_write_pack_guard.py` NEW; the staged brief file loaded by `staged_brief(DEFAULT_PROMPT_VERSION)` (write_pack.py:88; Haiku locates it and appends one schema section).
- **Change:**
  - `call_claude(..., max_budget_usd=None)` adds `["--max-budget-usd", f"{max_budget_usd:.2f}"]` when set (flag per https://code.claude.com/docs/en/headless). Return the raw stdout alongside `join_stream`, so writer_guard can scan it.
  - When `via == "claude"`, the stage call goes through `writer_guard.guarded_call`. Run `cli_ready()` once before stage 1.
  - Targeted repair in `run_stage` (write_pack.py:851-856). Today `prompt_for(errors)` asks for the whole stage and overwrites `raw_path`. New behaviour:
    - Collect ids with `re.findall(r"\bSHOT-\d{3}\b")` from the error lines.
    - If every error line has an id: prompt = base + `"Return ONLY a JSON list with the corrected objects for shots: <ids>"` + those objects + errors.
    - Save as `stage_<name>_repair<k>.json`; merge by id into data; re-check.
    - The original `stage_<name>_raw.json` is never overwritten.
    - Error lines without an id: raise StageFailed (no whole-stage rewrite).
  - At the end of `run_staged` (near write_pack.py:1322):
    - Write `<out>/blocking/<id>.json` from each row's `blocking` key.
    - Run `writer_guard.validate_pack`, `blocking_lint.lint`, `script_inspect.from_pack` (D-INSPECT) and `source_check.citations` (X-08).
    - Write `<out>/writer_gate.json {shots_sha256, ok, problems}`. If not ok, exit non-zero.
  - Brief: append the blocking/1 schema (X-01) and the per-second `source_refs` requirement.
- **Tests (fake call, no CLI):**
  - `test_repair_only_named_shots`: 3 shots, error `"BLK-L03 at SHOT-002: ..."`. The repair prompt contains SHOT-002 and not SHOT-001; SHOT-001 and SHOT-003 are unchanged after the merge; raw r0 bytes are unchanged; `stage_X_repair1.json` exists.
  - `test_unattributable_error_fails_stage`.
  - `test_limit_error_stops_without_repair` (fake call count 1).
  - `test_max_budget_flag_in_argv`.
  - `test_writer_gate_written_and_blocks_on_lint`.
  - `test_blocking_files_written`.
- **Closes:** 15 (writer emits a gated, renderable script), 18. Bug: C9 whole-stage repair rewrite, row 15.
- **Depends on:** X-06, X-02, X-08, D-INSPECT.
- **Collision:** write_pack.py (1400+ lines) has no other X job; check other parts for write_pack edits.
- **Acceptance:** `python -m pytest director/test_write_pack_guard.py director/test_write_pack_staged.py director/test_r3_write_pack.py -q`
- **OWNER DECISION:** writer is Opus medium (rule 11/27 text is stale; see X-23); targeted-only repair policy.
- **Second-attempt risk:** high (large file, stage data shapes). Supervisor: quote write_pack.py:819-862 and 1229-1330 in the spec.

**X-08 | source_check.json**
- **Files:** `director/source_check.py` NEW; `director/test_source_check.py` NEW.
- **Change:**
  - `line_ids(source_text) -> {"L<n>": text}`, numbering non-empty physical lines (1-based).
  - `citations(source_text, rows, sheets) -> list[str]` (free, offline):
    - C1: each blocking cast member has ≥1 `source_refs`.
    - C2: every ref exists.
    - C3: every per-second directive has ≥1 ref.
  - `review(items, reviewer_fn, writer_model, reviewer_model)`: raises if `writer_model == reviewer_model` (SAME_MODEL). `reviewer_fn(claim, cited_lines) -> "supported"|"unsupported"|"unclear"` is injected.
  - `write_report(path, ...)` writes `source_check.json {source_sha256, shots_sha256, citations, verdicts, pass}`. Pass = no C1-C3 problem and 0 `unsupported` among cast items (default; replaceable by the owner's rule).
  - CLI `--citations-only` (free) for the writer gate.
- **Tests:**
  - `test_line_ids_skip_blank`: lines `a,b,"",c,""` → **L1, L2, L4**.
  - `test_unknown_ref_L3_fails`.
  - `test_cast_without_ref_fails`.
  - `test_same_model_refused`.
  - `test_unsupported_cast_fails_pass` (fake reviewer).
  - `test_report_shas`.
- **Closes:** 16 (code half; pass definition by owner). Bug: row 16 (writer grades itself).
- **Depends on:** X-01.
- **Collision:** none.
- **Acceptance:** `python -m pytest director/test_source_check.py -q`
- **OWNER DECISION:** fidelity pass definition and reviewer model (free model; no paid call without go).
- **Second-attempt risk:** low.

---

## C. Keyframes up to Gate B

**X-09 | plates registry + A/B Flow jobs from the sheet**
- **Files:** `director/keyframe_jobs.py` NEW; `director/test_keyframe_jobs.py` NEW.
- **Change:**
  - `plates_index(flow_root) -> {plate_id: {path, sha256}}`, reading `<flow_root>/plates/plates.json` plus files.
  - `jobs_for_shot(sheet, plate, bible_names)` returns two jobs with exactly the key set of flow/scripts/build_jobs.py:301-325:
    - **A**: `method: "edit"`, `chips: [plate path]` (single reference, rule 25), prompt = "same set, add: <name> at (x,y), scale s, facing f, pose p ..." from `start`, `base_edit_id: plate_id`.
    - **B**: `base_edit_id: "<SHOT>-A"`, `chips: ["<SHOT>-A final"]`, `edit_instruction = "same picture, make these exact changes only: 1) … n)"` from `blocking.change_list(sheet)`.
    - `people_count` = on-screen cast count.
  - A missing plate raises `KeyframeJobError("plate PLATE-x missing: make it once per location first")`.
  - CLI writes `<flow_root>/adhyay_NN/keyframe_jobs.json`. Never calls Flow.
- **Tests:**
  - `test_job_keys_match_build_jobs`: key set equality with a build_jobs fixture job.
  - `test_b_is_edit_of_a` (base_edit_id, single chip).
  - `test_b_instruction_from_change_list` (exact text from the X-03 hand case).
  - `test_missing_plate_raises`.
  - `test_people_count`.
- **Closes:** 20 (B as an edit of A in code), 23 (job carries everything; rule).
- **Depends on:** X-03.
- **Collision:** none.
- **Acceptance:** `python -m pytest director/test_keyframe_jobs.py -q`
- **OWNER DECISION:** none.
- **Second-attempt risk:** low.

**X-10 | keyframe_gate.py (keyframe_review.json + image_gates + plate_composite → keyframe_gate.json)**
- **Files:** `director/keyframe_gate.py` NEW; `director/test_keyframe_gate.py` NEW.
- **Change:**
  - `validate_review(review, sheet)`: keyframe_review.json is written by the full-size reviewer, human or agent. Shape: `{shot_id, full_size: true, reviewer, A: {cast_count, chars: {id: {arms, posture: standing|seated|unknown}}, extra_figures: [], marks_or_letters: bool}, B: {...}}`. `full_size` must be true (rule 25 / problem 22).
  - `gate(plate, img_a, img_b, sheet, review, lock)`:
    - masks: `ma = plate_composite.diff_mask(plate, A)`, `mb = diff_mask(plate, B)` (plate_composite.py:154). The empty plate makes character masks free.
    - `image_gates.background_lock(A, B, ma, mb)`, plus `area_fraction >= MIN_AREA = 0.25` (D-IMG).
    - `plate_composite.plan(A, B, ma, mb)`. On `use == "composite"`, write `B_final = composite(A, B, mb, feather_px=4)`; otherwise B_final = B.
    - `cast_parity(review.A.cast_count, review.B.cast_count, expect.required_cast_count, expect.entry_exit_allowed)`.
    - `limb_parity` per char against `expect.arms`.
    - `posture_matches` per char against `expect.posture`.
    - `feasible_motion(displacement, seconds, MAX_SPEED_H)` with seconds from the lock.
    - `extra_figures` non-empty or `marks_or_letters` → fail.
  - Writes `<flow_root>/keyframe_gate/<SHOT>.json {sha256 of plate, A, B, B_final, sheet, review, lock.input_sha256; checks; pass}`.
- **Tests (synthetic 64×64):**
  - `test_shift_2px_composites`: square 10×10, diff_mask dilate 6 → 22×22; holes 2×22 = 44/4096 = **0.0107 ≤ 0.02**.
  - `test_shift_20px_keeps_b`: 440/4096 = **0.107**.
  - `test_background_moved_fails` (np.roll of background by 3 px).
  - `test_missing_sage_fails` (review A cast 2, required 3).
  - `test_seated_vs_standing_fails`.
  - `test_not_full_size_refused`.
  - `test_record_hashes_change_with_B`.
- **Closes:** 20, 21, 22 (enforced), 25 (gate runs at approval with real frames). Bug: 8A/8B pose mismatch, shots 7/9 missing cast.
- **Depends on:** X-03, D-IMG, D-LOCK.
- **Collision:** none.
- **Acceptance:** `python -m pytest director/test_keyframe_gate.py -q`
- **OWNER DECISION (problem 21):** manual keyframe_review.json counts (default) or a detector.
- **Second-attempt risk:** med.

**X-11 | approval sheet (3 layers) + Gate B record**
- **Files:** `director/approval_sheet.py` NEW; `director/test_approval_sheet.py` NEW.
- **Change:**
  - `build(lock, sheets, source_check, keyframe_gates, routes, vo_report=None)` writes `approval_sheet.md` + `.csv`, one row per shot, three independent layers (the reel-1 approval_sheet_18x3 idea, rule 36):
    - **timing**: edit_frames, seconds, voice lines start/end.
    - **source**: refs + verdicts.
    - **staging**: start→end summary, change_list, route, keyframe_gate pass and metrics, image paths.
  - `approve(shot, by, gate_b_path)`: refuses unless that shot's keyframe_gate pass is true. Appends `{shot, by, date, keyframe_gate_sha256}` to `gate_b.json` (append-only).
  - `gate_b_ok(gate_b, keyframe_gate_dir, shot_ids) -> list[problems]`: missing approval, or approved keyframe_gate sha ≠ current file sha.
- **Tests:**
  - `test_three_layers_present`.
  - `test_approve_refused_on_failed_gate`.
  - `test_gate_b_stale_after_new_B` (gate file rewritten → problem).
  - `test_csv_row_count_equals_lock_shots`.
- **Closes:** 21 and 25 (Gate B is a record, not a note); 35 partly (explicit approvals).
- **Depends on:** X-08, X-10, X-04.
- **Collision:** none.
- **Acceptance:** `python -m pytest director/test_approval_sheet.py -q`
- **OWNER DECISION:** owner approves each shot (the `approve` command is run by the owner or with the owner's word).
- **Second-attempt risk:** low.

---

## D. Lock consumers

**X-12 | lock_rows helper (one integer clock)**
- **Files:** `director/timeline_lock_io.py` (append); `director/test_timeline_lock_io.py` (append).
- **Change:** `lock_rows(lock) -> list[dict]` in lock order: `{id, start_frame, edit_frames, offset_sec = start_frame/fps, editorial_duration_sec = edit_frames/fps, trim_in_frame, trim_out_frame}`.
  - Recompute start_frame as a running integer sum and raise ValueError if a recorded `start_frame` differs.
  - Missing trim keys raise KeyError naming the shot (D-LOCK provides them).
- **Tests:** `test_lock_rows_hand`: edit_frames [168,120,192] → start [0,168,288], offsets **[0.0, 7.0, 12.0]**, total 480 = **20.0 s**; `test_start_frame_mismatch_raises`.
- **Closes:** 6 (shared helper).
- **Depends on:** D-LOCK.
- **Collision:** timeline_lock_io.py is also edited by D-LOCK (params). Run after it.
- **Acceptance:** `python -m pytest director/test_timeline_lock_io.py -q`
- **OWNER DECISION:** none.
- **Second-attempt risk:** low.

**X-13 | render_controller: timeline gate, Gate B gate, Gate D on lock seconds, render_ready.json**
- **Files:** `h3/render_controller.py`; `h3/pipeline_contract.py`; `h3/tests/test_render_controller_wiring.py` (append).
- **Change:**
  - pipeline_contract.py:11-22: add `("timeline", "Timeline lock matches its inputs")` and `("keyframes", "Gate B: every shot approved with a passing keyframe gate")` to STEP_ORDER before `lint`, and to PRE_ASSEMBLY. `build_plan` refuses unknown step ids (pipeline_contract.py:33), so this edit is required.
  - `plan_pipeline(..., lock_path=None, gate_b_path=None, keyframe_gate_dir=None)` (render_controller.py:567):
    - `results["timeline"]`: no path → ok False "no timeline lock". Otherwise `verify_lock(lock_path, load_lock(lock_path)["inputs"])` (StaleLockError → ok False), plus the lock shot ids must equal the selected shot ids.
    - `results["keyframes"] = approval_sheet.gate_b_ok(...)`.
  - `_gate_d_result` (render_controller.py:537-556): pass shots copied with `editorial_duration_sec = row["editorial_duration_sec"]` from `timeline_lock_io.lock_rows(lock)`, never the story value. Gate D then uses the same clock as build_final_reel.
  - CLI: add `--lock`, `--gate-b`, `--keyframe-gates`. `--mode execute` without `--lock` returns 2. When `assembly_allowed` is false, execute returns 1.
  - When all pre-render gates pass, write `<out>/render_ready.json {lock_input_sha256, gate_b_sha256, story_sha256, ok: true}`.
  - The runner side is another part: run_colab_batch.main `--go` must refuse without a matching render_ready.json (D-J8 runner job).
- **Tests:**
  - `test_plan_pipeline_no_lock_blocks` (results timeline ok False; assembly_allowed False).
  - `test_stale_script_byte_blocks` (edit one byte of an input → not ok).
  - `test_missing_gate_b_blocks`.
  - `test_gate_d_uses_lock_seconds`: story says 6.0 s, lock 168 → Gate D sees 7.0.
  - `test_execute_without_lock_exit_2`.
  - `test_render_ready_written_only_when_clean`.
- **Closes:** 1, 6, 8, 25, 35 (gate half). Bug: two Gate D verdicts (render_controller.py:551-552).
- **Depends on:** X-12, X-11, D-LOCK.
- **Collision:** none in this part. D-J8 runner reads render_ready.json.
- **Acceptance:** `python -m pytest h3/tests/test_render_controller_wiring.py h3/tests/test_render_controller.py -q`
- **OWNER DECISION:** none.
- **Second-attempt risk:** med.

**X-14 | clip_qa.py (frame extractor + clip_gates inside the lock window + clip_qa.json)**
- **Files:** `director/clip_qa.py` NEW; `director/test_clip_qa.py` NEW.
- **Change:**
  - `extract(clip, trim_in, trim_out, size=(192,336), run=subprocess.run) -> np.ndarray[F,H,W] float32 0..1`:
    - `ffmpeg -v error -i clip -vf "select='between(n\,TI\,TO-1)',scale=192:336,format=gray" -vsync 0 -f rawvideo -pix_fmt gray -`.
    - Frame count must equal `trim_out - trim_in`, else ClipQAError.
  - `features(frames, key_a, key_b)` →
    - `flow_p95` = 95th percentile of abs diff of consecutive frames;
    - `sim_to_a` per frame (image_gates.block_ssim);
    - end metrics against B (`end_frame_pass` inputs ssim/lpips/cosine: lpips not available → pass `lpips=0.0` and record "lpips not measured");
    - flicker (clip_gates.flicker_score on every 2nd frame).
  - `new_classes`: `clip_review.json` (counts per sampled frame, every 6th frame per rule 33; written by the reviewer like keyframe_review) is checked against `blocking.known_classes(sheet)`. Any class not known is new. Do not use clip_gates.new_object_classes's own learned set (clip_gates.py:82-93).
  - Audio: `score.sfx_study.find_hits(audio, 48000)` + `match_cues(hits, sheet sound_cues)` give `sfx_keep: [(t0,t1)]` and `bed_db` (sfx_study.py:142, 248). Import functions only; never call `main` (its constants point at reel 1).
  - `verdict = clip_gates.verdict({tail, end, cuts, new_classes, flicker, flicker_limit})` (D-CLIP requires all keys).
  - Writes `<results>/<SHOT>/clip_qa.json {clip_sha256, window: [ti,to], results, verdict, sfx_keep, bed_db, owner_accept: null}`.
  - CLI `accept --shot S --code NEW_OBJECT --note ...` records `owner_accept {code, date, note}`.
  - `clip_ok(path, clip) -> problems`: sha mismatch, or verdict fail without owner_accept.
- **Tests:**
  - `test_extract_window_count`: lavfi `testsrc=size=768x1344:rate=24:duration=7.6667` (184 frames), ti 8, to 176 → **168** frames.
  - `test_snake_not_known_blocks`.
  - `test_owner_accept_unblocks_and_is_recorded`.
  - `test_sha_mismatch_blocks`.
  - `test_sfx_keep_matches_cue` (synthetic click at 2.0 s, cue t 2.1 → kept, tol 0.4).
- **Closes:** 37, 40 (data for the policy). Bug: verdict({}) passes; owner overrides not recorded (reverse-engineering row 7).
- **Depends on:** X-03, D-CLIP, D-LOCK.
- **Collision:** none.
- **Acceptance:** `python -m pytest director/test_clip_qa.py -q`
- **OWNER DECISION:** clip_review by reviewer vs detector; owner_accept record format (default above).
- **Second-attempt risk:** med.

**X-15 | build_final_reel part 1: required --reel, lock_rows, no silent fallbacks, waivers.json, clip_qa gate**
- **Files:** `director/build_final_reel.py`; `director/test_build_final_reel_lock.py` NEW.
- **Change:**
  - build_final_reel.py:253: `--reel` becomes `required=True`, regex `^[a-z0-9_]+$`; `REEL_CLOSED = {"kalika_reel1"}` exits (rule 53).
  - Add `--lock` (required). Delete the `editorial_by_lang` import and apply_rows/apply_shots (lines 261-265). Rows take `editorial_duration_sec` from `timeline_lock_io.lock_rows(verify_lock(...))`, and h3_shots `timing_and_lattice` trims are checked equal to the lock.
  - `mux_argv` (lines 66-76): offsets from lock_rows `offset_sec`, not float sums. A missing VO WAV for a shot that has lines in shots.json raises SystemExit (today it becomes silence).
  - Lines 287-291: a missing `vo_tracks_report.json` raises unless `--title-cards`. Remove the second fallback path.
  - Delete `WAIVED` (line 32). `load_waivers(pack, reel)` reads `<pack>/waivers.json {reel, codes, signed_by: "owner", date}`. Missing file → none; reel mismatch or no signed_by → SystemExit. Report lists waived codes.
  - Before assembly: `clip_qa.clip_ok` for every clip in `--clips`; any problem → SystemExit.
- **Tests (pure functions; ffmpeg not run):**
  - `test_reel_required` (argparse SystemExit).
  - `test_reel1_refused`.
  - `test_offsets_from_lock` (**[0.0, 7.0, 12.0]**).
  - `test_missing_vo_with_lines_raises`.
  - `test_missing_report_raises`.
  - `test_reel2_no_waivers_blocks_dead_air` (DEAD_AIR_PAUSE stays blocking).
  - `test_waivers_reel_mismatch_raises`.
  - `test_clip_qa_fail_blocks`.
- **Closes:** 3, 6, 19, 37 (assembly side). Bug: Opus 17 (silent fallbacks, float offsets, --reel default), hard-coded reel-1 waiver.
- **Depends on:** X-12, X-14, D-LOCK.
- **Collision:** build_final_reel.py is also edited by X-16 and X-17 (sequential X-15 → X-16 → X-17), and by any other-part audio_edge job. Coordinate order.
- **Acceptance:** `python -m pytest director/test_build_final_reel_lock.py -q` and the existing build_final_reel tests (Glob `director/test_*final_reel*`).
- **OWNER DECISION:** per-reel waivers file format.
- **Second-attempt risk:** med.

**X-16 | build_final_reel part 2: caption_fields + crop/scale before the ASS burn**
- **Files:** `director/build_final_reel.py`; `h3/gate_d_audio.py`; `director/test_build_final_reel_captions.py` NEW.
- **Change:**
  - Delete `CAPTION_FIXES` (line 95) and its loop (lines 168-170).
  - `spoken_cues_real(rows, report, lang, manifest, font_file)` builds lines `{id, lang, spoken_text, caption_text, caption_diff_approved}`:
    - `spoken_text` = manifest row text for `"<line>.<lang>"`, with sha256 checked against `text_sha256`. Mismatch → SystemExit.
    - caption fields come from the shots.json line dict keys `caption_text` / `caption_diff_approved`.
    - Text = `caption_fields.caption_lines(lines)`; CaptionError → SystemExit.
  - Add `--manifest` (required unless `--title-cards`).
  - gate_d_audio.py:347 `build_final_mux_argv(..., pre_vf=None)`: line 364 becomes `f"[0:v]{pre_vf + ',' if pre_vf else ''}{build_subtitles_filter(...)}[vsub]"`. Default None leaves other callers unchanged.
  - build_final_reel probes the video size:
    - 768×1344: `DELIVERY_VF = "scale=1098:1920:flags=lanczos,crop=1080:1920:9:0"`. Hand check: 768×1920/1344 = 1097.14 → even 1098; (1098−1080)/2 = 9. Rule 51: "1080x1920 (lanczos, centre crop of the 768x1344 picture)".
    - 1080×1920: None.
    - Anything else: SystemExit.
- **Tests:**
  - `test_no_caption_fixes_symbol` (`not hasattr(bfr, "CAPTION_FIXES")`).
  - `test_unapproved_caption_diff_raises`: reel-2 style line spoken "गलती हुई", caption "ग़लती हुई", approved False.
  - `test_approved_diff_used`.
  - `test_manifest_sha_mismatch_raises`.
  - `test_crop_before_ass_in_argv` (index of "crop=1080:1920:9:0" < index of "ass=").
  - `test_export_probes_1080x1920`: real ffmpeg; lavfi testsrc 768×1344 for 2 s, tiny ASS → ffprobe **1080x1920**.
  - `test_gate_d_default_unchanged` (pre_vf None argv equals old argv).
- **Closes:** 14, 41 (code path matches rule 51). Bug: reverse-engineering row 1 (libass on the uncropped frame), Opus 14 (wrong text basis).
- **Depends on:** X-15, D-VOICE (manifest), X-23 rule 51 amendment (owner).
- **Collision:** gate_d_audio.py is also edited by X-18 (sequential X-16 → X-18).
- **Acceptance:** `python -m pytest director/test_build_final_reel_captions.py h3/tests -q -k "gate_d or final"`
- **OWNER DECISION:** amend rule 51 (CAPTION_FIXES → caption_fields; crop in code).
- **Second-attempt risk:** med.

**X-17 | build_final_reel part 3: --mix intake + versioned rN export + disk check**
- **Files:** `director/build_final_reel.py`; `director/test_build_final_reel_mix.py` NEW.
- **Change:**
  - `--mix LANG=WAV` (repeatable) and `--mix-voice LANG=WAV` (voice-only render of the same session, rule 50(3)).
  - `intake(mix, voice, total_frames, report_rows)`:
    - `wav_contract.require_wav`; 48000 Hz.
    - `need = total_frames * 2000` samples (48000/24). Length < need − 1 → refuse ("mix N samples short"). Longer → trimmed copy of exactly `need` samples.
    - Bus = mix − voice, sample by sample (same length).
    - Per speech window from vo_tracks_report: `voice_db − bus_db`. Need median in [15, 21.5] and min ≥ 12 (rules 48, 50).
    - Returns `{trimmed_path, median_db, min_db}`. Failure → SystemExit with the numbers.
  - With `--mix`, the language's audio is the trimmed mix (filter `[1:a]atrim=end_sample=need,asetpts=PTS-STARTPTS[<MASTER_LABEL>]`); no gate_d SFX/VO mix. `correct_loudness` is unchanged (−16, core.json).
  - Export name `<reel>_<lang>_r<N>.mp4`, N = 1 + max existing. Never overwrite (rule 50(2)).
  - Before export: `shutil.disk_usage(out).free >= MIN_FREE_GB_EXPORT * 2**30` (default 2.0), else SystemExit.
- **Tests:**
  - `test_mix_one_frame_short_refused`: lock 480 frames → need **960000**; mix 958000 refused.
  - `test_mix_long_trimmed_to_960000`.
  - `test_voice_over_bus_20db_passes`: voice sine amp 0.5, bus amp 0.05 → **20.0 dB**.
  - `test_bus_too_loud_fails`: bus amp 0.2 → **7.96 dB** < 12.
  - `test_next_version_r3_and_r1_untouched`.
  - `test_low_disk_refused` (fake disk_usage).
- **Closes:** 40 (Ableton mix measured right), 45 (local check). Bug: reverse-engineering rows 1 and 3 (manual delivery, no mix contract).
- **Depends on:** X-15, X-16.
- **Collision:** same file as X-15/X-16.
- **Acceptance:** `python -m pytest director/test_build_final_reel_mix.py -q`
- **OWNER DECISION:** move delivery crop and mix intake into code (default yes); MIN_FREE_GB_EXPORT.
- **Second-attempt risk:** med.

**X-18 | SFX policy in Gate D (rule 50(6))**
- **Files:** `h3/gate_d_audio.py`; `director/build_final_reel.py` (pass policy); `h3/tests/test_gate_d_sfx_policy.py` NEW.
- **Change:**
  - `sfx_policy_filter(label_in, label_out, keep, bed_gain_db)` → `volume='if(between(t,a1,b1)+between(t,a2,b2),1,G)':eval=frame` with G = 10^(bed_gain_db/20). Keep windows are the clip-relative `sfx_keep` from clip_qa.json.
  - `bed_gain_db = min(0, (voice_db − 22) − bed_db)`. Per shot, voice_db is the shot's voice RMS from vo_tracks_report; bed_db comes from clip_qa.json.
  - `build_mix_filter(..., sfx_policy=None)` (gate_d_audio.py:307) applies it per clip before concat. None leaves behaviour unchanged.
  - `check_sfx_beds(levels) -> errors`: SFX_BED_LOUD when `bed_db > voice_db − 22 + 0.5`.
  - build_final_reel passes the policy from each shot's clip_qa.json. A missing clip_qa.json raises (X-15 already blocks).
- **Tests:**
  - `test_bed_gain_hand`: voice −18, bed −30 → **−10 dB** → G = **0.3162**.
  - `test_bed_already_quiet_gain_0`: bed −45 → 0.
  - `test_keep_window_expression_text` (exact string).
  - `test_bed_louder_than_voice_minus_22_fails`.
  - `test_policy_none_unchanged`.
- **Closes:** 40. Bug: reverse-engineering row 4 (build_final_reel mixes model SFX without the 50(6) policy).
- **Depends on:** X-14, X-16.
- **Collision:** gate_d_audio.py after X-16; build_final_reel.py after X-17.
- **Acceptance:** `python -m pytest h3/tests/test_gate_d_sfx_policy.py h3/tests -q -k gate_d`
- **OWNER DECISION:** none (rule 50(6) already decided; the owner confirms −22 for code).
- **Second-attempt risk:** med.

**X-19 | score/cue_sheet.py requires the lock**
- **Files:** `score/cue_sheet.py`; `score/tests/test_cue_sheet_lock.py` NEW.
- **Change:**
  - `build_locked_cue_sheet(shots, lock, vo_reports, episode=None)`:
    - Copy shots and set `editorial_duration_sec = lock_rows[...].editorial_duration_sec`.
    - Call `build_cue_sheet(shots, episode=episode, vo_reports=vo_reports)` with no editorial and no voice_windows.
    - Error LOCK_MISMATCH if `sheet.total_frames != lock.total_frames` or shot ids differ.
    - Copy `bpm`, `snap`, `act` from the lock into each shot row.
    - `vo_reports` empty → error NO_VO_REPORT.
  - `main` (cue_sheet.py:592-652): add `--lock` (required) and `--lock-inputs-check`, which always runs `verify_lock(lock, lock["inputs"])`. StaleLockError → exit 2. `--vo-report` is required (≥1). Remove `--editorial` and `--voice-windows`.
  - `apply_editorial` stays for the old library tests (46 call sites in test_cue_sheet.py) but is unreachable from the CLI.
- **Tests:**
  - `test_no_lock_exit_2`.
  - `test_stale_wav_exit_2` (change one input byte).
  - `test_lengths_from_lock`: [168,120,192] → total_frames **480**, total_s **20.0**.
  - `test_bpm_snap_copied`.
  - `test_cli_has_no_editorial_flag`.
- **Closes:** 39; 3 (fourth clock removed from the CLI path). Bug: reverse-engineering row 5 (optional inputs, silent fallback); retiring editorial_by_lang no longer breaks the cue sheet.
- **Depends on:** X-12, D-LOCK (bpm/snap/act in the lock).
- **Collision:** none.
- **Acceptance:** `python -m pytest score/tests -q`
- **OWNER DECISION:** none.
- **Second-attempt risk:** low.

**X-20 | stem_builder −14 → named audition constant**
- **Files:** `score/stem_builder.py`; `score/tests/test_loudness_targets.py` NEW.
- **Change:**
  - `AUDITION_NODUCK_LUFS = -14.0  # music-only audition file, not a deliverable (log 11-09 17:23)`.
  - stem_builder.py:503 `write_noduck(..., target_lufs=AUDITION_NODUCK_LUFS)`; output file name gets the suffix `_audition`.
  - If the owner chooses "one target": use `load_core()["delivery"]["audio"]["lufs"]` instead.
- **Tests:** `test_only_audition_constant_is_minus_14`: an AST scan of director/, h3/, score/ (non-test files) finds the literal −14.0 only in stem_builder's AUDITION_NODUCK_LUFS. `test_deliverables_use_core`: gate_d LOUDNESS target equals core.json lufs.
- **Closes:** 42.
- **Depends on:** none.
- **Collision:** none.
- **Acceptance:** `python -m pytest score/tests/test_loudness_targets.py -q`
- **OWNER DECISION:** confirm −14 audition-only (reverse-engineering F, downgraded).
- **Second-attempt risk:** low.

---

## E. Git hooks

**X-21 | precommit_check: project key patterns, staged blob, binaries**
- **Files:** `tools/precommit_check.py`; `tools/test_precommit_check.py` (append).
- **Change:**
  - Add to SECRET_PATTERNS (precommit_check.py:11-16):
    - `"elevenlabs": r"sk_[0-9a-f]{40,}"`
    - `"anthropic": r"sk-ant-[A-Za-z0-9_-]{20,}"`
    - `"google": r"AIza[0-9A-Za-z_-]{35}"`
    - `"github": r"gh[pousr]_[A-Za-z0-9]{36,}"`
  - `_CONTROL_CHAR_RE` also matches `\x7f`.
  - `check_file(path, staged=True)` reads `git show :<path>` bytes (the staged blob), not the working copy (precommit_check.py:60).
  - Skip extensions `{.png,.jpg,.jpeg,.webp,.gif,.wav,.mp3,.mp4,.mov,.ttf,.otf,.zip,.pdf}` (no "not UTF-8" failure). The size limit still applies.
- **Tests:** secrets built at runtime (`"sk_" + "a"*48`) so the test file never trips the scanner.
  - `test_elevenlabs_key_found`, `test_anthropic_key_found`, `test_google_key_found`, `test_github_token_found`.
  - `test_nul_byte_found`.
  - `test_del_found`.
  - `test_staged_blob_scanned_after_worktree_cleaned`: tmp git repo; stage a file with a key, then clean the working file → still found.
  - `test_png_skipped`.
- **Closes:** 46 (patterns + staged blob), 44 (partly: syntax/control characters). Bug: Opus 12, merged E4.
- **Depends on:** none.
- **Collision:** none.
- **Acceptance:** `python -m pytest tools/test_precommit_check.py -q`
- **OWNER DECISION:** none.
- **Second-attempt risk:** low.

**X-22 | hooks: pre-commit NEW, pre-push runs pytest, core.hooksPath**
- **Files:** `.githooks/pre-commit` NEW (sh); `.githooks/pre-push`; `tools/test_git_hooks.py` NEW.
- **Change:**
  - pre-commit: same PY lookup as pre-push lines 6-8, then `"$PY" "$ROOT/tools/precommit_check.py"`. A non-zero exit blocks.
  - pre-push: `cd "$ROOT"`, then `"$PY" -m pytest ${PUSH_TEST_PATHS:-director h3 score tools} -q -p no:cacheprovider`. Its exit code is used directly (no wrapper; log 11-07 push with hidden failing tests). Then the existing secret_scan.
  - Install: the owner runs `git config core.hooksPath .githooks` (the hook never changes config, pre-push line 3).
- **Tests (tmp git repo, ANIME_PY = sys.executable):**
  - `test_precommit_blocks_staged_key` (`git commit` exit ≠ 0).
  - `test_precommit_allows_clean`.
  - `test_prepush_fails_on_failing_test`: PUSH_TEST_PATHS = tmp failing test; stub secret_scan exit 0 → exit 1, and the output contains "failed".
  - `test_prepush_passes_on_passing_test`.
- **Closes:** 44, 46 (enforced at commit and push).
- **Depends on:** X-21.
- **Collision:** none.
- **Acceptance:** `python -m pytest tools/test_git_hooks.py -q`, then (owner) `git config --get core.hooksPath` prints `.githooks`.
- **OWNER DECISION:** the owner sets core.hooksPath; the push test scope (full suites may take minutes).
- **Second-attempt risk:** med (sh on Windows Git Bash; LF line endings required: write the files with `newline="\n"`).

---

## F. Documents

**X-23 | blot / docs amendments (no code)**
- **Files:** `blot.md` in BOTH `D:\aai work\anime_studio\` and `D:\aai work\anime_studio_merge\` (rules 10, 17: kept equal); `MISTAKES_AND_LESSONS.md`; `HANDOFF_2026-11-10.md`; the log `D:\aai work\anime_studio\PROJECT_LOG.md` (NOW block); `anime_studio_merge\PROJECT_LOG.md` (stale copy).
- **Change (append-only amendments, never rewrite old lines):**
  1. **Rule 51 amendment:** "caption-only spelling fixes live in shots.json `caption_text` + `caption_diff_approved` per line (director/caption_fields.py); CAPTION_FIXES is deleted; crop/scale 768x1344→1080x1920 is done in build_final_reel before the ASS burn."
  2. **Rule 28(1) / R28:** "run.py about 40 KB; any `colab exec -f` payload ≤ 7 MB, pictures in 3 MB upload parts (rule 30(3)); the 12 MB figure is void (11.3 MB hung, C4)". Same correction in the MISTAKES C3 row "Fix" column (MISTAKES_AND_LESSONS.md:23) to match section 5 point 7 (line 71).
  3. **Numbering conflicts:**
     - Rule 46 heading gets "(superseded in part by rule 51)".
     - Rule 41 gets "(void: reel 1 closed, rule 53; shot 7 kept by owner 11-09 13:01)".
     - The tempo limits in rules 39 (1.15), 42 (1.15) and 47 (1.03) get "(superseded by timeline_lock: MAX_TEMPO 1.0, rule 52(2))".
     - Rule 43(3) points to the rule 46 amendment.
     - Rules 11/27 writer text: "story writer = Opus medium via the claude CLI (owner 11-11), guarded by writer_guard (cap, ledger)".
  4. **Stale NOW:**
     - In the anime_studio_merge/PROJECT_LOG.md copy, add a top line "STALE COPY, never written: the one log is D:\aai work\anime_studio\PROJECT_LOG.md (rule 10)".
     - Overwrite the NOW block of the real log with the current state.
     - HANDOFF_2026-11-10: append a "Corrections 11-11" section with the closure-review G lines (J3/J5/J6/J10 claims, the Kimi writer line now void).
  5. **New rule 56:** "blocking.json is the single source per shot (schema blocking/1); router, prompts, image/clip gates and Flow change lists read only it".
- **Tests:** none (docs). Check: `fc /b` of the two blot.md copies shows no difference; grep finds "superseded" on rules 39/42/46/47.
- **Closes:** 43; the rule halves of 29, 41, 44.
- **Depends on:** owner decisions; after X-16 (rule 51 text must match the code).
- **Collision:** none (docs only).
- **Acceptance:** `fc /b "D:\aai work\anime_studio\blot.md" "D:\aai work\anime_studio_merge\blot.md"` reports no differences.
- **OWNER DECISION:** every amendment text (blot rules are the owner's).
- **Second-attempt risk:** low.

## G. End-to-end proof

**X-24 | offline reel-2 end-to-end test: one sheet drives everything; one clock**
- **Files:** `director/test_e2e_blocking_lock.py` NEW (tests only, no module edits).
- **Change:** a synthetic reel-2 fixture: 3 shots, 3 blocking files, a lock with edit_frames [168,120,192] written by `timeline_lock_io.write_lock` over tmp input files, grey plate/A/B PNGs, and a review file.
- **Tests:**
  - `test_one_sheet_drives_router_prompt_gate_clip`: route, `cast_lock.cast`, keyframe_gate `required_cast_count` and clip_qa known classes all come from the same sheet. Removing one cast member from the sheet changes all four.
  - `test_cast_mismatch_anywhere_fails`.
  - `test_three_consumers_same_offsets`: build_final_reel offsets, render_controller Gate D seconds and the cue_sheet shot start_s are equal (**0.0, 7.0, 12.0**).
  - `test_same_gate_d_verdict`.
  - `test_stale_lock_blocks_all_three`.
- **Closes:** proves 3, 6, 21, 27 wiring. Rule 22 per new story.
- **Depends on:** X-04, X-05, X-10, X-13, X-14, X-15, X-19.
- **Collision:** none.
- **Acceptance:** `python -m pytest director/test_e2e_blocking_lock.py -q`
- **OWNER DECISION:** none.
- **Second-attempt risk:** med.

---

## Per-problem closure map (all parts)

Abbreviations for jobs in other parts (described by file + function):
- **LOCKW**: lock writer CLI + timeline_lock_core.plan_shots (snap flag, trims from v4_to_h3._plan_handles, needed_sec input, versioned lock).
- **VOX**: voice_cast.py run/export (voices check, pilot.json, require_wav, no atempo).
- **VOT**: build_vo_tracks.py (reads the lock, MAX_TEMPO 1.0).
- **RUN**: run_colab_batch.py after D-J8 (runner_safety preflight 7 MB, URLs/wheel, G4, clip_verified, stop, canary proof, render_ready).
- **PROMPT**: v4_to_h3:160 + compile_h3_sing8 + schema_and_linter.
- **J8**: git port.

`[rule/owner]` marks problems closed only by a rule or an owner decision.

| # | Closing card(s) | Single proving check |
|---|---|---|
| 1 | X-13 + RUN (`--go` needs render_ready.json) | `test_plan_pipeline_no_lock_blocks` |
| 2 | LOCKW + VOT | VOT test: every lock shot packs with max_tempo 1.0 without raising |
| 3 | LOCKW, VOT, X-15, X-19, X-04 | `test_three_consumers_same_offsets` (X-24) |
| 4 | LOCKW (trims from `_plan_handles`) | LOCKW test: `_plan_handles` problems == [] for every lock shot |
| 5 | LOCKW (snap flag, error_ms) `[owner: accept ±½ frame]` | LOCKW test: max error_ms ≤ 20.84 on a 128/176 BPM plan |
| 6 | X-12, X-13, X-15, X-19 | `test_same_gate_d_verdict` (X-24) |
| 7 | LOCKW (WAVs in lock inputs) | changing one WAV byte raises StaleLockError (`test_stale_lock_blocks_all_three`) |
| 8 | LOCKW (script in inputs) + X-13 | `test_stale_script_byte_blocks` |
| 9 | VOX (GET /v1/voices before reserve) | VOX test: missing voice → SystemExit, 0 POST |
| 10 | `[rule]` (Granth library copied) | none needed (rule 35) |
| 11 | VOX pilot.json + pronunciation_ok `[owner listens]` | VOX test: unflagged hard-name line is a problem |
| 12 | VOX require_wav | VOX test: a .wav holding MP3 bytes raises |
| 13 | VOX (no atempo, audio_edge before the lock) | VOX test: exported duration == trimmed duration |
| 14 | X-16 | `test_unapproved_caption_diff_raises` + `test_no_caption_fixes_symbol` |
| 15 | X-07 (writer_gate.json) + VOX (refuse without PASS) | `test_writer_gate_written_and_blocks_on_lint` |
| 16 | X-08 `[owner defines pass]` | `test_cast_without_ref_fails` |
| 17 | `[rule 19]` | none needed (existing STYLE-01/02 tests) |
| 18 | X-06, X-07 | `test_repair_only_named_shots` |
| 19 | X-15 (required --reel) + X-24 (reel-2 fixture) | `test_reel_required` |
| 20 | X-09, X-10 | `test_b_is_edit_of_a` + `test_background_moved_fails` |
| 21 | X-02, X-03, X-10, X-11 `[owner: manual review vs detector]` | `test_missing_sage_fails` |
| 22 | `[rule 25]` + X-10 (full_size required) | `test_not_full_size_refused` |
| 23 | `[rule 26]` + X-09 (complete job) | `test_job_keys_match_build_jobs` |
| 24 | `[owner: watermark tool]`; then flow/scripts/remove_sparkle.py / lama_inpaint.py exit non-zero on no input (other part) | owner decision recorded |
| 25 | X-10, X-11, X-13 | `test_missing_gate_b_blocks` |
| 26 | PROMPT `[owner: SX-01]` | PROMPT test: cue "a veil snaps" gives no "with a veil" |
| 27 | X-02 (L08), X-05, PROMPT (check_sound_cue in the compiler) | `test_serpents_hiss_fails` |
| 28 | PROMPT `[owner: mouth wording]`; X-05 supplies speaking | `test_cast_lock_equals_prompt_args` + the PROMPT mouth test |
| 29 | RUN (max_script_mb 7) + X-23 (R28) | RUN test: an 11.3 MB script fails preflight |
| 30 | PROMPT (single `\n`) + J8 (builder raise survives) | PROMPT test: no compiled prompt contains `"\n\n"` |
| 31 | `[rule 29]` + RUN clip_verified(expected_frames) | RUN test: truncated mp4 is not verified |
| 32 | RUN (stop on ALL DONE, argv lists) | RUN test: fake colab, all verified → stop issued |
| 33 | RUN (preflight URLs + wheel sha) | RUN test: fake HEAD 504 → failure |
| 34 | RUN (refuse non-G4; survives J8) | RUN test: "A100" refused |
| 35 | RUN (canary proof) + X-13 (render_ready) | `test_render_ready_written_only_when_clean` |
| 36 | J8 | both files exist in the merge tree and their suites pass |
| 37 | X-14, X-15 (+ D-CLIP) | `test_snake_not_known_blocks` |
| 38 | `[rules 44, 48]` | none needed |
| 39 | X-19 (+ LOCKW bpm/snap/act) | `test_stale_wav_exit_2` |
| 40 | X-14, X-17, X-18 `[rule 50(6) decided]` | `test_bed_louder_than_voice_minus_22_fails` |
| 41 | `[rule 51]` + X-16 + X-23 | `test_export_probes_1080x1920` |
| 42 | X-20 `[owner confirms audition-only]` | `test_only_audition_constant_is_minus_14` |
| 43 | X-23 `[owner approves texts]` | the two blot.md copies are byte-identical |
| 44 | X-21, X-22 `[rule 20; partial]` | `test_precommit_blocks_staged_key` (a control character or syntax error blocks the same way) |
| 45 | X-17 (local free-space check) + RUN (min_free_gb) `[owner: Drive access, disk numbers]` | `test_low_disk_refused` |
| 46 | X-06, X-21, X-22 `[owner rotates keys]` | `test_elevenlabs_key_found` + `test_prepush_fails_on_failing_test` |

**Run order inside P3:**
- Wave 1, all parallel: X-01, X-06, X-08, X-12, X-20, X-21.
- Then X-02 and X-03.
- Then X-04, X-09, X-10, X-14, X-19, X-22.
- Then X-11, X-13, X-15.
- Then X-16, then X-17, then X-18.
- X-05 and X-07 run after their other-part collisions.
- Then X-24, then X-23.

Every card waits for the owner's go.
