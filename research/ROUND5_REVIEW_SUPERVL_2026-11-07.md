

# BATCH r5_h3 (supervl) 11-07 12:03

Brief reasoning: I reviewed the four provided files for regressions, wrong/incomplete fixes, logic errors, spec violations, and trust-boundary crashes. The round-2 fixes in these files (asset_root report, episode_plan guard, non-object block handling, retry/single-flight guards, etc.) appear correctly applied. The real defects are all in `schema_and_linter.py` (`lint_story`/`lint_profile` crash on malformed story input instead of reporting rules) and one logic error in `gate_d_audio.py` (spurious `NO_VO_FILES`). `voice_manifest.py` and `render_controller.py` show no defects in the provided code. Files not provided (app.js, server.py, pipeline.js, pipeline.py, h3/*.py, etc.) could not be inspected and are unverified.

- medium, schema_and_linter.py:982, `lint_story` calls `compiled_map.get(sid)` with `sid = shot.get("shot_id")` before `lint_shot` validates the id; a non-hashable shot_id (JSON array) raises `TypeError: unhashable type` and crashes instead of reporting ID-01. Failing input: a shot with `"shot_id": [1, 2]`. Fix: `c = compiled_map.get(sid) if isinstance(sid, str) else None`.
- medium, schema_and_linter.py:942/949 (root cause lint_profile:411), `lint_story` does `prof = reg["execution_profile"]` (`KeyError` when missing) and passes it to `lint_profile`, which runs `set(profile)` (`TypeError` for `null`/int/bool) instead of reporting PO-03. `render_controller` guards this, but direct `lint_story`/`lint_profile` calls crash. Failing input: `{"registry": {}, "episodes": [...]}` or `"execution_profile": null`. Fix: `prof = reg.get("execution_profile")`; if not a dict, report PO-03 and return (also harden `lint_profile` against non-dicts).
- low, gate_d_audio.py:708, `_plan_one_language` raises `NO_VO_FILES` whenever `not h3_voice and not vo_files`, even when no shot has speech in that language (no VO is needed), a spurious blocker for speech-less/pure-Foley reels. Failing input: a pure-Foley reel with `languages=["hi"]`; `plan_language_outputs` reports `NO_VO_FILES` for hi. Fix: only raise `NO_VO_FILES` when at least one shot has speech in that language but no VO files exist.
- medium, schema_and_linter.py:980, `lint_story`'s duplicate shot_id scan calls `shot.get("shot_id", ...)` on every row; a non-dict shot row (JSON number) raises `AttributeError` and crashes. Failing input: `episodes[].shots = [42]`. Fix: `if not isinstance(shot, dict): continue` before `shot.get(...)`.

voice_manifest.py: no findings. render_controller.py: no findings.

FINAL:
- medium, schema_and_linter.py:982 — `lint_story` crashes `TypeError` on unhashable/non-string `shot_id` via `compiled_map.get(sid)` before ID-01 validation; input `"shot_id": [1, 2]`; fix `c = compiled_map.get(sid) if isinstance(sid, str) else None`.
- medium, schema_and_linter.py:942/949 — `lint_story` crashes `KeyError`/`TypeError` when `execution_profile` is missing or non-dict instead of reporting PO-03; input `{"registry": {}}` or `execution_profile: null`; fix `prof = reg.get("execution_profile")` and guard non-dict.
- low, gate_d_audio.py:708 — spurious `NO_VO_FILES` when a language has no speech (no VO needed); input pure-Foley reel with `languages=["hi"]`; fix only raise when speech exists but no VO files.
- medium, schema_and_linter.py:980 — `lint_story` crashes `AttributeError` on a non-dict shot row in the duplicate-ID scan; input `shots = [42]`; fix skip non-dict rows.
- (4 real defects found; no fifth in the provided files.)


# BATCH r5_ui (supervl) 11-07 12:12

medium, server.py:414, `scope_ids` builds `known = {s.get("id") for s in shots}`; a shot row whose `id` is a list/dict raises `TypeError: unhashable type` and crashes `run_kaggle_prepare` preview/run. Coerce ids to text: `known = {str(s.get("id")) for s in shots if s.get("id") is not None}`.

medium, server.py:1556, `export` builds `order = {sid: i for i, sid in enumerate(ids)}` from raw `s.get("id")` values; an unhashable shot id crashes the endpoint with `TypeError`. Use `str(sid)` as the key and match on `str(c["shot"])`.

medium, pipeline.py:391, `facts` inserts `dq_entries[(shot_id, version)] = entry` without coercing unhashable JSON values; a list/dict `shot_id` or `version` in the queue log raises `TypeError`. Coerce `shot_id`/`version` to `str` before using as a dict key.

medium, pipeline.py:408, `facts` adds `(img_id, ver)` to `fl_set` without coercing `ver`; a list/dict `version` in the flow log raises `TypeError` on `set.add`. Coerce `ver` to `str` when building `fl_set`.

medium, pipeline.py:412, `facts` tests `(entry["image_id"], entry["version"]) not in fl_set`; an unhashable `version` makes the tuple unhashable and raises `TypeError`. Store `version` as `str` in `dq_entries` (same coercion as line 388).

medium, pipeline.py:321 and pipeline.py:853, `gate_d_problems` and `_per_language` index `gd["reasons"]` directly; a plan step missing the `reasons` key raises `KeyError` and crashes Gate D validation / render status with a 500. Use `gd.get("reasons")`.

low, server.py:737, `read_pack` returns the raw `secs` value (possibly a string) in the shot row `seconds` field instead of normalizing to a number, inconsistent with the "zero or negative seconds count as 0" rule and the `num()`-based episode aggregation. Use `"seconds": 0 if isinstance(secs, bool) else max(0.0, num(secs))`.

low, server.py:861-864, 879, 896-898, `p.stat().st_size` can raise `FileNotFoundError` if a file is deleted between `glob()` and `stat()`, crashing image/video/clip listing. Wrap `stat()` in try/except and skip missing files.

unverified, ui/static/app.js and pipeline.js fixes (X-UI header, loadStory guard, Save-story pack scoping, loadDetail single-flight) were not provided in the files under review, so client-side correctness cannot be confirmed from server.py/pipeline.py alone.

FINAL:
1. server.py:414 — `scope_ids` set comprehension crashes on unhashable shot `id`; coerce to `str`.
2. server.py:1556 — `export` dict comprehension crashes on unhashable shot `id`; key on `str(sid)`.
3. pipeline.py:391/408/412 — `facts` crashes with `TypeError` when `shot_id`/`version` are unhashable in dict/set operations; coerce to `str`.
4. pipeline.py:321/853 — `gd["reasons"]` raises `KeyError` when a plan step lacks `reasons`; use `gd.get("reasons")`.
5. server.py:737 — `read_pack` leaves `seconds` as a raw string instead of a clamped number; normalize with `max(0.0, num(secs))`.


# BATCH r5_tests (supervl) 11-07 12:21

I reviewed the three `test_bf_fixes.py` blocks against the described round-2 fixes and the owner spec. Source files were not provided, so source-level `file:line` claims for `server.py`, `pipeline.py`, `h3/router.py`, etc. are marked unverified. The test files themselves contain concrete issues, and the described fixes have logical gaps that the tests do not cover.

Findings:

- **medium, test_bf_fixes.py:38** — `assert seen[1] == 0` assumes shot A contributes nothing to the running total, but `build_story` likely gives shot A a nonzero `editorial_duration_sec`. The assertion then measures total duration, not just bool-frame handling, so it can fail for the wrong reason or pass while the bool bug remains. Set shot A’s `editorial_duration_sec` to `0` and assert `seen[1] == seen[0]` (or that the delta is `0`).
- **medium, test_bf_fixes.py:51** — `assert api.run(...) == {"job_id": "job1"}` uses exact dict equality on the success path. If the server returns extra keys (e.g. `spend_recorded`), the test errors instead of asserting the intended behavior. Assert `res["job_id"] == "job1"` only.
- **high, server.py:? (unverified)** — “episode sort on mixed types” can raise `TypeError` in Python 3 when episode IDs mix `int` and `str`, because default ordering is not supported across types. Sort with `key=str` (or normalize IDs) before sorting.
- **high, pipeline.py:? (unverified)** — “zero or negative shot seconds count as 0” does not cover `bool`. Since `bool` is a subclass of `int`, `True` compares as `1` and would survive a `<= 0` clamp, contradicting the UI test that expects `True` → `0`. Explicitly reject non-numeric/bool values and coerce them to `0`.
- **medium, h3/gate_d_audio.py:? (unverified)** — `_lang_track` treats non-object `narration_by_lang` as missing `(None, [])` (test line 71), but `same_timing_problems` flags the identical non-object input as `TIME-01` (test line 76). Inconsistent handling of the same trust-boundary input; make both treat non-object tracks as missing or both as timing errors.
- **medium, h3/router.py:? (unverified)** — “ref lists (RF-03, non-dict keyframes)” has no test coverage. If a keyframe is not a dict, downstream code calling `.get()` or subscripting will crash; validate that each keyframe is a dict before access.
- **low, test_bf_fixes.py:66** — `lint_story(story, compiled=["not", "a", "map"])` will raise `TypeError` if `lint_story` does not accept a `compiled` parameter, erroring out instead of producing a clean assertion failure. Verify the signature before asserting on the error list.

FINAL:
1. medium, test_bf_fixes.py:38 — running-total assertion confuses bool frames with shot duration; zero out shot A duration and compare `seen[1] == seen[0]`.
2. medium, test_bf_fixes.py:51 — brittle exact-dict equality on `api.run`; assert on `job_id` only.
3. high, server.py:? — mixed-type episode sort can crash with `TypeError`; sort with `key=str`.
4. high, pipeline.py:? — `bool` seconds (`True` = 1) survive a `<= 0` clamp; coerce non-numeric/bool to `0`.
5. medium, h3/gate_d_audio.py:? — non-object `narration_by_lang` is treated as missing by `_lang_track` but as `TIME-01` by `same_timing_problems`; unify the handling.
