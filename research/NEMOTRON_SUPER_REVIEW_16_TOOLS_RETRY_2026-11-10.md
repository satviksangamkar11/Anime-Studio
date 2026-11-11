# Nemotron super review of the 16 new tools (2026-11-10)

## director/timeline_lock_core.py
NO_REVIEW (OK)

## director/timeline_lock_io.py
CLOSURE: 1 NOT / 3 PARTLY (lock is a single timing contract but nothing retires or adjudicates time_range, H3 lattice, voice windows, editorial_by_lang, beat grid, or the tempo limits; needs wiring into a named timeline compiler/render controller) / 6 PARTLY (total_seconds is produced but Gate D, the render controller, and reel builder still use 70.0/70.8/72.833 and two verdicts; needs wiring to one clock) / 39 PARTLY (verify_lock can detect stale inputs but nothing calls it from the cue sheet builder or rebuilds on mismatch)

BUGS:
- `    recorded_total = lock.get("total_frames")\n    if type(recorded_total) is not int or recorded_total != total_frames:\n        raise ValueError("total_frames does not match sum of shot edit_frames")` -> `load_lock` never validates `total_seconds`, so a corrupt lock with a wrong/stale `total_seconds` passes and can be consumed by cue sheets/reel builders. -> After the total_frames check, add: `recorded_seconds = lock.get("total_seconds"); if not isinstance(recorded_seconds, (int, float)) or isinstance(recorded_seconds, bool) or recorded_seconds != round(total_frames / fps, 6): raise ValueError("total_seconds does not match total_frames / fps")`
- `        shot_id = shot.get("id")\n        edit_frames = shot.get("edit_frames")` -> `load_lock` reads `shot_id` but does not require it to be a string or unique (unlike `write_lock`), so missing/duplicate ids pass and `frames_for` then returns the first match silently. -> In the `load_lock` shot loop, require `isinstance(shot_id, str)` and track `seen_ids` to reject duplicates.

VERDICT: FIX-FIRST

## director/caption_fields.py
CLOSURE: 14: PARTLY (module supplies validation/resolution but does not remove or wire against the silent CAPTION_FIXES override; needs integration into the caption/voice pipeline)
BUGS: NONE
VERDICT: READY

## h3/prompt_hygiene.py
CLOSURE: 26: PARTLY (missing checks for time references like "at seconds N", pronoun clashes, and jargon; cue glue is detected/raised but not stripped, and wiring into the converter is not shown) / 27: CLOSED-BY-MODULE / 28: CLOSED-BY-MODULE
BUGS: NONE
VERDICT: READY

## director/runner_safety.py
CLOSURE: 29 PARTLY (script-size gate present but default 12 MB admits the 11.3 MB hung script; no 180 s proof or 3 MB upload-part logic); 30 NOT (no prompt/blank-line/batch-builder/compiler logic); 32 PARTLY (stop_decision can halt after ALL DONE once clips verified, but filename splitting on spaces, setup error text loss, and stray G4 are not addressed or wired into the runner); 33 PARTLY (preflight runs URL HEAD and disk checks but only returns failures; not shown enforced as a mandatory pre-flight gate that halts setup); 35 PARTLY (script-size pre-flight exists but is not wired as an enforced render-start gate; no full script/prompt read or one-shot proof check)
BUGS: NONE
VERDICT: FIX-FIRST

## tools/precommit_check.py
CLOSURE:
43: NOT — module does not address logs, docs, stale copies, rule 41/shot 7 conflict, or caption rule numbering.
44: NOT — no heredoc/backslash or human-error handling; generic syntax check may miss corrupted-but-valid Python and is not wired to the Edit-tool rule.
46: PARTLY — scans staged file contents for HF/OpenRouter/NVIDIA/generic `sk-` secrets, but does not address key expiry monitoring, agent “done” verification, failing tests hidden by wrapper, or chat paste outside staged files.

BUGS:
`    except SyntaxError as exc:\n        line = exc.lineno if exc.lineno is not None else 1` -> `ast.parse` raises `ValueError` (not `SyntaxError`) on NUL bytes, so `check_file` crashes instead of returning a finding -> `    except (SyntaxError, ValueError) as exc:\n        line = getattr(exc, "lineno", None)\n        line = line if line is not None else 1`
`_CONTROL_CHAR_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")` -> `\x7f` (DEL) is a control character but is not matched, contradicting the docstring and silently passing bad input -> `_CONTROL_CHAR_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")`

