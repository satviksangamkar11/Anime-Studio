

# BATCH r7_caption_text (dots) 11-07 13:29



I only have two files to review (`caption_text.py` and `test_caption_text.py`). The many other files mentioned in the round-2 fix list were not provided, so I cannot check them.

## caption_text.py

**Low** — `caption_text.py:138` — `_parse_subtable` format-4 rangeOffset address includes an extra `2 * i` term. The spec says rangeOffset is measured from the beginning of the rangeOffset array, so the address should be `ranges_off + r + 2 * (c - s)`, not `ranges_off + 2 * i + r + 2 * (c - s)`. This is a pre-existing bug (not a round-2 regression) that only triggers for fonts with irregular segment mappings where rangeOffset ≠ 0; Devanagari fonts typically use delta-only segments (rangeOffset = 0) so tests pass.  
Fix: change `addr = ranges_off + 2 * i + r + 2 * (c - s)` to `addr = ranges_off + r + 2 * (c - s)`.

## test_caption_text.py

No findings — all tests have real assertions, can fail, and correctly exercise the module.

---

**Note:** The remaining files listed in the round-2 fix summary (app.js, pipeline.js, server.py, pipeline.py, h3 router.py, schema_and_linter.py, compile_h3_sing8.py, h3_author, v4_to_h3, voice_manifest, gate_d_audio, render_controller, voice_engine, director write_pack, pack_validator, run_registry, retry_policy) were not provided for review.

FINAL:
1. Low — caption_text.py:138 — format-4 rangeOffset address adds a spurious `2 * i` term; correct formula is `ranges_off + r + 2 * (c - s)`. Pre-existing, only affects fonts with non-zero rangeOffset segments.


# BATCH r7_caption_export (dots) 11-07 13:39



I only received two files this round (`caption_export.py`, `test_caption_export.py`). I reviewed both exhaustively; the remaining files named in the prompt were **not provided**, so I cannot verify them.

## caption_export.py — no findings
I traced every function against its tests: `_num`/`_ms`/`srt_time`/`vtt_time` (bool excluded, negatives→0, half-up ms rounding), `_clean_cues` (non-list, non-dict, NaN/inf t0/t1, t1≤t0, empty text, `latin` type guard all produce exactly one WARN each), `to_srt`/`to_vtt` (sort by (t0,t1), latin line appended, blank lines stripped, UTF-8, `\n` newlines), `write_sidecars` (stem `/`/`\` rejection, LANG_RE skip with WARN, makedirs, per-ext `continue` on OSError keeps the other sidecar), `words_from_elevenlabs` (nested alignment/normalized_alignment unwrap, length/type checks, whitespace word grouping, conf=1.0), `karaoke_text` (empty→phrase, all-strings→phrase/synthetic, `_first_problem` monotonic/conf/duration gates, centisecond bounds with `max()` monotonicity), `timing_error_stats` (nearest-rank p90, empty→None), `contact_sheet_plan` (positive-int w/h, filter-safe ass/font names, absolute png, relative `subtitles=` argv, misplaced-fontsdir WARN, duplicate/bad-id skip), `frame_hash`/`compare_frames`, and `ffmpeg_preflight` (TimeoutExpired/OSError/returncode paths). All match the codified tests; no logic errors, no crash paths at trust boundaries.

One item I checked and deliberately **did not** promote to a defect: `to_vtt` escapes `&` and `<` but not `>` (line 98). Whether the W3C WebVTT "escape a string" algorithm requires `&gt;` is ambiguous across references, and `test_to_vkt_exact_two_cues_and_escaping` explicitly codifies the current output, so per "say unverified when unsure" I leave it as a style question, not a confirmed bug.

## test_caption_export.py — no findings
Every test has a concrete, falsifiable assertion (exact SRT/VTT strings, exact argv lists, exact WARN/FAIL rule lists, hash equality, centisecond sums). No test is tautological; the `no_subprocess` fixture is only applied to plan-only tests that never invoke subprocess, so it cannot mask a real call. The one conditionally-skipped test (`test_ffmpeg_preflight_real_call_returns_only_preflight_entries`) guards on `shutil.which("ffmpeg")` correctly.

## Unverified (file contents not provided this round)
- `ui/static/app.js` (api() X-UI header, loadStory array guard)
- `pipeline.js` (rebuilt panels, next_step key/text, API timeout, chips)
- `server.py` (record_spend only after job starts, episode sort on mixed types, POST body pack, 127.0.0.1 binding, approvals scoped by story+pack, Gate A blocked on validator errors)
- `h3_router.py` (ref lists RF-03, non-dict keyframes)
- `schema_and_linter.py` (non-object timing_and_lattice, episode_plan, missing asset_root)
- `compile_h3_sing8.py` (compile_episode wraps TypeError/ValueError/AttributeError, episode-not-found, missing profile key)
- `pack_validator`, `write_pack`, `story_state`, `run_registry`, `gate_d_audio`, `render_controller`, `v4_to_h3`, `h3_author`, `voice_manifest`, `voice_engine`, `director`, `retry_policy` (all round-1/round-2 fixes)

FINAL:
1. (high, unverified) `server.py` — record_spend only-after-start + episode sort on mixed types + Gate A block-on-validator-errors: three independent trust-boundary behaviors, none checkable from this round's paste.
2. (high, unverified) `ui/static/app.js` api() X-UI-on-every-request + loadStory array guard: JS/server contract mismatch risk if the header is conditional.
3. (medium, unverified) `schema_and_linter.py` non-object timing_and_lattice / episode_plan: could crash or silently pass bad author input.
4. (medium, unverified) `compile_h3_sing8.py` compile_episode TypeError/ValueError/AttributeError wrapping: broad except may swallow real bugs or mask the wrong exception type.
5. (medium, unverified) `h3_router.py` RF-03 ref lists / non-dict keyframes: list-indexing on unvalidated refs can crash at render time.
No real defects found in the two files provided (`caption_export.py`, `test_caption_export.py`); the other ~18 files/fixes are unverified pending their contents.
