

# BATCH r7_caption_text (supervl) 11-07 13:29

Reviewing only the two files provided.

`caption_text.py`: The cluster/run logic is internally consistent (round‑trip preserved, leading/trailing "other" handled via `pending`, virama/mark joining matches the corpus tests). The cmap parser (format 4/12) uses correct offsets (`segCountX2` at `off+6`, `endCount` at `off+14`, pad before `startCount`, idRangeOffset relative to its own entry) and every struct access is wrapped so malformed fonts yield an empty set rather than a crash. `measure`, `wrap_lines`, `fit_text`, and `_fallback_build` all guard non‑string/junk input, never raise on bad fonts (cache `None`, fallback widths), and `fit_text` correctly floors at `min_size_px` and emits a single CAP‑WRAP FAIL when nothing fits. No logic errors, spec violations, or trust‑boundary crashes found.

`test_caption_text.py`: Tests exercise real behavior (font presence, missing file, junk bytes, narrow/wrap/fail cases). The random cluster test and `shaping_engine` test are weak/tautological but they do not assert false positives and cannot mask a real failure, so they are not a defect category here.

No findings for either file.

FINAL: no real defects found


# BATCH r7_caption_export (supervl) 11-07 13:31

medium, core/caption_export.py:230-236, `karaoke_text` word mode builds `bounds` from each *following* word's start offset (it skips `words[0]`), so the first `{\k}` is the next word's start time instead of that word's own duration and the last word gets `end − start` instead of its duration. Example: `karaoke_text([{"text":"Hi","t0":0.0,"t1":0.2,"conf":0.9},{"text":"yo","t0":0.3,"t1":0.5,"conf":0.9}], line_t0=0.0, line_t1=0.5)` returns `{\k30}Hi {\k20}yo`; correct is `{\k20}Hi {\k20}yo`. Fix: build `bounds` as cumulative per-word centisecond durations (`t1 − t0`) so each `{\k}` equals its own word's duration.

low, test_caption_export.py:173-178, `test_karaoke_word_mode_centiseconds_sum_to_line_duration` asserts the buggy output (`{\k30}Hi {\k20}yo`) and that k-values sum to the line duration (50), so it locks in the wrong timing and would fail against a correct fix. Fix: expect `{\k20}Hi {\k20}yo` (sum 40).

