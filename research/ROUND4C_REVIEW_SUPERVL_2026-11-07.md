

# BATCH r4c_director (supervl) 11-07 09:51

Reasoning: I reviewed the two files provided (write_pack.py, pack_validator.py) against the owner spec and the round-2 fix list. The cross-file items (app.js, pipeline.js, server.py, router.py, etc.) were not included, so I treat those as unverified and confine concrete findings to the two files given.

Most round-2 fixes appear correctly implemented and guarded: tone required, ML-06 single-language narration vs shot length, bool-not-int, non-empty screen/depth, shot-id/episode validation, catalog-unreachable and key-file errors, answer_text JSON-decode handling, and the shared retry policy with ModelRefused. pack_validator is well-guarded throughout (dict checks before .get, _d/_l coercions, isinstance guards on voice_map/speaker_map).

The real defects are all crashes on malformed model output at trust boundaries in write_pack: `episodes_from` indexes `.get` on non-dict JSON, and `apply_captions` assumes `cards`, `dialogue_texts`, and the `*_by_lang` fields are lists/dicts without verifying, so non-list/non-dict truthy values raise TypeError/AttributeError. `parse_captions` only validates that stage-5 items are dicts, so malformed item internals reach `apply_captions` and crash the run.

- pack_validator.py: no findings.

severity: medium, write_pack.py:383 — `episodes_from` calls `.get("episodes")` on `json.loads(story.group(1))` without confirming the parsed value is a dict; a stage-1 answer whose ```json story block is a JSON array/number/string raises `AttributeError`, and the caller at line 927 only catches `ValueError`, so the run crashes with a traceback instead of a clean `StageFailed`. Failing input: `stage_1_raw.json` whose story block is `[1, 2, 3]` or `42`. Fix: parse once into a variable and guard with `isinstance(..., dict)` before `.get("episodes")`.

severity: medium, write_pack.py:844 — `apply_captions` does `list(item.get("cards") or [])`; when `cards` is a non-iterable truthy value (e.g. `5` or `True`), `or []` returns it and `list()` raises `TypeError`. Failing input: stage-5 captions item `{"shot_id": "SHOT-01", "cards": 5}`. Fix: `cards = item.get("cards"); shot["captions"] = list(cards) if isinstance(cards, list) else []`.

severity: medium, write_pack.py:849 — `apply_captions` zips `item.get("dialogue_texts") or []`; a non-iterable truthy `dialogue_texts` (e.g. `5`) raises `TypeError` in `zip`. Failing input: stage-5 captions item `{"shot_id": "SHOT-01", "dialogue_texts": 5}`. Fix: coerce `dialogue_texts` to a list via an `isinstance` check before `zip`.

severity: medium, write_pack.py:852,854,856,860 — `apply_captions` multi-language branch calls `.get()` / `.items()` on `captions_by_lang`, `narration_text_by_lang`, and `dialogue_texts_by_lang` without confirming they are dicts; a non-dict truthy value raises `AttributeError`. Failing input: stage-5 captions item `{"shot_id": "SHOT-01", "captions_by_lang": [1, 2]}` or `"narration_text_by_lang": [1, 2]`. Fix: guard each field with `isinstance(..., dict)` (or `_d()` coercion) before `.get`/`.items`.

FINAL: medium write_pack.py:383 `episodes_from` crashes with AttributeError on a non-dict ```json story block (uncaught, only ValueError is caught); medium write_pack.py:844 `apply_captions` `list(item.get("cards") or [])` raises TypeError when `cards` is a non-iterable truthy value; medium write_pack.py:849 `apply_captions` zips `item.get("dialogue_texts") or []` and raises TypeError on a non-iterable truthy value; medium write_pack.py:852/854/856/860 `apply_captions` calls `.get()`/`.items()` on `captions_by_lang`, `narration_text_by_lang`, `dialogue_texts_by_lang` without dict checks, raising AttributeError on non-dict truthy values; pack_validator.py no findings.


# BATCH r4c_h3 (supervl) 11-07 09:58

No findings in gate_d_audio.py beyond a low-severity logic issue; schema_and_linter.py and voice_manifest.py have real crashes on bad input; render_controller.py has one narrow gap.

- **medium, schema_and_linter.py:971 (also 952-959)** — `lint_story` calls `shot.get("shot_id")` without confirming `shot` is a dict. A non-dict shot row (e.g. `{"shots": [42]}`) raises `AttributeError` and aborts the whole story lint. The round-2 fix guarded non-object `timing_and_lattice` and `episode_plan` but not non-object shots. Failing input: story JSON whose `episodes[].shots` contains a number or string. Fix: skip/`continue` non-dict shot rows before accessing `shot.get`.

