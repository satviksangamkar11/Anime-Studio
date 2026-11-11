# Nemotron super review of the 16 new tools (2026-11-10)

## director/timeline_lock_core.py
NO_REVIEW (OK)

## director/timeline_lock_io.py
NO_REVIEW (OK)

## director/wav_contract.py
CLOSURE: 12 PARTLY (sniff_audio/require_wav can detect WAV content stored as .mp3, but nothing renames/converts those files or wires detection into an export/ingest script); 13 PARTLY (wav_name/find_voice/plan_names standardize <id>.<lang>.wav for reading/planning, but no export writer is shown to emit that name, and nothing addresses speed-in-place rewrite or timeline plan reading raw files)
BUGS: NONE
VERDICT: FIX-FIRST

## director/caption_fields.py
NO_REVIEW (OK)

## h3/prompt_hygiene.py
NO_REVIEW (OK)

## h3/shot_mode.py
CLOSURE: 20: NOT — the module only validates image_prompt_type and pixel_frames and builds frame rows; it contains no “B as an edit of A” rule, no image-content consistency check, and nothing addressing shot 8/shot 2 or Brahma pose disagreement.

BUGS: NONE

VERDICT: READY

## director/runner_safety.py
NO_REVIEW (OK)

## tools/precommit_check.py
NO_REVIEW (OK)

## director/script_hook.py
CLOSURE: 15: PARTLY — only H3 content (stakes/question) is checked; H3 timing, seam, and mouth checks are absent, and no writer wiring/call site is shown. 16: NOT — no source-fidelity or hash check exists in this module; it does not address the writer grading itself.

BUGS:
- `if "?" in line or "？" in line:\n            return True` inside `_has_stakes` -> Question punctuation is not a stakes indicator, so non-stakes lines are falsely approved -> Remove that early return from `_has_stakes`; stakes must come only from `STAKES_WORDS`.
- `for key in ("id", "seconds", "action", "events", "lines"):\n            if key not in shot:\n                raise ValueError("missing key: " + key)` -> Key presence alone lets bad types (e.g. `events: None`, `lines: "x"`, `action: 5`) pass validation and crash later -> Add type checks in `_validate_shots` for list/dict/str types before `inspect_hook` uses them.
- `for event in events:\n        if event.get("t", 0.0) <= 1.0:` -> Assumes every event is a dict; a non-dict event raises `AttributeError` -> Guard with `isinstance(event, dict)` or validate event elements in `_validate_shots`.
- `first_start = lines[0].get("start_s", 0.0)` -> Assumes `lines[0]` is a dict; a non-dict first line raises `AttributeError` -> Guard with `isinstance(lines[0], dict)` or validate line elements.
- `h6_ok = _has_concrete_subject(first.get("action", ""), lang)` -> A non-string `action` (e.g. `None` or `int`) crashes on `action.strip()` inside `_has_concrete_subject` -> Coerce with `str(first.get("action") or "")` or validate `action` is a string.

VERDICT: FIX-FIRST

## director/script_pacing.py
NO_REVIEW (OK)

## director/script_inspect.py
NO_REVIEW (OK)

## director/audio_edge.py
NO_REVIEW (OK)

## director/image_gates.py
NO_REVIEW (OK)

## director/plate_composite.py
NO_REVIEW (OK)

## director/clip_gates.py
NO_REVIEW (OK)

## director/shot_router.py
NO_REVIEW (OK)