VERDICT: FIX-FIRST

## director/script_pacing.py
CLOSURE: 15: PARTLY — implements only timing/pacing checks; seam and mouth checks are missing, and the module is not wired into the writer (needs a call site in the writer script). 16: NOT — no source-fidelity or hash-check logic exists in this module.
BUGS: `if total < 60.0 or total > 75.0:` — comment states length is “not a hard fail,” yet it is appended to `problems` and therefore forces `"pass": False`, wrongly failing a reel that passes all other checks; exclude length from the pass gate (e.g., separate soft warnings) or amend the comment/return logic. `line_start = float(line["start_s"])` — only shot-level keys are validated, so a line/event missing nested keys (`start_s`, `end_s`, `t`) crashes with KeyError instead of returning a problem; validate nested keys up front or report them as problems.
VERDICT: FIX-FIRST

## director/script_inspect.py
CLOSURE: 15: NOT / 16: NOT
BUGS: `    if not shots:` in `main` -> accepts any non-empty JSON value as `shots` (e.g. a string or number), so invalid input passes validation and is forwarded to `script_hook`/`script_pacing`, causing a crash or wrong result -> replace with `    if not isinstance(shots, list) or not shots:`
VERDICT: FIX-FIRST

## director/audio_edge.py
CLOSURE: 12 NOT (no MP3 decoding; module only reads WAV). 40 NOT (no SFX/voice loudness policy or plan-ahead logic; only edge repair).

BUGS: `y[f + k] *= k / n_in` and `y[l - k] *= k / n_out` -> the fade divisor `n` caps the ramp at `(n-1)/n` instead of `1.0` at the boundary with un-faded audio, causing a step discontinuity and incorrect gain -> divide by `max(1, n_in - 1)` and `max(1, n_out - 1)` respectively.

VERDICT: FIX-FIRST

## director/image_gates.py
CLOSURE: 21: PARTLY (provides cast/limb/posture/motion primitives but no per-shot script consumer or approval wiring; needs wiring into a named shot-approval script); 25: NOT (no H3, boundary PNG, Gate B, or lint-order handling)
BUGS: `        return arr.astype(np.float64) / 255.0` (floating branch in `to_float01`) -> divides already-0-1 float images by 255, breaking SSIM/L1 scale and letting clearly different images pass `background_lock` silently -> `        return arr.astype(np.float64)` (treat floating input as already 0-1)
VERDICT: FIX-FIRST

## director/plate_composite.py
CLOSURE: 20: PARTLY (module implements the “B as an edit of A” rule but needs wiring into a named script/pipeline that calls plan()/composite() on the affected shots)
BUGS: NONE
VERDICT: READY

## director/clip_gates.py
CLOSURE: 37: PARTLY — adds frame-by-frame checks (tail flow spike, scene cuts, new object classes, flicker, end-frame vs keyframe) but does not measure audio at all, does not detect disappearing objects/lost arms, and has no automatic frame scanner; must be wired into a named frame-scanning script.

BUGS: `for i in range(after_frame, len(counts_by_frame)):` -> negative `after_frame` skips known-set construction and wraps `counts_by_frame[i]` to the end of the list, falsely reporting objects as new -> add `if after_frame < 0: raise ClipGateError("after_frame must be non-negative")` before the loops. `best_val = similarities[0]` -> non-finite/NaN similarities silently corrupt the max search and can return the first index regardless of valid data -> after the empty check add `if not np.all(np.isfinite(np.asarray(similarities, dtype=float))): raise ClipGateError("similarities has non-finite values")`.

VERDICT: FIX-FIRST

## director/shot_router.py
CLOSURE: 20: NOT / 21: NOT / 36: NOT
BUGS: `        reasons.append("more than 3 moving people")` -> It runs whenever `kind == "crowd"`, even when `cast_count <= 3`, so the reason can be factually false. -> Guard the append with `if cast_count > 3:`. `        shot_id = shot["id"]` -> `plan_reel` indexes `shot` without confirming it is a dict containing `"id"` and `"features"`, so malformed input crashes with `KeyError`/`TypeError` instead of `RouterError`. -> Validate each `shot` is a dict with `"id"` and `"features"` before accessing them, raising `RouterError` otherwise.
VERDICT: FIX-FIRST