- **medium, voice_manifest.py:48 and 50** — `voice_ids_for` calls `.get` on `audio_and_dialogue_track` and on each dialogue entry without type checks. A truthy non-dict track (e.g. `[1, 2]`) or a non-dict dialogue entry raises `AttributeError`. `build_manifest` → `build_entry` → `voice_ids_for` has no try/except. Failing input: a shot with `"audio_and_dialogue_track": [1, 2]` or `"dialogue": ["not a dict"]`. Fix: type-check `trk` and each dialogue entry before calling `.get`.

- **low, gate_d_audio.py:383-388** — `parse_loudness_text`'s `last()` returns the last match of the *first* matching pattern, so a per-frame ebur128 value shadows the loudnorm summary block, contradicting the docstring ("the summary block beats any per-frame lines"). Failing input: ffmpeg text containing both ebur128 `I:` lines and a loudnorm `Input Integrated:` summary with differing values. Fix: search all patterns and return the match from the last pattern that has matches (summary patterns last).

- **low, schema_and_linter.py:974** — `lint_story` evaluates `(compiled or {}).get(sid)` without confirming `compiled` is a dict; a truthy non-dict `compiled` (e.g. a list) raises `AttributeError`. Failing input: `lint_story(story, compiled=[...])`. Fix: guard with `isinstance(compiled, dict)` before `.get`.

- **low, render_controller.py:523** — `_qc_result` catches `(KeyError, TypeError, ValueError)` but not `AttributeError`, so an `AttributeError` from `final_qc` crashes the dry-run plan. Failing input: `final_qc` raising `AttributeError` (e.g. rows not in the expected layout). Fix: add `AttributeError` to the except tuple.

Unverified (could not check from the files provided): the CAPTION margin values (bottom 896, top 360, sides 160) because `shot_table_spec` is not included; the JS/server contract (app.js `X-UI` header, pack scoping, `record_spend`, episode sort) because `ui/static/app.js`, `pipeline.js`, and `server.py` are not included.

FINAL:
1. medium, schema_and_linter.py:971 — lint_story crashes on non-dict shot rows; guard with isinstance before shot.get.
2. medium, voice_manifest.py:48,50 — voice_ids_for crashes on non-dict track/dialogue entries; type-check before .get.
3. low, gate_d_audio.py:383-388 — parse_loudness_text lets per-frame ebur128 shadow the loudnorm summary; check summary patterns last.
4. low, schema_and_linter.py:974 — lint_story crashes on non-dict compiled; isinstance-guard before .get.
5. low, render_controller.py:523 — _qc_result misses AttributeError from final_qc; add it to the except tuple.


# BATCH r4c_ui (supervl) 11-07 10:10