FINAL:
- medium, core/caption_export.py:230-236 — karaoke word-mode `{\k}` timings are wrong (first word gets the next word's start offset); build bounds as cumulative per-word durations.
- low, test_caption_export.py:173-178 — test asserts the buggy karaoke output/sum, blocking a correct fix.


# BATCH r7_captions_integration (supervl) 11-07 13:32

Reasoning: I reviewed the three provided files. `post.py` is defensive throughout: `run_post` traps all exceptions, `_shot_facts` handles a non-dict/missing `timing_and_lattice`, the fps/clip/loudness checks bail cleanly, the dry-run path skips ffmpeg, and the refuse gate runs after all final gates. I found no confirmable defect in `post.py` from the code given. `test_captions_integration.py` has assertions that depend on unseen modules (`fit_text`, `karaoke_text`, `load_core` templates) and font presence, so I could not confirm a "cannot-fail" test or a broken assertion there.

In `captions.py` there is one confirmable logic/spec defect: the horizontal caption position. With `\an5` the `\pos` x is the text centre, and `text_w = W − 2·margin` is the wrap width, so to respect the side margins the centre must be `W/2`. Instead `x = round((W − right·W)/2)` = `W/2 − margin/2`, shifting every caption left by half a side margin and letting a full-width line overflow the left side (owner spec: sides 160; e.g. W=1080, margin=160 → text spans [80,840] instead of [160,920]).

- medium | captions.py:317 | `\an5` caption is centred at `W/2 − margin/2` instead of `W/2`, so wrapped lines overflow the left side margin, violating the "sides 160" spec (e.g. 1080p text spans [80,840] rather than [160,920]). | Fix: replace `x = round((W - right * W) / 2)` with `x = W // 2`.

post.py: no findings. test_captions_integration.py: no confirmed findings (several assertions are unverified because they depend on unseen `fit_text`/`karaoke_text`/core config and font availability).

FINAL: medium, captions.py:317, caption x-position uses `round((W - right * W) / 2)` (off by margin/2) instead of centring at `W // 2`, overflowing the side margin; fix `x = W // 2`.


# BATCH r7_calibrate (supervl) 11-07 13:46

Reasoning: Both files are narrow utilities, so the surface for regressions is small. `calibrate_sat_ceiling.py` handles the CLI, nearest-rank math, regex replacement, and JSON round-trip correctly. The real defects are contract violations: `calibrate` promises `ValueError` for an unreadable file but only converts `RuntimeError`, so `OSError` escapes; `write_ceiling` promises formatting is kept but forces `\n` line endings; and the percentile validator accepts `bool` because `bool` subclasses `int`. In the test file, `ROOT = ...parents[2]` is likely an off-by-one path that breaks imports and fixture copies in standard layouts, and the PNG-based calibration test may not match what `per_frame_stats` expects (unverified).

medium, calibrate_sat_ceiling.py:41 — `calibrate` only wraps `RuntimeError` from `per_frame_stats` into `ValueError`; an unreadable file raises `OSError` (e.g. `PermissionError`) as a raw traceback, violating the docstring ("ValueError on ... an unreadable file") and crashing direct callers. Concrete input: pass a mode-000 file, or delete it between the `is_file()` check and `per_frame_stats`. Fix: change `except RuntimeError as exc:` to `except (RuntimeError, OSError) as exc:`.

low, calibrate_sat_ceiling.py:57 — `write_text(..., newline="\n")` rewrites line endings to LF, breaking the docstring promise that file formatting is kept when `core.json` uses CRLF. Concrete input: a CRLF `core.json`; after `write_ceiling`, all line endings become LF. Fix: remove `newline="\n"` to preserve original newlines.

low, calibrate_sat_ceiling.py:33 — `isinstance(pct, (int, float))` accepts `bool` (a subclass of `int`), so `calibrate([...], True)` is silently treated as `pct=1` instead of being rejected. Concrete input: `cal.calibrate([ref], True)`. Fix: add `and not isinstance(pct, bool)` to the percentile validation.

medium (unverified), test_calibrate_sat_ceiling.py:12 — `ROOT = Path(__file__).resolve().parents[2]` is likely an off-by-one; in a standard repo-root or `tests/` layout it resolves above the project, so `ROOT / "tools"` and `ROOT / "core" / "core.json"` do not exist and tests error on import/copy. Concrete input: run `pytest test_calibrate_sat_ceiling.py`. Fix: change `parents[2]` to `parents[1]` (if under `tests/`) or `parents[0]` (if at repo root).

low (unverified), test_calibrate_sat_ceiling.py:36 — `test_calibrate_matches_the_measured_frames` feeds PNG files to `per_frame_stats`; if that helper requires a video container, the test errors instead of validating ceiling logic. Concrete input: run the test with ffmpeg present but `per_frame_stats` unable to probe a PNG. Fix: generate a tiny ffmpeg `lavfi` video instead of PNGs, or skip when images are rejected.

FINAL:
medium calibrate_sat_ceiling.py:41 — `calibrate` lets `OSError` from an unreadable file escape instead of converting to `ValueError`; catch `(RuntimeError, OSError)`.
low calibrate_sat_ceiling.py:57 — `write_text(newline="\n")` rewrites CRLF to LF despite promising to keep formatting; drop `newline="\n"`.
low calibrate_sat_ceiling.py:33 — percentile validator accepts `bool`; exclude `bool` explicitly.
medium (unverified) test_calibrate_sat_ceiling.py:12 — `parents[2]` likely resolves to the wrong directory and breaks test imports/copies; adjust to `parents[1]` or `parents[0]`.
low (unverified) test_calibrate_sat_ceiling.py:36 — PNG inputs may not be valid for `per_frame_stats`, making the calibration test error rather than validate; use a tiny ffmpeg video instead.
