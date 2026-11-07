

# BATCH r5_h3 (dots) 11-07 12:03



I reviewed the four provided files against the owner spec and the round-2 fix list. Most of the round-2 fixes in these files look correctly applied (non-object `timing_and_lattice`/`episode_plan` are wrapped in `_run`/guarded; `same_timing_problems` catches bad ranges; empty `tracks == []` is treated as no-BGM in `_bgm_track`; reel id is sanitized; PLAN-01 per-language guard exists; default language `hi`; no ffmpeg/ElevenLabs calls). The UI/server/pipeline/h3_author/v4_to_h3/compile_h3_sing8 fixes are not present in what you sent, so I mark those unverified.

Real defects found:

1. **medium** — `gate_d_audio.py:239-241` (vs `:671-672`): `validate_bgm_manifest({"tracks": []})` returns `BGM_MANIFEST_EMPTY`, but the spec says "empty BGM tracks = no BGM", which `_bgm_track` already implements. The round-2 fix is incomplete: the public validator still rejects the explicit no-BGM marker, so a spec-conforming test on `validate_bgm_manifest`/`read_bgm_manifest` fails. Fix: return `{"ok": True, "errors": [], ...}` for a `{"tracks": []}` doc, consistent with `_bgm_track`.

2. **low** — `gate_d_audio.py:279-290`: `check_music_presence` is a trust boundary. `v >= speech_gate_db` raises `TypeError` if `voice_db` holds strings, and `sorted(bgm_db)` raises on mixed types; `math.isfinite` is never reached. Fix: guard with `_is_num(v) and _is_num(b)` in the comprehension and filter `bgm_db` before sorting.

3. **low** — `voice_manifest.py:46-57`: `voice_ids_for` reads the legacy `dialogue` field, not `dialogue_by_lang[lang]`, so for a multi-language track (which `narration_text` correctly handles via `narration_by_lang`) the speaker voice-id map comes back empty. Fix: use `dialogue_by_lang.get(lang) or []` when the track carries per-language maps.

4. **low** — `gate_d_audio.py:696-706`: `_plan_one_language` appends every shot with a present VO wav to `vo_fit_check`'s `existing` even when `editorial_duration_sec <= 0`; then `vo > ed - margin` is always true, emitting a spurious `VO_OVERFLOW_ERROR`. This also disagrees with `voice_manifest.build_manifest` (`voice_manifest.py:99-104`), which reports `VO_UNREADABLE` for the same case. Fix: only append to `existing` when `ed > 0`.

5. **low** — `render_controller.py:273-275, 305-307, 362-366`: `_num` and the `isinstance(pf, int)` guard do not exclude `bool`, so a bool `pixel_frames`/`editorial_frames` (already flagged by the linter as TM-02/PF-02) is still counted as 1 in `totals` frames/seconds and in the seconds estimate. Fix: use `isinstance(v, int) and not isinstance(v, bool)` in `_num` and the `secs` guard.

Unverified (files not provided): UI `app.js`/`pipeline.js` (X-UI header, loadStory array guard, Save-story pack scoping, loadDetail single-flight), `server.py` record_spend timing, episode sort on mixed types, `pipeline.py` zero/negative seconds → 0, `h3/router.py` ref lists (RF-03/non-dict keyframes), `compile_h3_sing8.compile_episode` exception wrapping, and the h3_author/v4_to_h3/voice_engine/director/pack_validator/run_registry/retry_policy fixes.

FINAL:
1. [medium] gate_d_audio.py:239-241 — `validate_bgm_manifest` errors on `{"tracks": []}`, contradicting the spec "empty BGM tracks = no BGM" that `_bgm_track` (:671) implements; make the empty-list case ok.
2. [low] gate_d_audio.py:279-290 — `check_music_presence` crashes on non-numeric `voice_db`/`bgm_db` at the trust boundary; filter with `_is_num` before compare/sort.
3. [low] voice_manifest.py:46-57 — `voice_ids_for` reads `dialogue` instead of `dialogue_by_lang[lang]`, losing speakers in multi-language tracks.
4. [low] gate_d_audio.py:696-706 — shots with `editorial_duration_sec <= 0` still enter `vo_fit_check`, yielding spurious `VO_OVERFLOW_ERROR` and a code mismatch with `voice_manifest`; guard with `ed > 0`.
5. [low] render_controller.py:273,305,362 — `_num`/`isinstance(pf, int)` do not exclude `bool`, so bool frame counts leak into totals; use `and not isinstance(v, bool)`.


# BATCH r5_ui (dots) 11-07 12:14



The round‑2 fixes were checked for correctness and regressions. Several new endpoints and pipeline functions were added without guarding against missing optional modules (h3, story_state, story_links). When those modules are absent the server returns 500 instead of a graceful error. Also, `read_pack` passes through non‑numeric seconds and `_manifest_status` crashes on a non‑dict manifest. The five most important real defects are listed below.