no findings for files not shown (app.js, h3/router.py, schema_and_linter.py, compile_h3_sing8.py, director/* etc. are out of scope for this diff). Reviewing pipeline.py and server.py only.

severity: medium, file: pipeline.py:387,401,407
why: `facts()` reads `download_queue.jsonl` and `flow_log.jsonl` and inserts `(shot_id, version)` into a dict/set and `(image_id, version)` into a set. JSONL lines produced by a crash or hand edit can carry a list or dict for `shot_id`/`version`/`image_id`, making the tuple unhashable and raising `TypeError`, which crashes `facts()`, `pipeline_state()`, `summary()`, and `render_status()` (500 on the UI).
concrete failing input: `download_queue.jsonl` line `{"shot_id": ["s1"], "version": "v01", "image_id": "img1"}` or `flow_log.jsonl` line `{"image_id": {"x": 1}, "version": "v01"}`; then open any pipeline/summary/render-status page for that pack.
one-line fix: skip or coerce non-hashable values, e.g. only accept `isinstance(x, (str, int))` (or wrap with `str()`) before using as dict/set keys.

severity: medium, file: server.py:1256-1259
why: `rec["used"] = True` is set before `_ops_checks().record_spend(...)`. If `record_spend` raises (ledger unwritable, disk full, etc.), the exception propagates as a 500, but `_start()` already launched the Colab subprocess and the preview token is marked consumed. The client gets no `job_id` and cannot track or stop the running spend job; the token cannot be retried.
concrete failing input: start a `colab_run` job with spend ON while the ledger path is read-only; `_start` succeeds, `record_spend` raises, API returns 500, token is spent, job runs untracked.
one-line fix: move `rec["used"] = True` to after `record_spend()` succeeds (or wrap `record_spend` in try/except and only mark the token used on success).

All other round-2 fixes visible in these files check out: `record_spend` is after `Popen` (not before), episode sort handles mixed int/str without `TypeError` (pipeline.py:703-704, server.py:748-749), zero/negative seconds clamp to 0 (pipeline.py:103), Gate A is blocked on validator errors (pipeline.py:639-642), approvals are scoped by story+pack (pipeline.py:193-197, 611-615), server binds 127.0.0.1 (server.py:1845), and no default model/Colab/ffmpeg/ElevenLabs calls are made by the UI.

FINAL: pipeline.py:387,401,407 — TypeError crash on unhashable shot_id/version/image_id in JSONL logs; server.py:1256-1259 — preview token consumed and spend job orphaned if record_spend raises after process start.


# BATCH r4c_tests (supervl) 11-07 10:25

- **high, write_pack.py:?, `episodes_from` accepts JSON `true` as an episode number because `bool` is a subclass of `int`.** Failing input: `{"episodes": [{"episode": true}, {"episode": 2}]}`. Fix: reject `bool` explicitly before accepting `int`.

- **high, pipeline.py:? / server.py:?, `summary` and `read_pack` crash on unhashable episode values (`[1]`, `{"a": 1}`) when they are inserted into a set or sorted.** Failing input: shot `"episode": [1]`. Fix: coerce episode to `str` before set/sort operations.

- **high, pipeline.py:?, the “every shot has seconds>0” check skips shots that lack an `episode`, so a zero-second shot without an episode passes.** Failing input: `{"id": "S2", "editorial_duration_sec": 0}` with no `episode`. Fix: validate `editorial_duration_sec > 0` for every shot regardless of episode.

- **high, h3/gate_d_audio.py:?, `plan_language_outputs` reads `shot["shot_id"]` but real stories key shots by `id`, causing `KeyError` for every language.** Failing input: shot with only `"id"` and `editorial_duration_sec`. Fix: resolve id via `shot.get("shot_id", shot.get("id"))`.

- **high, h3/render_controller.py:?, `main` lets `AttributeError` from `prepare` escape as a traceback instead of exiting 1 with an `ERROR` line.** Failing input: monkeypatched `prepare` raising `AttributeError` during `--dry-run`. Fix: catch `AttributeError` in `main` and return 1.

- **medium, h3/voice_manifest.py:?, `narration_text` crashes on non-dict narration blocks (`"corrupt"`, `42`).** Failing input: `narration_by_lang: "corrupt"`. Fix: return `""` unless the block is a dict.

- **medium, h3/gate_d_audio.py:?, `check_music_presence` includes `float("-inf")` BGM windows in the median, which can falsely trigger `BGM_MEDIAN_OUT_OF_BAND`.** Failing input: bgm list containing `-inf`. Fix: filter non-finite values before computing the median.

- **medium, pack_validator.py:?, `_check_voice` raises `TypeError: unhashable type: 'list'` when narration language is `["en"]`.** Failing input: `{"language": ["en"], "text": "x"}`. Fix: skip or coerce non-hashable languages.

- **medium, write_pack.py:?, `apply_captions` crashes on malformed stage-5 items (`cards: 5`, `captions_by_lang: [1, 2]`).** Failing input: items with non-list/non-dict fields. Fix: type-guard fields and default captions to `[]`.

- **medium, write_pack.py:?, `call_path` retries the same model on an `EMPTY` answer instead of switching/giving up, so `max_attempts=3` makes 3 calls.** Failing input: empty NVIDIA envelope. Fix: on `EMPTY`, do not retry the same model.

- **medium, pack_validator.py:?, `validate_pack` reads the story block from `stage_1_raw.json` instead of `story_plan.json`, producing spurious `STORY-` errors.** Failing input: `stage_1_raw.json` containing “no story block here”. Fix: read story block from `story_plan.json`.

- **medium, pipeline.py:?, `takes_of` returns the string `"3"` for `{"takes": "3"}` and does not clamp `0`/`11` to `3`.** Failing input: `{"takes": "3"}`. Fix: `int(takes)` with fallback and clamp to `[1, 10]`.

FINAL:
1. high, write_pack.py:?, `episodes_from` treats JSON `true` as episode 1 because `bool` is a subclass of `int`; reject `bool` explicitly before `int`.
2. high, pipeline.py:? / server.py:?, `summary`/`read_pack` crash on unhashable episode values (`[1]`, `{"a": 1}`) during set/sort; coerce episode to `str` first.
3. high, pipeline.py:?, zero-second shot without an episode passes the seconds>0 check because the check skips shot-less episodes; validate seconds for every shot.
4. high, h3/gate_d_audio.py:?, `plan_language_outputs` reads `shot["shot_id"]` but stories use `id`, causing per-language `KeyError`; use `shot.get("shot_id", shot.get("id"))`.
5. high, h3/render_controller.py:?, `main` does not catch `AttributeError` from `prepare`, so dry-run failure exits with a traceback instead of code 1; catch `AttributeError` and return 1.
