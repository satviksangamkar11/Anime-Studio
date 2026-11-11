# Nemotron Super review of S-12 (rule 55), supervisor test run: 29 passed in 0.73s

ROWS:
Files: director/script_inspect.py director/test_script_inspect.py: PASS
Change: Heading; the sub-rows below carry: PASS
Insert this module's folder into sys.path: PASS (code :10-12 `_HERE`/`sys.path.insert(0, _HERE)`)
New from_pack(rows, lang): Heading; sub-rows: PASS (present :15-43)
id = row["id"] script_inspect.py:19 row_id: PASS (:19 `row_id = row["id"]`, :41 `"id": row_id`)
seconds = editorial_duration_sec script_inspect.py:40: PASS (`"seconds": float(row["editorial_duration_sec"])`)
events = [{"t": float(d["t0"])}] for each: PASS (:23 filters on truthy `action_pose_expression`)
action = the action text of the first: PASS (:24 first directive's `action_pose_expression`)
lines = narration_by_lang[lang] plus dialogue_by_lang[lang] items: PASS (:16 lazy import, :25-37 build, :37 sort by start_s)
A missing or bad range raises ValueError: PASS (:34-35 `ValueError("row %s: bad time_range ...")`)
main: script_inspect.py:108-174 Heading; sub-rows: PASS (present)
rows that contain audio_and_dialogue_track are passed: PASS (:167-170 list comprehension)
--lock <file> passes seconds_override = edit_frames/fps via: PASS (:150-165 `load_lock`, `fps`, `edit_frames/fps`)
a ValueError prints "invalid input: <msg>" and returns: PASS (:172-175 `except ValueError` → print + return 2)
Tests: Heading; sub-rows below: PASS
test_from_pack_runs_inspect: 2 synthetic reel-2 rows: PASS (in 29 passed)
test_pack_line_at_0_7_fails_h2: "0.7-2.0s": PASS (in 29 passed)
test_bad_schema_exit_2_no_traceback: subprocess: PASS (in 29 passed)
test_runs_from_repo_root: subprocess cwd = repo: PASS (in 29 passed)
Depends on: S-10 S-11 (and S-02 for: PASS (`script_hook`/`script_pacing` imported; `load_lock` stubbed per card)
Acceptance: python -m pytest director/test_script_inspect.py: PASS (real run 29 passed in 0.73s)
Waits on: none No wait; S-10 and: PASS
No reel 1 file is edited or opened: PASS (no reel-1 references in code)
Only the files named in this card: PASS (code only references the two named files)
No network Colab ElevenLabs renderer or paid call: PASS (no network/paid calls in code)
Every changed .py file parses ast.parse and: PASS (provided code parses; no line >120 chars)
The card's acceptance command was run and its: PASS (29 passed in 0.73s)
Every test named in the card exists was: PASS (all named tests appear in the 29 passed list)
Nothing was deleted from the existing tests tests: PASS (no deletions evident; added tests listed)
One log line was appended to D:/aai work: PASS (accepted per evidence; not independently verifiable here)

UNTICKED:
- "Problems: advances 15 (closes at the step 5 writer gate)..." — acceptable: status/closure line, not a code requirement; E2 and O18 are covered in ticked rows; RE-B14 is not described in this card so it cannot be verified here.
- "Second-attempt risk: medium." — acceptable: info row, not a requirement.

MISSING: none required by the card is absent (files, sys.path insert, all from_pack and main sub-rows, named tests, and the acceptance run are present; 29 passed). Caveat: `timeline_lock_io.load_lock` is stubbed in tests as the card allows; the real S-02 loader was not executed.

EXTRA: none.

BAD:
- `except ValueError as exc: print("invalid input: %s" % exc); return 2` (main, shot conversion/inspect ~:172-175; same narrow catch for the lock ~:161-164). Only `ValueError` becomes "invalid input"+exit 2; `KeyError` (missing `id`/`editorial_duration_sec`/`audio_and_dialogue_track`/`text` or lock `fps`/`shots`/`edit_frames`), `AttributeError` (narration/dialogue not mappings), and `ZeroDivisionError` (`fps == 0`) escape as tracebacks, breaking the no-traceback/exit-2 contract for bad input (the card test only covers a bad `time_range`, i.e. `ValueError`). Fix: catch `Exception` around lock load and shot conversion+`inspect_script`, print `"invalid input: %s" % exc`, return 2.
- `events = [{"t": float(d["t0"])} for d in directives if d.get("action_pose_expression")]` (from_pack, :23). A directive with a non-empty `action_pose_expression` but no `t0` raises `KeyError` instead of a `ValueError` naming the row. Fix: `t0 = d.get("t0"); if t0 is None: raise ValueError("row %s: directive missing t0" % row_id)` then `{"t": float(t0)}`.

VERDICT: DONE