FINAL:
1. **high**, server.py:1453-1465 – `author_status` calls `_h3_author_module()` without catching `ImportError`. If the h3 engine is not built, GET /api/author/status returns 500 instead of an error. Click path: open the Author panel in the UI. Fix: wrap the call in try/except and return `{"error": H3_MISSING}` on `ImportError`.
2. **high**, server.py:1408-1418 – `pack_voices_set` calls `pl.write_voice_map`, which calls `_h3("voice_engine")` (pipeline.py:936). When h3 is missing, POST /api/pack/voices returns 500. Click path: save a voice map in the Voices panel. Fix: in `write_voice_map`, catch `ImportError` and return a problem message like `"h3 engine not built yet"`.
3. **high**, server.py:1325-1327 – `story_state` calls `_story_state_module()` without exception handling. If the `story_state` module is missing, GET /api/story/{slug}/state returns 500. Click path: load the story‑state page. Fix: catch `ImportError` and return an error dict.
4. **high**, server.py:797-806 – `_story_image_root` does `import story_links` with no try/except. When `story_links` is missing, GET /api/images crashes with


# BATCH r5_tests (dots) 11-07 12:18



### Findings

**1. Medium** — `test_bf_fixes.py` (ui) line 18‑29  
**What is wrong:** `test_row_seconds_bool_and_none_are_zero` creates a `Config` with `flow=studio.parent / "flow"` but never creates that directory or any files inside it. If `server.read_pack` touches the flow directory (e.g., to load a default config or validation schema) it will raise `FileNotFoundError` and the test fails.  
**Concrete failing input:** A studio directory that lacks a `flow` subdirectory.  
**One‑line fix:** Create the flow directory with the necessary files before calling `read_pack`, or mock the flow‑dependent parts of `read_pack`.

**2. Medium** — `test_bf_fixes.py` (ui) line 75‑88  
**What is wrong:** `test_unhashable_image_id_in_jsonl_does_not_raise` calls `pipeline.facts(studio_dir, runs)` without supplying a `Config` or ensuring the studio directory has the full required structure (e.g., a `flow` directory, proper `runs` layout). If `pipeline.facts` needs those pieces it will raise an exception.  
**Concrete failing input:** A studio directory missing required subdirectories or a `Config` object.  
**One‑line fix:** Set up a complete studio environment using the existing helpers, or pass a fully populated `Config` to `pipeline.facts`.

**3. Medium** — `pipeline.py` fix “zero or negative shot seconds count as 0” (tested indirectly by `test_row_seconds_bool_and_none_are_zero`, ui test line 18)  
**What is wrong:** The test only checks that `bool` and `None` seconds become 0; it never exercises zero or negative values. If the implementation silently converts negative seconds to 0 without emitting a validation error, it may violate the spec that requires validator errors to block Gate A.  
**Concrete failing input:** A shot with `editorial_duration_sec: -5`.  
**One‑line fix:** Add a test for negative seconds and ensure an error is reported, or adjust the fix to report an error for negative values.

**4. Low** — `test_bf_fixes.py` (h3) line 38  
**What is wrong:** `assert seen[1] == 0` assumes the story has at least two shots. If `build_story` ever returns a story with only one shot, `seen[1]` raises `IndexError` and the test fails spuriously.  
**Concrete failing input:** A story with a single shot.  
**One‑line fix:** Change to `assert seen[-1] == 0` or guard with `len(seen) >= 2`.

**5. Low** — `test_bf_fixes.py` (h3) line 86‑92  
**What is wrong:** `test_qc_result_attribute_error_blocks_instead_of_raising` only verifies that `AttributeError` is wrapped. The fix description states that `TypeError` and `ValueError` are also wrapped, but no tests cover them. If the wrapping logic fails for those exceptions, the suite will not catch it.  
**Concrete failing input:** A `final_qc` that raises `TypeError` or `ValueError`.  
**One‑line fix:** Add tests for `TypeError` and `ValueError` to confirm they are caught and reported as blocking reasons.

---

### Unverified (no concrete defect found, but lacking test coverage)
- `server.py` “episode sort on mixed types” – no test provided.  
- `run_registry` (h3 voice only for en, Marathi detection by u0933) – no test.  
- `render_controller` (default language hi) – no test.  
- `v4_to_h3` + `h3_author` (derive trim/handles/seams, author step with lint+repair, cache) – no test.  
- `gate_d_audio` (per‑language PLAN‑01 guard, empty BGM tracks = no BGM, reel id sanitized) – only TIME‑01 aspects are tested.  
- `write_pack` (shot id and episodes validation, key‑file and catalog‑unreachable errors, empty‑price model is NOT free, JSON decode error in answer_text, shared retry policy in call_path with ModelRefused) – only `envelope_check` is tested.  
- UI JavaScript fixes (`api()` X‑UI header, `loadStory` array guard, `Save‑story` pack scoping, `loadDetail` single‑flight with rerun) – no Python tests can cover these.

---

FINAL:  
1. Medium – `test_bf_fixes.py` (ui) line 18‑29: missing flow directory setup.  
2. Medium – `test_bf_fixes.py` (ui) line 75‑88: missing `pipeline.facts` setup.  
3. Medium – `pipeline.py` zero/negative seconds fix lacks test for negative values.  
4. Low – `test_bf_fixes.py` (h3) line 38: IndexError risk on single‑shot stories.  
5. Low – `test_bf_fixes.py` (h3) line 86‑92: incomplete coverage for TypeError/ValueError in `_qc_result`.
