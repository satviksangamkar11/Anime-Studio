

# BATCH r8_cue_layer (supervl) 11-07 15:53

=== FILE caption_cues.py ===

- high, caption_cues.py:69 — `cap = (trk.get("captions_by_lang") or {}).get(lang)` crashes with `AttributeError` when `captions_by_lang` is present but not a dict (e.g. a list or string in a malformed pack), because `or {}` keeps a truthy non-dict and `.get()` is called on it. This is a trust-boundary crash on untrusted pack data.
  Fix: `cb = trk.get("captions_by_lang"); cap = cb.get(lang) if isinstance(cb, dict) else None`

- high, caption_cues.py:77 — `dia` from `lang_track` can be a non-list truthy value (e.g. `dialogue_by_lang[lang]` is a string); `or []` does not replace it, so the comprehension calls `.get()` on a character and raises `AttributeError`.
  Fix: in `lang_track`, return `dbl.get(lang) if isinstance(dbl.get(lang), list) else []` (or guard `dia = dia if isinstance(dia, list) else []` before line 77).

- medium, caption_cues.py:114 — `build_cue_list` assumes every spoken cue is a dict with numeric `t0`/`t1`; malformed cues passed to this public function raise `KeyError`/`TypeError` instead of being skipped or rejected cleanly.
  Fix: validate each cue (dict with numeric `t0` and `t1`) before sorting and skip invalid ones.

=== FILE test_caption_cues.py ===

no findings

FINAL:
1. high, caption_cues.py:69 — `captions_by_lang` non-dict truthy value causes `AttributeError` on `.get(lang)`; coerce to dict only when it is a dict.
2. high, caption_cues.py:77 — `dialogue_by_lang[lang]` non-list truthy value causes `AttributeError` on `d.get()`; coerce to `[]` unless it is a list.
3. medium, caption_cues.py:114 — `build_cue_list` crashes on spoken cues missing `t0`/`t1`; validate and skip malformed cues before sorting.


# BATCH r8_engine (supervl) 11-07 15:54

Reasoning: I reviewed `captions.py` and `test_captions_engine.py`. The caption engine is defensive (never raises, validates cues/dims/core, sanitizes karaoke emphasis/words, dedupes entries) and matches the owner constraints (no ffmpeg/ElevenLabs/model calls here, deterministic output). The test file contains real, non-tautological assertions and no "cannot fail" tests. The one concrete defect is the horizontal caption anchor: `x` is computed as `(W − margin)/2` instead of `W/2`. With `\an5\pos` the text is centered exactly on `x`, so the whole block shifts left by half a side margin and can overflow the configured side margin even though wrapping is clamped to `text_w = W − 2·margin` (spec: sides 160).

- severity: medium
- file: captions.py:347
- why: `x = round((W - right * W) / 2)` places the caption anchor at `(W − sideMargin)/2` rather than the horizontal center `W/2`, shifting captions left and risking left side-margin overflow (spec violation: sides 160).
- one-line fix: `x = round(W / 2)`

test_captions_engine.py: no findings.

FINAL: medium, captions.py:347 — caption horizontal anchor uses `(W − margin)/2` instead of `W/2`, shifting captions left and risking side-margin overflow; set `x = round(W / 2)`.


# BATCH r8_post_voice (supervl) 11-07 16:00

post.py: no findings

The file is defensive at trust boundaries: non-dict/missing shot fields are coerced and validated (`_shot_facts`), `timing_and_lattice` and `metadata.look` are type-checked, impact frames are validated, clip paths are made relative to `post/` with `ValueError` handling, ffmpeg probe/encode/flash/seam failures are caught and turned into FAIL entries rather than tracebacks, and the dry-run path starts no subprocess and writes no file. Voice resolution (`voice_arg or story voice_engine[lang]`, default elevenlabs; H3 refused for hi/mr per VE-01), the missing-voice-file refusal that names the file and never falls back to H3 audio, the single-graph voice mix (sidechaincompress + loudnorm) ducked under the H3 SFX bed, caption script validation, ungraded warning with `graded: false` in `colour_report.json`, and sidecar writing all match the owner brief. No regressions, logic errors, or contract mismatches are present.

test_post_voice.py: no findings

Each test carries real, falsifiable assertions (voice engine, vo file list, graph contents, `-i` count, refusal behavior, ordering of steps, loudness measurement, graded flag). None are vacuous or always-passing; they depend on actual `run_post` output and ffmpeg.

FINAL: no real defects found


# BATCH r8_gate_d (supervl) 11-07 16:05

gate_d_audio.py:112 — medium — `check_narration_density` prorates words with `n * _overlap(s, e, 0.0, win) / (e - s)`. A zero-duration speech interval (`e == s`, e.g. narration `time_range: "3-3"`) divides by zero and raises `ZeroDivisionError`. That exception is not in the handler at line 702 (`ValueError, KeyError, TypeError, AttributeError`), so it escapes `plan_language_outputs` and crashes every language instead of being reported. Failing input: a shot with narration text and `time_range: "3-3"` plus a positive `editorial_duration_sec`, `narration_driven=True`. Fix: `words = sum(n * _overlap(s, e, 0.0, win) / (e - s) for s, e, n in items if e > s)`.

gate_d_audio.py:686 — medium — the `TIME-01` fix is incomplete: `same_timing_problems` calls `parse_time_range` on caller-supplied `time_range` values (line 739), but the `except` only catches `ValueError` and `AttributeError`. A non-string `time_range` (e.g. an int or a list) raises `TypeError` from `parse_time_range`, which is not caught, so `plan_language_outputs` crashes for all languages rather than isolating the bad one. Failing input: `narration_by_lang: {"hi": {"time_range": 5}}` or `{"time_range": [1, 2]}` on any shot. Fix: `except (ValueError, TypeError, AttributeError) as exc:`.

test_gate_d_captions.py — no findings (the tests make real assertions; caption margin spec compliance delegates to `core/captions.py`, which was not provided, so that is unverified).

FINAL:
- gate_d_audio.py:112 — `ZeroDivisionError` on a zero-duration speech interval in `check_narration_density`, uncaught (absent from the line-702 except tuple), crashes all languages; fix: `for s, e, n in items if e > s`.
- gate_d_audio.py:686 — `TIME-01` fix incomplete: the line-686 `except` omits `TypeError`, so a non-string `time_range` from `parse_time_range` crashes `plan_language_outputs` for every language; fix: add `TypeError` to the except tuple.
