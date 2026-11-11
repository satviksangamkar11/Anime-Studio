# Nemotron ultra review of the 16 new tools (2026-11-10)

## director/timeline_lock_core.py
NO_REVIEW (OK)

## director/timeline_lock_io.py
CLOSURE:
1: NOT — module only provides a data contract; it does not enforce render-before-voices workflow.
3: PARTLY — establishes a single timeline lock (frames+fps) but the writer time_range, H3 lattice, voice windows, editorial_by_lang, and beat grid must be wired to read/obey this lock.
6: PARTLY — defines one authoritative clock (total_frames, fps, total_seconds) but render controller and reel builder must be wired to consume this lock instead of their current clocks.
39: CLOSED-BY-MODULE — `verify_lock` detects stale locks via input hash and path-set mismatch; cue sheet builder can call it and read authoritative lengths from the lock.

BUGS:
- `if type(fps) is not int or fps <= 0:` (write_lock) -> rejects valid int subclasses (e.g. numpy.int64) and crashes on good input -> `if not isinstance(fps, int) or isinstance(fps, bool) or fps <= 0:`
- `if type(edit_frames) is not int or edit_frames <= 0:` (write_lock, two occurrences) -> same -> `

## director/wav_contract.py
CLOSURE: 12: PARTLY (needs wiring into audio ingest/export pipeline to call require_wav on written files) 13: PARTLY (needs wiring into export writer and track builder to use wav_name/plan_names/find_voice instead of ad-hoc naming)
BUGS: NONE
VERDICT: READY

## director/caption_fields.py
NO_REVIEW (OK)

## h3/prompt_hygiene.py
CLOSURE:
26: PARTLY – detects duplicate sentences and cue-glue (raises error), but does not auto-remove cue-glue; “at seconds 7”, pronoun clashes, jargon untouched. Needs wiring into converter to handle/remove cue-glue.
27: CLOSED-BY-MODULE – `check_sound_cue` implements the lint; `cast_line` emits “Only … appear; no extra figures or creatures.”
28: CLOSED-BY-MODULE – `mouth_sentence` produces unambiguous per-person mouth/lips lines for any on-screen group.

BUGS:
1. `clean_prompt`: `cast = cast_line(cast)` shadows the `cast` list parameter with a string. Later code expects the original list (none here, but fragile). Fix: rename to `cast_str = cast_line(cast)` and use `cast_str` in the two `replace`/filter lines.
2. `clean_prompt`: `text = text.replace(mouth, "").replace(cast, "")` uses bare string replacement; if `mouth`/`cast` appear as substrings inside other sentences, it corrupts the prompt (e.g., “Alice speaks with moving lips and gestures” → “ and gestures”). Fix: remove by line identity or regex with word boundaries, not substring replace.
3. `remove_duplicate_sentences`: calls `split_sentences(line)` twice per loop (inefficient, not a functional bug but wasteful). Fix: store `sents = split_sentences(line)` once and reuse.

VERDICT: FIX-FIRST

## h3/shot_mode.py
CLOSURE: 20: PARTLY — module provides "S" (start-only) mode validation enabling "B as edit of A" workflow, but the actual generation logic that makes B an edit of A is not in this module; needs wiring into the image generation script that consumes these rows.

BUGS: NONE

VERDICT: READY

## director/runner_safety.py
CLOSURE:
29: PARTLY (preflight has script size gate via max_script_mb param, but default 12 MB ≠ required 3 MB; needs wiring with max_script_mb=3.0)
30: NOT (prompt blank-line validation absent; problem states fix lives in batch builder)
32: PARTLY (stop_decision/can_stop enforce clip verification before stop; _valid_shot_id blocks space-splitting; but runner must call these — not wired)
33: PARTLY (preflight does HEAD URL checks; but not yet wired as mandatory pre-flight gate)
35: PARTLY (preflight can gate on script size + URL reachability; but not wired to block render start)

BUGS:
`if len(expected_ids) == 0: raise ValueError("expected_ids must not be empty")` in can_stop -> rejects valid zero-shot batch (should stop immediately) -> change to `if len(expected_ids) == 0: return (True, [])`

VERDICT: FIX-FIRST

## tools/precommit_check.py
CLOSURE:
43: NOT — module does not address log/doc reliability, rule conflicts, or duplicate rule numbers.
44: NOT — module does not fix heredoc/backslash corruption; it only scans files statically.
46: PARTLY — detects secrets in staged files (HF, OpenRouter, NVIDIA, generic sk-), but does not monitor key expiration, prevent chat pastes, verify agent claims, or unmask failing tests. Needs wiring into `.pre-commit-config.yaml` to run on every commit.

BUGS:
1. `result = subprocess.run(["git", "diff", "--cached", "--name-only", "--diff-filter=ACMR"], capture_output=True, text=True, check=True)` -> crashes with `CalledProcessError` if git fails (not a repo, git missing, etc.) instead of returning a clean error code. Fix: wrap in try/except and return non-zero with message.
2. `except SyntaxError as exc:` in `check_python` -> misses `ValueError` (e.g., null bytes in source) and `MemoryError` from `ast.parse`, causing unhandled exceptions. Fix: `except (SyntaxError, ValueError, MemoryError) as exc:`.
3. `except OSError:` in `check_file` -> reports "missing file" for permission errors, disk full, etc. Fix: `except FileNotFoundError:` for missing; re-raise or report actual error for others.

VERDICT: FIX-FIRST

## director/script_hook.py
CLOSURE:
15: PARTLY — Module implements H1–H6 checks (including H3 stakes/question), but problem states "only partly wired into the writer"; `inspect_hook` exists but integration into writer pipeline is not shown.
16: NOT — Module validates script structure/hooks; no source-fidelity check (render vs. script comparison) is implemented.

BUGS:
1. `_has_stakes` returns True for any line containing "?" or "？" -> conflates stakes with questions; a pure question passes as stakes. H3 already calls `_has_question` separately. -> Remove the question-mark check from `_has_stakes`; keep only stakes-word/phrase matching.
2. `_has_concrete_subject` uses `stripped[0].isupper()` -> `isupper()` is always False for Devanagari (hi/mr), so capitalized-proper-noun detection never works for those languages. -> Skip capitalization check for hi/mr; rely on noun lists, or add script-aware detection.
3. `_validate_shots` does not verify `events` and `lines` are non-empty lists -> `inspect_hook` silently passes H2–H5 when `lines == []` (empty list is falsy, guards skip all checks). -> In `_validate_shots`, assert `isinstance(shot["lines"], list) and len(shot["lines"]) > 0` (same for `events` if at least one event is required).
4. `inspect_hook` treats missing/empty `lines` as passing -> With `lines == []`, H2–H5 `*_ok` stay True, score unchanged, reel passes hook check despite no spoken line. -> Add explicit `if not lines: hard_fails.append("H2: no spoken lines in first shot"); score -= 40` (and similar for H3–H5) before per-line checks.

VERDICT: FIX-FIRST

## director/script_pacing.py
CLOSURE: 15: PARTLY (pacing checks implemented but not wired into writer; seam/mouth checks absent) / 16: NOT (this validates script pacing, not source-fidelity of rendered output)

BUGS: 
- `for line in lines[1:]:` with `prev_end = lines[0]["end_s"]` -> assumes lines sorted by start_s; unsorted input yields wrong gaps or negative gaps silently ignored -> sort lines by start_s first or validate order
- `line["start_s"]`, `line["end_s"]`, `event["t"]` accessed without validation -> KeyError on missing keys in line/event dicts -> validate required keys in each line/event or catch KeyError
- `float(shot["seconds"])` and similar -> no check for negative/non-numeric values; negative duration breaks P3 absolute_start logic and P2 payoff_start -> validate > 0
- `if index > 0 and lines:` skips dead-air-before-first-line check for shot 0 -> first shot can start with >2s silence unflagged; comment says "later shot" but reel-start silence is also dead air -> remove `index > 0` guard or add separate reel-start check
- dead-air checks only examine `lines`, ignore `events` -> shot with events but no lines (or gaps filled by events) falsely flagged -> include events in gap/first-line checks or document lines-only intent

VERDICT: FIX-FIRST

## director/script_inspect.py
CLOSURE:
15: PARTLY - Module provides hook+pacing inspection (inspect_script) but is not wired into the writer; writer must call inspect_script and block on failure.
16: NOT - Module does hook/pacing checks only; no source-fidelity verification (e.g., transcript-to-script alignment, evidence grounding) is implemented.

BUGS:
- `if not shots:` in inspect_script and main -> passes non-list iterables (e.g., non-empty string) which pass the emptiness check but crash downstream in script_hook/script_pacing -> add `if not isinstance(shots, list): raise ValueError("shots must be a list")` in inspect_script; in main, validate `isinstance(shots, list)` after extraction.
- `lang` parameter in `format_report(result, lang)` is unused (dead code) -> remove parameter or use it for localized strings.

VERDICT: FIX-FIRST

## director/audio_edge.py
CLOSURE: 12: NOT (module only reads WAV; cannot handle mislabeled .mp3 files). 40: NOT (module does edge detection/fades, not SFX/voice level policy or mix planning).

BUGS: 
- `apply_edges`: `f = first + pad_front; l = last + pad_front; ... if abs(y[f]) > 0.02: for k in range(n_in): y[f + k] *= k / n_in` -> fade-in starts at first non-zero sample instead of at sample 0 of the padded signal; fade-out ends at last non-zero sample instead of at final sample. Fix: apply fade-in from index 0 for n_in samples, fade-out from index len(y)-n_out for n_out samples.
- `apply_edges`: `idx = [i for i, v in enumerate(x) if v != 0.0]` -> after first call, faded edges become exactly 0.0, so second call sees a shorter non-zero region, adds more padding, and changes length. Fix: detect content region using a threshold (e.g., abs(v) > 1e-4) or track original content bounds separately to ensure idempotency.
- `apply_edges`: `n_in = min(int(round(fade_in_ms / 1000.0 * sr)), span)` (and n_out) -> if fade_ms is 0 or sr very low, n_in can be 0; loop skipped but division k/n_in would crash if loop ran. Fix: `n_in = max(1, min(int(round(fade_in_ms / 1000.0 * sr)), span))` (same for n_out).

VERDICT: FIX-FIRST

## director/image_gates.py
CLOSURE: 21: PARTLY (needs a per-shot check function that wires cast_parity, limb_parity, posture_matches, feasible_motion against a shot script) 25: NOT
BUGS: "if np.issubdtype(arr.dtype, np.floating): return arr.astype(np.float64) / 255.0" -> assumes floating point images are in [0,255]; if they are already in [0,1] this scales them down 255x, causing SSIM/L1 to produce wrong results silently -> fix: only scale integer types; for floating point, assume [0,1] and just cast to float64 (or check max value > 1.0 before scaling)
VERDICT: FIX-FIRST

## director/plate_composite.py
NO_REVIEW (OK)

## director/clip_gates.py
CLOSURE: 37: PARTLY — provides frame-by-frame gate functions (tail spike, end-frame similarity, scene cut, new object detection, flicker) but no automatic frame scan/orchestration; needs wiring into a clip processor script that extracts per-frame features (flow_p95, similarities, counts_by_frame, luma_frames) and calls these gates.

BUGS: NONE

VERDICT: READY

## director/shot_router.py
CLOSURE: 20: NOT (module only routes shots needing end-pose to use A/B keyframes; does not enforce "B as edit of A" consistency). 21: NOT (no per-shot script validation of keyframe content). 36: NOT (unrelated to drifted Colab scripts).

BUGS: 
- `for shot in shots:` -> assumes each shot has "id" and "features" keys; missing keys cause KeyError crash. Fix: add validation inside loop: `if not isinstance(shot, dict) or "id" not in shot or "features" not in shot: raise RouterError("shot structure")`.

VERDICT: FIX-FIRST
