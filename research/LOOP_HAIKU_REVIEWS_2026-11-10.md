
## J7 precommit_check

Scope: tools/precommit_check.py and tools/test_precommit_check.py against loop_run_reel2/specs/J7_precommit_check.md. Read-only; no model, API, network or Colab call. pytest is not installed, so the 12 test functions were run by hand: all pass. check_file on both files returns no findings.

Passes: public names and finding formats; the four SECRET_PATTERNS; findings never contain secret text; control-character set is exact (tab, LF, CR allowed); fake keys built by concatenation; exactly 1 MB passes, over 1 MB flagged; main returns 0/1 from the staged argument.

Real bugs (confirmed by running):
- B1 CLI ignores its arguments. `sys.exit(main())` never passes sys.argv. `python precommit_check.py nope_missing.py` exits 0 with no output.
- B2 Line numbers drift. str.splitlines() also breaks on VT, form feed, U+2028 and U+2029. A form feed before a key on line 2 is reported as line 3; a VT before a control character shifts it from line 2 to line 3. CRLF is correct.
- B3 UTF-8 BOM. A .py file starting with a BOM gets "syntax error" on line 1 (false positive).
- B4 Staged deletions. `git diff --cached --name-only` also lists deleted files, so deleting a file blocks the commit with "missing file". From git behaviour, not run.

Test gaps:
- The no-secret-text check covers only hf; the spec asks for each pattern.
- The spec asks for a 2 MB file; the test uses 1 MB + 1 byte.
- check_files order test uses any(), so order is not checked.
- No check_file test for a .py syntax error, no BOM test, no CRLF or form-feed line-number test, no main(argv) test.
- Low: check_file reads the whole file before the size check; `.PY` is skipped (case-sensitive endswith); a directory reports "missing file"; ast.parse on NUL raises ValueError on Python below 3.12 (fine on 3.14 here).

Exact fixes:
1. In `__main__`: `sys.exit(main(sys.argv[1:] or None))`. Add a test that main(argv=[dirty]) returns 1.
2. In scan_secrets and check_control_chars, split on "\n" only (`text.split("\n")`, numbering from 1). Add tests for form feed, VT and U+2028 line numbers.
3. In check_file, decode with "utf-8-sig". Add a BOM .py test expecting [].
4. In main, add `--diff-filter=ACMR` to the git command. This changes the literal spec command, so the spec must be amended too.
5. In the tests: run the no-secret check over all four patterns; add a 2 MB case; add a check_file .py syntax test; assert exact order in check_files; add a CRLF test.

## Verdict: FIX FIRST

## J2 wav_contract

Scope: director/wav_contract.py and director/test_wav_contract.py against loop_run_reel2/specs/J2_wav_contract.md, including its Review findings. Read-only; no model, API, network or Colab call. pytest 9.1.1 installed: 23 passed. Probes ran in a temp folder.

Passes: all seven public names and results match the spec. require_wav checks extension and content, with the required messages ("extension", "looks like mp3"). Sniff rules match (RIFF/WAVE, ID3, 0xFF plus 0xE0 mask, under 12 bytes gives ValueError with the path, missing gives FileNotFoundError). The 12-byte limit does not block a valid header (a RIFF/WAVE header is exactly 12 bytes). The 4-byte and 5-byte short-file tests exist. plan_names order and duplicate check are correct. The find_voice message contains SHOT-003.hi.wav.

Real bugs:
- B1 A colon in shot_id escapes the folder on Windows. wav_name("C:x", "en") returns "C:x.en.wav", and PureWindowsPath("D:/voices") / "en" / "C:x.en.wav" resolves to "C:x.en.wav". A colon also makes an NTFS alternate stream ("a:b.en.wav"). The path-like check misses it.
- B2 find_voice with a str folder raises TypeError (str / str). The spec does not name the type, but callers will pass str.
- B3 find_voice uses exists(), so a directory named SHOT-004.hi.wav is returned as a voice file. Use is_file().
- B4 plan_names(["A", "a"]) passes. NTFS maps both to one file, so the duplicate check should compare casefold().

Test gaps:
- No require_wav test for "X.WAV" (spec says case-insensitive).
- No NaN case for slot_seconds (only inf).
- No test for colon ids, str folder, or a directory at the voice path.

Exact fixes:
1. wav_name: add `or ":" in shot_id` to the path-like check. Test: wav_name("C:x", "en") and wav_name("a:b", "en") raise ValueError.
2. find_voice: `expected = Path(folder) / lang / wav_name(shot_id, lang)` and `if not expected.is_file():`. Test: str folder works; a directory at the expected name raises FileNotFoundError.
3. plan_names: `if len({s.casefold() for s in shot_ids}) != len(shot_ids): raise ValueError("shot_ids contains duplicates")`. Test: plan_names(["A", "a"]) raises.
4. Tests: require_wav on a RIFF/WAVE file named X.WAV passes; slot_seconds({"en": math.nan}) raises ValueError.

## Verdict: FIX FIRST

## J7 precommit_check (second review)

Reviewer HK-J7b (haiku, high). Read-only: no code file edited, no model, API or network call. pytest: 23 passed (Python 3.14.3, pytest 9.1.1). Mutation runs were done on copies in scratchpad.

First-review findings:
1. CLI ignored args: FIXED. `__main__` now calls `main(sys.argv[1:] or None)`; a dirty file exits 1, a clean file exits 0 on the command line. NOT COVERED: reverting the `__main__` line still passes 23/23, because the tests only call `main(argv=...)`.
2. Line numbers on form feed, VT, U+2028, U+2029: FIXED (`split("\n")` in `scan_secrets` and `check_control_chars`). Test meaningful: reverting to `splitlines()` fails 3 tests.
3. BOM false syntax error: FIXED (`utf-8-sig`). Test meaningful: reverting to `utf-8` fails `test_check_file_bom_python_valid_is_clean`.
4. Staged deletions: FIXED (`--diff-filter=ACMR`). Test meaningful: an `ACM` mutant fails `test_main_default_git_command_uses_diff_filter`.
5. Extra tests: all present (four no-secret-text checks, 2 MB file, .py syntax error via check_file, exact-order list, .PY).

Secrets: scan of both files returns no findings; the test file builds fake keys by concatenation. The module prints only `path:line: name` or `path:line: syntax error` or a control-character line; no secret text.

Minor, not blocking: the old `test_check_files_order_and_missing` still uses `any`. A .py file with a NUL byte gives no crash on Python 3.14; older Python was not tested.

Exact fix: add this test to `tools/test_precommit_check.py`, then rerun pytest. The reverted `__main__` mutant must then fail it.

```python
def test_cli_entry_point_passes_argv(tmp_path) -> None:
    import subprocess
    script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "precommit_check.py")
    dirty = tmp_path / "cli_dirty.py"
    dirty.write_text(f"key = {_key_hf()}\n")
    clean = tmp_path / "cli_clean.py"
    clean.write_text("x = 1\n")
    dirty_run = subprocess.run([sys.executable, script, str(dirty)], capture_output=True)
    clean_run = subprocess.run([sys.executable, script, str(clean)], capture_output=True)
    assert dirty_run.returncode == 1
    assert clean_run.returncode == 0
```

## Verdict: FIX FIRST

## J2 wav_contract (confirm review)

Reviewer: HK-J2b (haiku, high). Read-only: no repo file edited, no model/API/network call. Mutants were run on copies in the scratchpad.

Test run: `python -m pytest director/test_wav_contract.py -p no:cacheprovider -q` gives 29 passed.

| Earlier bug | Code fix | Covering test | Mutant (fix removed) |
|---|---|---|---|
| 1. colon in shot_id | wav_name refuses ":" (line 17) | test_wav_name_colon_refused | KILLED |
| 2a. find_voice with str folder | Path(folder) / lang | test_find_voice_accepts_str_folder | KILLED (TypeError) |
| 2b. directory at voice path | expected.is_file() | test_find_voice_directory_at_voice_path_refused | KILLED |
| 3. case-only duplicate in plan_names | casefold check (line 83) | test_plan_names_case_insensitive_duplicate_refused | KILLED |
| 4a. X.WAV passes require_wav | lower().endswith(".wav") | test_require_wav_uppercase_extension_passes | KILLED |
| 4b. NaN slot length refused | isfinite check | test_slot_seconds_nan_refused (and non_finite test) | KILLED |

Also checked: ".." in shot_id refusal (mutant KILLED by test_wav_name_path_like_shot_id); 4-byte and 5-byte short-file cases present; "AVI " RIFF refused.

Not blocking: find_voice returns any regular file at the path; content checks stay in require_wav, as the spec says.

## Verdict: READY

## J1a timeline_lock_core

Read-only review. pytest: 29 passed (no network, no bytecode written). Probe and mutants ran in scratchpad copies only.

Hand checks agree with code:
- need 40 @128: bar 45 (4 beats), spare 5; beat also 45, tie goes to bar.
- need 85 @176: bar 90 (11 beats), spare 5.
- need 25 @60: bar 48 (2 beats), spare 23.
- Lattice 158/175/192/209/243 valid; fit_lattice(176)=192; fit_lattice(77)=90.
- Beat error max 20.83 ms (half a frame). Successive beats at 128 match round(k*g).
- Beat after a 22-frame shot, need 30 @128: beats 5, frames 34 (correct).

Spec API, names, signatures (start_in_act_frames before fps) and result keys match. Inputs not mutated; need 0 raises in all three functions; KeyError text correct.

Mutants (8): killed tie-to-beat, no act reset, lattice +4, no margin. Survived: always-bar (no test where beat strictly wins), beat uses floor, no tail handle in pixel_frames, beat ignores in-act offset.

Findings:
1. Old test_beat_candidate_error_bounded calls the same args 200 times and only checks k=1. Tautology.
2. test_choose_fewer_spare is a tie case, not a beat win.
3. bar error_ms is 0.0 even when the cut is off-grid: 128 BPM, 22-frame beat shot then bar 45 gives cut 67 vs grid 67.5 (20.8 ms). Within bound, no accumulation, but misreported.
4. edit_frames_for_shot({"en": 1e308}) raises OverflowError, not ValueError.
5. bar_beats parameter and plan_shots act_start_frame are unused.

Fixes:
F1. Delete test_beat_candidate_error_bounded (the successive-beat test replaces it).
F2. Add test: choose(20, 128.0) -> method "beat", frames 22, beats 2, spare 2.
F3. In the successive-beat test add: assert c["frames"] == round(k*g).
F4. Add test: plan_shots edit 30, bpm None -> pixel_frames 73.
F5. Add test: choose(30, 128.0, 22) -> method "beat", beats 5, frames 34.
F6. Decide: compute real cut error for bar, or state in the spec that bar error_ms is duration-only.
F7. In edit_frames_for_shot, raise ValueError when seconds*fps is not finite.
F8. Remove or document bar_beats and the unused act_start_frame.

## Verdict: FIX FIRST
Fixes F1-F5 and F7 are required (F6 needs a spec decision). Module maths is correct; tests need the gaps closed.

## J1b timeline_lock_io

Reviewer: HK-J1b (haiku, high). Read-only: no repo file edited, no model/API/network call. Mutants and probes ran on scratchpad copies.

Test run: `python -m pytest director/test_timeline_lock_io.py -p no:cacheprovider -q` gives 20 passed.

Mutants: 16 run, 11 killed, 5 survived: backslash normalise removed (M1), file name removed from hash (M3), write_lock accepts float edit_frames (M7), temp cleanup on failure removed (M8), ensure_ascii=True (M9).

Probes against the spec:
- OK: failed write leaves no temp file and keeps the old target; backslash paths stored with forward slashes; raw UTF-8 Devanagari in file; missing input raises StaleLockError; bad edit_frames refused before the file exists.
- BUG P2: `"version": true` loads (True == 1).
- BUG P4: unhashable shot id `["s1"]` gives TypeError from write_lock, not ValueError.
- SPEC P6: a dict shot without id reports "shot None"; the spec asks for the index.
- LOW P3: hash is not injective: name "a" with bytes "bc" equals name "ab" with bytes "c". verify still refuses via the path-set check.
- LOW P5: total_frames 5.0 loads.

Exact fixes:
1. Test: shot with `"note": object()`; assert TypeError, no `.tmp` left, old target bytes unchanged (kills M8).
2. Test: same bytes under a different file name gives a different input_sha256 (kills M3).
3. Test: backslash path string: no backslash in lock["inputs"], hash equals the forward-slash form (kills M1).
4. Test: edit_frames 2.5 and "5" refused by write_lock, target not created (kills M7); assert "invalid edit_frames" in the load_lock message for "5" and True.
5. load_lock: `type(lock.get("version")) is int`; test with true.
6. write_lock: non-str shot id raises ValueError before the set check.
7. load_lock: label by index when id is missing; require total_frames int; require inputs to be a list of str (by reading, a non-list inputs makes verify_lock raise TypeError).
8. Optional: length-prefix name and bytes in input_sha256 (fixes P3) while no lock is in use yet.

## Verdict: FIX FIRST

## J5 shot_mode
Reviewed h3/shot_mode.py and h3/tests/test_shot_mode.py against specs/J5_shot_mode.md. Read-only; repo untouched.
- pytest: 22 passed.
- By hand: default SE; S refused with no env and with "0", accepted with "1"; "E" refused; 158/175/192/209/226/243/22 valid; 5/160/100/bool/float refused; 160 -> "158 and 175", 100 -> "90 and 107"; S result has no end; SE without end refused; missing start/id raise ShotModeError in frame_row and rows; duplicate id refused and named.
- Mutations on scratchpad copies (all killed): default "S" -> 3 fail; env gate removed -> 2 fail; S keeps end -> 3 fail; duplicate check removed -> 1 fail.
- Bug 1: rows() names the shot id only if str(id) appears in the message. Id "s" or "158" with bad pixel_frames is not named. Fix: always wrap in rows(): raise ShotModeError(f"shot {shot_id!r}: {exc}") from exc.
- Bug 2: frame_row with no pixel_frames raises KeyError. Fix: if "pixel_frames" not in shot: raise ShotModeError(f"shot {shot_id!r} is missing required 'pixel_frames'").
- Test gaps: no test for Bug 1 or Bug 2. test_S_refused_without_env_flag reads os.environ (not hermetic). Fix: pass env={} there and add the two tests.
- Note: "None" is printed as the lower neighbour for 0, 5, 10. Acceptable; decide and document.
- Note: h3/shot_mode.py and both test files are untracked in git (??). Commit when approved.

## Verdict: FIX FIRST
1. rows(): replace the substring check with an unconditional wrap: raise ShotModeError(f"shot {shot_id!r}: {exc}") from exc.
2. frame_row(): check "pixel_frames" in shot before reading it; raise ShotModeError naming the shot id.
3. Tests: add rows() case with id "s" and pixel_frames 160 asserting "'s'" in message; add missing-pixel_frames test (ShotModeError, not KeyError); pass env={} in test_S_refused_without_env_flag.

## J4 prompt_hygiene
Reviewed h3/prompt_hygiene.py and h3/tests/test_prompt_hygiene.py against the J4 spec. pytest: 30 passed. All spec examples return the expected output (collapse, glue, legitimate phrases, mouth 1/2/3, speaker missing, cast 1/2/3, sound cue, beehive, clean_prompt no double newline). Spec item 3 (frozen glue tests asserting "with") is already resolved: the tests assert the full phrase.

Bugs:
1. mouth_sentence grammar: `mouth_sentence(["A","B"],["A","B"])` returns "A and B speaks with moving lips."; `mouth_sentence(["A","B","C"],["A","B"])` gives "...; C keep their lips completely closed." Verb must follow count (speak/speaks, keep/keeps). Untested.
2. clean_prompt cast-last: if the text already contains the cast line, it is not moved, so the result does not end with it (`clean_prompt("x.\nOnly A appears ...\ny.", cast=["A"], ...)` ends with the mouth sentence). Fix: drop existing copies of the mouth and cast lines from `lines` before appending both.

Test gaps (mutants in scratchpad):
- m1 (remove the "and" skip in find_cue_glue): 30 pass. Add `find_cue_glue("with a veil and dust snaps") == []`.
- m2 (find_duplicate_sentences never sets seen to False): 30 pass. Add a three-occurrence case expecting one report.
- m3 (remove final collapse_blank_lines in clean_prompt): 30 pass. Add a case where mouth/cast input has blank lines, or drop the step deliberately and note it.
- m4 (drop trailing \b in check_sound_cue): 3 fail. Caught.
- test_clean_prompt_no_blank_lines_ends_with_cast only checks for any PromptError; name does not match. Rename, or match the message "cue glue".
- No clean_prompt test for a banned sound cue or a speaker missing from on_screen.

Minor, optional: find_cue_glue is case-sensitive ("With a veil snaps" missed).

Exact fixes: (1) in mouth_sentence use plural verb forms when len(speaking) > 1 and len(silent) > 1 (or "keep" when len(silent) > 1); (2) in clean_prompt, `lines = [l for l in text.split("\n") if l not in (mouth, cast)]` before appending; (3) add the four tests above.

## Verdict: FIX FIRST

## J3 caption_fields

Read-only review of director/caption_fields.py and director/test_caption_fields.py against J3 spec (incl. Clarification and review finding 1). pytest: 27 passed.

Checked by hand: resolve_caption identical/absent/empty caption, both Hindi pairs approved (returns 'ब्याहीं', 'ग़लती'), unapproved refused, approved with word count change refused, approval 1 (non-bool) refused, empty/missing spoken refused. diff_report pairs give changed_words [('ब्याही','ब्याहीं')] and [('गलती','ग़लती')], empty changed_words when counts differ, same only after NFC. caption_lines returns dicts and raises on first bad line. check_lines reports problems in input order, and the caption-without-spoken case returns ['line 1: missing spoken text'].

Mutations (scratchpad copies): M1 approval truthy check: 1 failed (caught). M3 word-count check disabled: 1 failed (caught). M4 duplicate check removed: 3 failed (caught). M2 NFC removed from resolve_caption equality: 27 passed (NOT caught).

Problems:
1. check_lines does not "never raise" as the spec says. Non-string spoken_text or caption_text (e.g. caption_text 5) raises TypeError from _nfc; a non-dict element (e.g. None) raises AttributeError.
2. The NFC/NFD test is vacuous. 'नमस्ते' is identical under NFC and NFD, so M2 survives. Devanagari chars where NFC and NFD really differ are U+0929, U+0931, U+0934.

Exact fixes:
1. In check_lines, skip non-dict entries with a problem string such as "line <index>: not a mapping"; treat a non-str spoken_text or caption_text as a problem string and skip the caption comparison for that line. Keep the duplicate check running.
2. In test_nfc_and_nfd_count_as_equal, use spoken "\u0929" and caption "\u0928\u093c" (NFD of U+0929). Verified: this passes on the real module and fails under M2.

Optional (not blocking): diff_report raises TypeError when spoken_text is explicitly None and caption_text is set; whitespace-only spoken_text ("   ") is treated as present.

## Verdict: FIX FIRST

## J6 runner_safety

Files: director/runner_safety.py, director/test_runner_safety.py. Spec: loop_run_reel2/specs/J6_runner_safety.md. Read-only review; no model, API or network call. pytest: 25 passed. Both files parse.

Findings (safety):
1. Path traversal: clip_verified accepts shot_id "../x". With x.mp4 at the parent of results_dir, clip_verified returns True and stop_decision returns stop True. Fix: require a non-empty str with no path separators, not "." or "..", and check the resolved mp4 parent equals the shot dir.
2. stop_decision: all_done is checked by truthiness. The string "no" stops the session. Fix: require `all_done is True`, else raise TypeError.
3. can_stop: a str expected_ids iterates characters ("abc" -> a, b, c). Fix: require list or tuple.
4. wheel_ok: a directory path raises PermissionError instead of returning False. Fix: `p.is_file()`.
5. deadman_seconds: n_clips 0.5 and bool True are accepted. Fix: require int and not bool for n_clips.
6. preflight: default head uses urlopen, which raises HTTPError for 504. The message then has "HTTPError" and no "504". Fix: when exc has a code attribute, add "HTTP <code>" to the message.
7. Spec: line 132 is 138 chars (limit 120).

Mutation survivors (4 of 4 pass the suite; scratchpad copies only):
- m1 `>` to `>=` in clip_verified: no test at exactly 50_000 bytes.
- m2 stop_decision returns stop when all verified even if all_done is False: no test for that case.
- m3 `int(math.ceil(...))` to `int(...)`: no test with a fractional deadman result.
- m4 `if not result` to `if result is None` in preflight: no test of a key check returning False.

Missing tests: exact 50_000 boundary; a symlink or directory named like an mp4; traversal ids; all_done True-only cases; str expected_ids; wheel directory; HTTPError status in the message; key check returning False with no secret text.

## Verdict: FIX FIRST

Exact fixes: items 1 to 7 above, plus tests for each missing case and for m1 to m4. Re-run the suite and mutations after the fix.

## J5 shot_mode (confirm review)
Read-only confirm of h3/shot_mode.py and h3/tests/test_shot_mode.py against specs/J5_shot_mode.md (fifth-run findings). No model, API or network call.
- pytest: 24 passed.
- Fix 1 (rows names every id): code wraps every frame_row error as "shot {id!r}: ..."; test_rows_wraps_error_with_shot_id_for_short_ids covers "s" and "158". Fixed.
- Fix 2 (missing pixel_frames): ShotModeError naming the shot, not KeyError; test_frame_row_missing_pixel_frames_names_shot_not_keyerror. Fixed.
- Fix 3 (docstring on None neighbour): present in check_pixel_frames. Fixed.
- Fix 4 (hermetic S-refused test): env={} passed; passes with SHOT_MODE_S_ALLOW=1 set in the shell. Fixed.
- Earlier behaviours hold: default SE, S gated by env "1" only, 17n+5 counts, S result has no end key.
- Mutations (scratchpad copies, all killed): rows wrap removed -> 2 fail; pixel_frames guard removed -> 1 fail; env param ignored -> 3 fail.
- Cosmetic only: rows() now repeats the id for missing-field errors ("shot 's1': shot 's1' is missing ..."). Not blocking.

## Verdict: READY

## J9b script_pacing
Read-only review of director/script_pacing.py and director/test_script_pacing.py against specs/J9b_script_pacing.md (sixth run, hard examples 1-6, clarifications). No model, API or network call.
- pytest (repo, read-only): 23 passed.
- Hand check: P1 within-shot gap > 1.5 (exact 1.5 ok) and later-shot first line > 2.0 (exact 2.0 ok, shots with no lines skipped) match. P2 payoff window [dur-5, dur] correct. P3 uses shot-relative times against each shot's own start, window 25-35 inclusive, skipped under 36 s: correct. P4 bounds 60.0 and 75.0 inclusive in code. Problem strings contain "dead air", "payoff", "re-hook", "length". Languages, empty shots, missing shot key -> ValueError. Deterministic, no mutation, no imports.
- Mutations (scratchpad copies only, under scratchpad j9b):
  - m1 gap > 1.5 changed to >= 1.5: killed (2 fail).
  - m2 first_start > 2.0 changed to >= 2.0: killed (1 fail).
  - m3 re-hook skip removed: killed (2 fail).
  - m4 length bounds changed to <= 60.0 and >= 75.0: SURVIVED (23 pass). No test sits exactly on 60.0 or 75.0.
- Minor: a missing key inside a line dict (start_s, end_s, text) raises KeyError, not ValueError. Spec only requires the shot-level key check, so this is optional.

## Verdict: FIX FIRST

Exact fixes:
1. In director/test_script_pacing.py add two tests: a 10-shot reel of 7.5 s (total 75.0) and an 8-shot reel of 7.5 s (total 60.0), both built from _good_reel-style shots (re-hook shot starts 22.5/30.0 are fine), each asserting pass True and problems []. Re-run pytest and mutation m4; m4 must fail.
2. Optional: validate line keys in inspect_pacing and raise ValueError naming the key, then add one test.

## J1a timeline_lock_core (confirm review)
- F6 bar error_ms: FIXED (choose recomputes it). Hand checks: choose(40,128,22) -> bar 45, error 20.833; choose(40,128,0) -> 0.0. Killed by M1.
- F7 huge seconds: FIXED (cap checked before isfinite). 1e308 and 10**1000 -> ValueError. Killed by M2.
- Tautological beat test: replaced by successive-beat test (k=1..200, 128 and 176 BPM), passes.
- Other hand examples match: bar 40@128=45, 85@176=90, 25@60=48, choose(20,128)=beat 22, choose(30,128,22)=beat 5 / 34, plan pixel_frames 73, fit_lattice(176)=192.
- Mutants (scratchpad copies): always-bar, beat floor, no tail handle, beat ignores offset: all KILLED. New: tie-to-beat KILLED.
- SURVIVED: ceil->floor in edit_frames_for_shot. No test uses fractional seconds.
- Non-blocking: beat_candidate loops without bound; bpm 1e9 with need 1000 did not return in 8 s.

## Verdict: FIX FIRST
Exact fix: add to director/test_timeline_lock_core.py:
    def test_edit_frames_fractional_seconds_ceil():
        assert timeline_lock_core.edit_frames_for_shot({"en": 1.01}) == 31
(ceil(1.01*24)+6 = 31; floor gives 30.) Re-run pytest; it must stay 41 passed. Optional: bound the beat_candidate loop or reject absurd bpm.

## J4 prompt_hygiene (confirm review)
Read-only. Repo untouched. Suite `h3/tests/test_prompt_hygiene.py`: 36 pass. No model, API or network call.

Prior findings:
- mouth_sentence plural verbs: FIXED and covered (both spec strings match exactly).
- clean_prompt cast line already in input (own line): FIXED and covered (ends with it once).
- find_cue_glue "With a veil snaps": module FIXED (IGNORECASE), NOT covered by a test.
- find_cue_glue "with a veil and dust snaps" == []: module correct, NOT covered by a test.

Mutants (scratchpad copies only):
- m1 skip the "and" check: 36 pass (SURVIVED)
- m2 drop `seen[key] = False`: 1 fail (killed)
- m3 drop final collapse_blank_lines: 36 pass (SURVIVED; `clean_prompt("")` leaks a leading blank line)
- m4 drop re.IGNORECASE on GLUE_RE: 36 pass (SURVIVED)

Extra gap: input `"A line. Only A appears in this shot; no extra figures or creatures appear.\n"` gives the cast line TWICE, because the filter drops whole lines only.

Exact fixes:
1. Add tests to test_prompt_hygiene.py:
   - `find_cue_glue("with a veil and dust snaps") == []`
   - `find_cue_glue("With a veil snaps") == ["With a veil snaps"]`
   - `clean_prompt("", cast=["A"], on_screen=["A"], speaking=["A"])` == "A speaks with moving lips.\nOnly A appears in this shot; no extra figures or creatures appear." (kills m3)
   - the embedded-cast input above: result.count(cast_line) == 1
2. clean_prompt: before the line filter, remove the mouth sentence and cast line as substrings (`text = text.replace(mouth, "").replace(cast, "")`, then collapse_blank_lines). Keep the final collapse.

## Verdict: FIX FIRST
Fix 1 and 2 above, then one confirm pass on the changed files.

## J6 runner_safety (confirm review)
Reviewer: HK-J6b (haiku, medium). Read-only: no repo file edited, no model/API/network call. Mutants on scratchpad copies only.
- pytest: 35 passed. Both files parse. No line over 120 characters.
- Earlier findings 1-7 are in the code and covered by tests (traversal ids, all_done `is True`, str expected_ids, wheel_ok on a directory, n_clips bool/fraction, HTTP status in message, 138-char line now wrapped, exact 50_000 boundary, key check returning False).
- Mutants: m2 (stop gate ignores all_done) KILLED (3 fail); m4 (`if not result` to `is None`) KILLED (1 fail).
- SURVIVED m1: injected branch `>` to `>=` at line 31 (23-35 tests use 60_000 only; no injected 50_000 test).
- SURVIVED m3: `int(math.ceil(...))` to `int(...)` (no test with a fractional deadman result).
- Hand probes (6), stop guarantee:
  P1 small 49_999 clip only: refused. OK.
  P2 shot id "a." with only a/a.mp4 present: VERIFIED (True). Windows strips the trailing dot, so "a." reads shot a's clip. BREAKS guarantee.
  P3 results on D:, shot id "C:outside" with clip at C: cwd: VERIFIED, stop True. Drive-relative path escapes results_dir. BREAKS guarantee.
  P4 "s4.mp4" is a directory: refused. OK.
  P5 "s5.mp4.part" 60_000 bytes: refused. OK.
  P6 injected size 50_000 refused; injected exists False refused. OK.
- Not blocking: a symlinked shot directory is followed (is_dir), so a clip outside results_dir can verify.

Exact fixes:
1. _valid_shot_id: also return False when ":" in shot_id, or when shot_id ends with "." or " ". Tests: "C:outside" and "a." return False with clips present (P2, P3 as tests).
2. clip_verified (non-injected): after clip_dir is built, require clip_dir.resolve().parent == Path(results_dir).resolve(), else False. Optional test with a symlinked shot dir where the OS allows it.
3. Add test: injected size exactly MIN_CLIP_BYTES returns False (kills m1).
4. Add test: deadman_seconds(1.0, 1) == 1352 (kills m3).
Re-run pytest and m1/m3 after the fix.

## Verdict: FIX FIRST

## J9c script_inspect
Scope: director/script_inspect.py and director/test_script_inspect.py against specs/J9c_script_inspect.md. Read-only on repo; mutants made in scratchpad only. No model, API or network call.

- Tests: `python -m pytest director/test_script_inspect.py -p no:cacheprovider -q` gives 22 passed. director/script_hook.py is NOT in the repo, so the test's sys.modules fakes and CLI stubs were used. Parse OK, no line over 120 chars.
- Code matches the spec: SUPPORTED_LANGS; ValueError for empty shots and unsupported lang; pass = hook and pacing; modules imported by bare name at call time; exceptions propagate; format_report line order and prefixes; main exit codes 0/1/2 for both JSON forms, missing file, bad JSON and wrong arg count; CLI runs from the module folder.
- Mutants (scratchpad j9c/m1-m4): M1 `and` changed to `or`: 4 fail. M2 REWRITE prefix changed: 1 fail. M3 missing-file return 2 changed to 1: 2 fail. M4 pacing exception swallowed: 0 fail. Gap: only a hook exception is tested for propagation. Test file is frozen, so this is noted, not blocking.
- Minor: main() prints format_report(), which already ends with a newline, and print adds another. CLI stdout therefore ends with a blank line (checked: "PACING: PASS" then an empty line). Optional fix at line 101: `sys.stdout.write(format_report(result, lang))`. Tests still pass with it because they check only line 0.

## Verdict: READY

## J11 image_gates
Reviewer: HK-J11 (haiku, medium). Read-only. Files: director/image_gates.py, director/test_image_gates.py. No model, API or network call.

- pytest `python -m pytest director/test_image_gates.py -p no:cacheprovider -q`: 35 passed.
- Parse: both files parse. No line over 120 characters.
- Hand checks on synthetic arrays (scratchpad j11/handcheck*.py): to_float01 uint8/float; dilate 0 and 3 (49 px); block_ssim identical 1.0; all-invalid and sub-8 sizes raise "no comparable area"; uint8 and float (0..255) give equal results; 20x20 change in the untiled rows gives 1.0; background_lock 16x16 case gives ssim 0.75002, mean_l1 0.25, area_fraction 1.0. Single normalisation is correct: background_lock passes the original arrays to block_ssim (the "THE ACTUAL BUG" is not present).
- Mutants (scratchpad j11/mutate.py), all caught by the frozen tests: M1 double normalisation (1 fail, ssim 0.9667); M2 tile off-by-one (4 fail); M3 entry_exit guard removed (1 fail); M4 dilate(0) aliases input (1 fail).

Real bug (not covered by tests):
- background_lock with a non-bool mask and dilate_px=0 crashes: uint8 0/1 mask gives IndexError at `compared = diff[valid]`. With dilate_px>0 it works, because dilate casts to bool. Spec says masks are bool.

Exact fix (image_gates.py only; the test file is frozen):
1. In background_lock, after `mask_b = np.asarray(mask_b)`, add:
   `if mask_a.dtype != bool or mask_b.dtype != bool:` then `raise GateError("masks must be bool")`.
2. Optional: in dilate, `mask = np.asarray(mask, dtype=bool)` so px=0 returns bool too.

Non-blocking notes: dilate with a non-integer px raises TypeError, not GateError; NaN seconds in feasible_motion passes validation and returns False.

## Verdict: FIX FIRST
Fix 1 above, then re-run pytest and add a check that a uint8 mask gives GateError.

## J10 audio_edge
Scope: director/audio_edge.py and director/test_audio_edge.py against specs/J10_audio_edge.md. Read-only on repo; probes and mutants in scratchpad only. No model, API or network call.

- Tests: `python -m pytest director/test_audio_edge.py -p no:cacheprovider -q` gives 28 passed (spec text says 27; harmless).
- Checked by hand: read_wav_mono, rms, voiced_threshold, edge_report fields, cut_margin_problems, inspect_wav rule, spec item 1 fade-in condition (applied), comment length 101 (ok), 1e-3 tolerance (ok).
- Burst at sample 0: edge_report gives starts_at_sample0 True and start_abrupt True; after apply_edges both are False. PASS.
- Mutants: m1 fade-in pad-only: 1 fail. m2 margin `<=`: 2 fail. m3 start_abrupt off: 1 fail. m4 fade-out always: 0 fail (survives).

Findings:
1. BLOCKING, idempotence: apply twice differs from once on 196 of 300 random signals (scratch). Smallest case is 53 samples: the voiced threshold is recomputed on the padded signal (0.0879 to 0.0799), so the second call pads 7 more samples. Aligning pad_front to the 20 ms grid does not fix it (still 196). Sine bursts hide this.
2. BLOCKING, the owner's click: when tail zeros are added the fade-out is skipped, because the padded end is 0.0. A voice ending on 0.0625 then steps straight to 0 (scratch probe). edge_report says end_abrupt False, so the report hides it. Fading the voiced tail before padding removes the click and passes all 28 tests, but breaks idempotence on 67 of 300 signals until item 1 is fixed.
3. m4 survives: the fade-out skip changes nothing (fading a 0.0 sample is a no-op). The DECISION's premise is wrong; removing the skip costs no test.
4. LOW: cut_margin_problems(0.3, 0.5, 0.2, 0.6, 0.10) flags "starts too close" because 0.3 - 0.2 = 0.0999. Use margin_s - 1e-9.

## Verdict: FIX FIRST
Exact fixes:
a. Make padding a fixed point: measure lead-in and tail on the exact leading and trailing zero runs, not on a threshold recomputed after padding. Then apply twice equals once (rerun the 300-signal check).
b. Fade the voiced tail (last fade_out_ms of the input) before padding; then the skip can go (m4).
c. Add tests: a fixed-seed noise idempotence test and a voice-end step test.
d. Compare margins with a 1e-9 tolerance.
Owner decision needed on (a): "voiced frame" versus "zero run" as the padding anchor.

## J9a script_hook
Read-only review of director/script_hook.py and director/test_script_hook.py against the J9a spec (all sections, incl. whole-word correction and the final H6 noun list).

- pytest: `python -m pytest director/test_script_hook.py -p no:cacheprovider -q` -> 28 passed.
- Hand-checked by running inspect_hook: good en hook = 100 pass; Marathi opener "एकेकाळी एक राजा होता" = 45 fail (H3 -15, H5 -40); 10-word en line = 85 pass (H4 -15); first line at 0.9 s = 60 fail (H2 -40). All match the spec.
- Mutations in scratchpad copies (repo untouched), each caught by the suite:
  - substring question-word match -> test_mr_opener_fails_h5 (60 != 45)
  - H2 threshold 0.6 -> 0.9 -> test_first_line_at_0_9_fails_h2 and the H2 parametrized case
  - Devanagari noun list removed -> 6 tests fail, incl. test_all_three_languages_good_hook
  - H1 threshold 1.0 -> 1.5 -> test_no_event_before_1_0_fails_h1 and the H1 parametrized case
- Spec items checked: constants, OPENERS, STAKES_WORDS (8 per Devanagari language), QUESTION_WORDS, H6 English list (23) and Devanagari list (13) match the final decision; H6 extended list (forest, sea, ...) correctly NOT adopted; reason strings start with the rule code; ValueError messages name the missing key; inputs not mutated; deterministic; no line over 120 characters.
- Non-blocking notes (no change required by spec): H5 uses str.startswith, so "it was a timeline" also trips the "it was a time" opener; an event with no "t" key defaults to 0.0 and passes H1; a shot with no spoken line skips H3-H5 (owner-accepted in triage round 2).

## Verdict: READY
No fixes required. Notes above are optional hardening only.

## J6 runner_safety (second confirm review)
Files: director/runner_safety.py, director/test_runner_safety.py. Read-only; pytest only; no model, API or network call. Mutations and probes ran in scratchpad copies.
- pytest: 41 passed, 1 skipped. The skip is test_clip_verified_symlinked_shot_dir_outside_results_refused (no directory symlinks on this machine), so the symlink guard did not run here.
- Lines: none over 120 characters. Both files parse.
- Spec coverage: C1 control refusal (line 28) present and tested; "a." and "C:x" refused; injected exact 50_000 refused; deadman_seconds(1.0, 1) == 1352 passes.
- Probes (37 of 40 as expected, plus notes): ids "", " ", "..", ".", "a/b", backslash id, "a.", "C:x", "a b", NUL, U+0085, U+009F all refused on the real path; non-bool all_done never stops; plain str and empty expected_ids raise; 49_999 / 50_000 / 50_001 bytes give False / False / True in real and injected modes; directory named x.mp4 not a clip; outside junction refused.
- Mutations: M1 (C1 block removed) caught by suite. M4 (>= for injected size) caught by suite. M2 (symlinked mp4 guard removed) SURVIVES: no test. M3 (shot-folder parent check removed) SURVIVES: its only test is skipped here; a junction to an outside folder then verifies.
- HOLE: a shot folder that is a junction to a sibling inside results (results/b -> results/a) is verified as clip b. The parent check passes because the sibling shares the parent. A stop could be granted for a missing clip.
- Note (not a stop path): preflight raises TypeError when head returns None (the status compare sits outside the try).

## Verdict: FIX FIRST
Exact fixes:
1. director/runner_safety.py clip_verified, replace `if clip_dir.resolve().parent != Path(results_dir).resolve():` with `if clip_dir.resolve() != Path(results_dir).resolve() / shot_id:`. Checked in a scratchpad copy: outside junction and sibling junction refused, real clip "a" still verified, suite 41 passed, 1 skipped.
2. director/test_runner_safety.py: add a sibling-junction test (results/b -> results/a, stop refused). Make the symlink test create the link with `mklink /J` on Windows so it runs without admin, and skip only if that fails.
3. Optional: in preflight, treat a non-int status as a failure string instead of raising.

## J6 runner_safety (final confirm review)
Reviewer: HK-J6d (haiku, medium). Read-only; no model, API or network call. Probes run on scratchpad copies only.

pytest (director/test_runner_safety.py): 44 passed, 0 skipped. The junction tests ran (sibling junction and outside junction both created and passed).

Earlier findings, each re-checked in code and killed by a test:
- Traversal ids ("../x", ".", "..", "a/b", "a\b", ""): refused.
- "a.": refused by the trailing "." rule; stop refused.
- "C:outside": refused by the ":" rule; stop refused.
- C1 control characters (128-159): refused in `_valid_shot_id`; test passes.
- Sibling junction (results/b -> results/a): resolve check refuses; clip_verified("b") False; stop refused.
- Non-int head status: reported as "invalid status"; no TypeError.
- Injected 50_000 boundary: strictly greater; 50_000 not verified, 50_001 verified.
- deadman_seconds(1.0, 1) == 1352.

Hand probes (8 required plus extras):
1. Junction to outside folder (folder named as id, and folder named differently): refused.
2. Junction to sibling: refused, stop refused.
3. Trailing-space id "a ": refused.
4. Mixed case "mixed" vs folder "Mixed": accepted on Windows (same folder, correct, not a hole).
5. ".MP4" uppercase: accepted (glob is case-insensitive on Windows; correct).
6. mp4 that is a directory: refused.
7. 49_999 / 50_000 / 50_001 bytes: refused / refused / accepted.
8. Folder with big mp4 plus small other.mp4: accepted via the big clip (correct).
Extras: small mp4 with another name refused; U+00A0 and U+200B pass the validator (not in the spec's control range; no escape possible, since the folder must resolve exactly to results/<id>).

No false stop found. No hole found.

Non-blocking notes:
- Injected mode (exists/size passed) skips the junction and containment checks by design. Nothing in the repo calls clip_verified, can_stop or stop_decision yet. Keep injected functions out of any production caller.
- Optional: reject Unicode format characters (category Cf) in ids. Not required for safety.

## Verdict: READY

## J14 shot_router
Reviewer: HK-J14 (haiku, medium). Read-only; no model, API or network call. Files: director/shot_router.py, director/test_shot_router.py (frozen).

- pytest: 46 passed (`python -m pytest director/test_shot_router.py -p no:cacheprovider -q`). Both files parse; no line over 120 chars.
- Rule order 1-6 matches spec. Rule 2 extra reason "more than 3 moving people" is added only in the crowd/cast_count branch (camera_move returns first, one entry). Table text stays first.
- Per-route values (route, image_prompt_type, input_video_strength, keyframes, gpu, est_units, requires_owner_flag, reasons) match the spec table for all five routes. arc_sec 1.5 gives SOFT_SE, 1.51 gives KFI.
- Validation raises RouterError naming the key (missing key, kind, bool-as-number, duration <= 0, negative cast_count/arc_sec, non-dict features -> "features"). NaN is rejected.
- No aliasing: result lists are deep copies (`import copy`; crowd branch and final return). Spec item 1 is already applied.
- plan_reel hand check (5 shots): total_est_units 5.1, keyframe_count 9, gpu_shots 4, needs_owner_flag [s1, s4]. Matches test comments. Inputs not mutated.
- Mutations (scratchpad copies, repo untouched), each caught by tests: M1 shallow copy -> 1 fail (aliasing test); M2 arc >= 1.5 -> 1 fail (1.5 test); M3 wrong crowd reason text -> 4 fails; M4 camera_move reordered after end-pose -> 1 fail (camera_move test).

Non-blocking notes (not required by spec; test file frozen):
1. plan_reel does not check shot shape: a shot without "id" or "features" raises KeyError, not RouterError. Unhashable id raises TypeError.
2. Validation tests cover arc_sec, kind, duration_sec, cast_count, needs_end_pose, multi_arm only. Missing keys other than arc_sec and wrong types for arc_sec and cast_count are not tested (code handles them).

## Verdict: READY
No fixes required.

## J13 clip_gates
Reviewer: HK-J13 (haiku, medium). Read-only. Files: director/clip_gates.py, director/test_clip_gates.py. Spec: loop_run_reel2/specs/J13_clip_gates.md (incl. clarifications and round-10 items 1-4).

- pytest (python -m pytest director/test_clip_gates.py -p no:cacheprovider -q): 60 passed.
- Round-10 fixes present in clip_gates.py: end_frame_pass range checks use `not (lo <= x <= hi)` (NaN raises); tail_spike finite check; scene_cut isfinite check with `import math`; flicker_score finite check.
- Hand examples:
  1. tail_spike, 60 x 1.0, flow[52]=2.5 -> flag True, first_spike_index 52 (absolute), ratio 2.5, median 1.0. flow[52]=2.2 -> flag False (strict >).
  2. suggest_trim_out(52) -> 48; suggest_trim_out(2) -> 1 (minimum floor).
  3. end_frame_pass(0.82, 0.18, 0.88) -> pass; end_frame_pass(0.8199, 0.18, 0.88) -> failed ['ssim'].
  NaN in any of the three end-frame inputs raises ClipGateError (checked).
- Mutations (scratch copies, repo untouched), each caught:
  M1 tail `>` changed to `>=`: 2 failed.
  M2 first_spike_index made relative: 2 failed.
  M3 ssim `<` changed to `<=`: 3 failed.
  M4 flicker mask ignored: 2 failed.

Spec coverage: all listed behaviours have tests; head spike ignored; zero median and too-short raise; trim boundaries; best_cut offset and first-on-tie; scene_cut index 0 and start_index 0; new_object_classes at 12 and 20; flicker constant/alternating/mask; verdict strict flicker limit; inputs not mutated.

No fixes required.

## Verdict: READY

## J11 image_gates (confirm review)
Reviewer: HK-J11b (haiku, medium). Read-only on repo; probes and mutants in scratchpad j11b. No model, API or network call. Scope: director/image_gates.py and director/test_image_gates.py against specs/J11_image_gates.md (all sections).

- pytest `python -m pytest director/test_image_gates.py -p no:cacheprovider -q`: 42 passed (the prior review recorded 35; the test file has grown). Both files parse; no line over 120 characters.
- Earlier findings, now fixed and covered: uint8 mask with dilate_px=0 gives GateError("masks must be bool") (test present); float px in dilate gives GateError (test present); NaN seconds, NaN displacement and infinite inputs in feasible_motion give GateError (tests present).
- 16x16 case: ssim 0.75002, mean_l1 0.25, area_fraction 1.0. Hand arithmetic and direct block_ssim agree. background_lock passes the original arrays to block_ssim, so each public function normalises its own inputs once.
- Hostile probes: 10x10 (not a multiple of 8) gives 1.0 with one tile; 7x7 gives "no comparable area"; 2-D and 4-channel arrays give GateError; all-True mask gives "no comparable area"; np.float64 px gives GateError.
- Mutants: M1 double normalisation: 1 fail (test_changed_background_fails). M2 mask-dtype check removed from background_lock: survives, but is equivalent, because dilate checks dtype before its px==0 return. M3 NaN guard removed in feasible_motion: 3 fail.

Non-blocking notes:
- dilate(9x9, 10**6) takes about 10 s because it loops once per px. Clamp the loop to max(mask.shape); dilation saturates there, so output is unchanged.
- NaN pixels give ssim NaN and pass False, not GateError. Optional: raise GateError on non-finite image input.

## Verdict: READY

## J3 caption_fields
Reviewer: HK-J3 (haiku, medium). Read-only. Frozen tests: `python -m pytest director/test_caption_fields.py -p no:cacheprovider -q` = 34 passed. Mutations in scratchpad copies (repo untouched): no approval check = 3 fail; index labels = 5 fail; no NFC = 1 fail; no word-count check = 2 fail. All four caught.

Findings against the spec (eighth-run check order and whitespace rules):
1. `check_lines` runs the duplicate check BEFORE the caption comparison. Spec step 4 says comparison first, then duplicate. Probe: two identical lines id "1" with an unapproved diff give `[unapproved l1, duplicate l2, unapproved l2]`; spec order gives `[unapproved l1, unapproved l2, duplicate l2]`.
2. `diff_report` treats a whitespace-only caption as present: `caption_text: "   "` gives `same=False, word_count_equal=False`. `resolve_caption` and `check_lines` treat it as absent. Spec: caption absent in both; tests and code must agree.
3. `check_lines` raises TypeError for an unhashable id (`{"id": ["x"]}`), because `(line_id, lang)` goes into a set. Spec: never raises.
4. A non-str caption is handled inconsistently. `resolve_caption` with `caption_text: 5` silently returns the spoken text (the hidden-substitution problem this job is meant to close). `diff_report` with 5 raises TypeError.
5. Test gaps: no test for whitespace-only or None caption (resolve, check_lines, diff_report); no test for duplicate plus unapproved on the same line; no test for diff_report with caption None or whitespace.

## Verdict: FIX FIRST
Exact fixes (caption_fields.py, then tests):
- In `check_lines`, move the `key in seen` / `seen.add` block after the caption comparison block, so the per-line order is: not a mapping, missing spoken, spoken not text, caption not text, comparison problems, duplicate.
- Use `key = (repr(line_id), repr(lang))` in `check_lines` so unhashable ids cannot raise.
- In `diff_report`, treat `caption` as absent unless it is a non-blank str (same rule as `resolve_caption`).
- In `resolve_caption` and `diff_report`, a caption that is not None and not str raises `CaptionError("line <id>: caption_text is not text")`.
- Add tests: whitespace-only caption and None caption (resolve_caption, check_lines, diff_report); duplicate plus unapproved on one line, asserting the spec order; unhashable id returns without raising; resolve_caption raises for caption 5.

## J12 plate_composite

Reviewer: HK-J12 (haiku, medium). Read-only; repo files not edited. Scratch checks and mutants in the session scratchpad.

Tests: `python -m pytest director/test_plate_composite.py -p no:cacheprovider -q` gives 24 passed.

Synthetic checks: composite (full-True equals B, full-False equals A, feather centre = 255/9 = 28, uint8, shape mismatch), diff_mask (square, dilation by 2 grows 5x5 to 9x9, speckle, threshold 24 ignored and 25 kept, min_area 4 kept and 4 removed at 50, diagonal pixels stay separate), hole_fraction and composite_is_safe at exactly 0.02, plan keys and mask_area, save/load round trip, missing folder error.

Real bug: `_box_blur` zero-pads the mask. With feather_px > 0 a full-True mask no longer returns B on the image border. Measured: corner pixel = 113 where B = 255 (feather_px=1, 5x5 image). This breaks the spec invariant that a full-True mask equals B.

Test gaps (mutants that survive the 24 tests):
- M2 `diff > threshold` changed to `>=`: 24 passed.
- M4 `(labels == lab).sum() >= min_area` changed to `>`: 24 passed.
Mutants M1 (no union, the U-shape test catches it) and M3 (`<=` to `<` in composite_is_safe) fail as expected.

Speed (768x1344 random pair): diff_mask 2.65 s; 3,000 speckles 3.82 s; grid of 2,600 separated 1-px changes 5.3 s. Composite with feather 4: 1.6 s. Cost grows with components times pixels (`_remove_small` does a full-array compare per label), so it is fine for normal keyframes and would be slow for heavy noise. Note only, not blocking.

Nit: `save_rgb` writes the temp file as .png, so `out.jpg` ends up as PNG bytes under a .jpg name.

Fixes before READY:
1. In `_box_blur`, replace `np.zeros` padding with `np.pad(mask, px, mode="edge")` (or divide by in-bounds counts). Add a test: full-True mask with feather_px=2 equals B everywhere.
2. Add boundary tests: diff exactly 24 is not in the mask; a 4-pixel blob is kept at min_area 4 and removed at min_area 5.
3. In `save_rgb`, refuse a target whose extension is not .png, or write with the target's format. Add a test.

## Verdict: FIX FIRST

## J10 audio_edge

Reviewer: HK-J10 (haiku, medium). Read-only on repo code; scratch copies and WAVs in the session scratchpad.

Tests: `python -m pytest director/test_audio_edge.py -p no:cacheprovider -q` gives 33 passed.

Checks:
1. `apply_edges` body matches the reference statement for statement (only type annotations on the signature differ). Behaviour equal on 300 random inputs. sr 0 and -1 raise ValueError; all-zero raises "no voiced audio"; input unchanged; new list; clipping ok.
2. 100 signals, Random(2026): second call same length, no sample grows, values in [-1, 1], fade edges exactly 0.0, envelope bound holds. 0 failures.
3. x=[0.5]*100, sr 1000: length 240, y[80]=0.0, y[179]=0.0, y[81]=0.5/12. [0.0625]*100: last voiced sample 0.0; end-edge step 0.00208 (<= 0.0021).
4. Real WAV (440 Hz, 1.5 s, 24 kHz, 0.6, abrupt end): before: starts_at_sample0, start_abrupt, end_abrupt, clipped_tail all True, needs_fix True. After: lead_in 80.0 ms, tail 79.96 ms, all flags False, needs_fix False. Written file re-read and inspected: same result.
5. cut_margin_problems(0.3, 0.5, 0.2, 0.6, 0.10) returns []. Float 0.3-0.2 is 0.09999999999999998; the 1e-9 tolerance handles it.

Mutants (scratch copies): fade-in k/(n-1) fails 2 tests; full lead pad fails 5; no fade-out fails 4; cut_margin without tolerance fails 1. All caught.

Fixes before READY (comments and docstring only, no behaviour change):
1. `director/audio_edge.py` line 180, `apply_edges` docstring: replace "Idempotent in padding: only pads when the lead-in or tail is too short." with the three guarantees: second call keeps the length, values stay in [-1, 1] and never grow, fade edge samples are exactly 0.0.
2. `director/audio_edge.py` lines 205-207: replace the fade-in comment with "Fade-in skipped when the onset is already soft (abs <= 0.02)." The text "apply-twice == apply-once" is false (spec CORRECTION).
3. `director/audio_edge.py` line 212: delete the `# ponytail: fade-out skipped when input already ends at exact 0.0 ...` line. The rule it describes no longer exists; the code skips only when abs <= 0.02.
4. `director/test_audio_edge.py` line 308: delete the "EXPECTED TO FAIL" comment in `test_apply_edges_idempotent_with_subthreshold_head`. The test passes.
5. Spec wording: "no step bigger than 0.0021 at the edge" holds only at the fade-out. The fade-in step for [0.0625]*100 is 0.0052 (amplitude/12). Correct the spec wording; the code is right.

Rerun pytest after the fixes; expect 33 passed.

## Verdict: FIX FIRST

## J3 caption_fields (confirm review)
Reviewer: HK-J3b (haiku, medium). Read-only; no model, API or network call. Repo files not edited. Mutants in scratchpad copies.

Tests: `python -m pytest director/test_caption_fields.py -p no:cacheprovider -q` = 43 passed.

Earlier findings, status:
1. Unhashable id: fixed. `check_lines([{"id": ["x"], "lang": "hi", "spoken_text": "a"}])` returns `[]`, no raise. Key is `(repr(id), repr(lang))`. Not directly covered by a strict assertion (test only checks list and str items), acceptable.
2. Whitespace caption in diff_report: fixed. `caption_text "  "` gives same True, word_count_equal True, changed_words []. Covered by test_diff_report_whitespace_only_caption_is_absent. resolve_caption and check_lines also treat it as absent (checked by hand).
3. Non-text caption: fixed. resolve_caption and diff_report with caption_text 5 raise "line 1: caption_text is not text". Covered by test_resolve_caption_non_text_caption_raises and test_diff_report_non_text_caption_raises.

Hand checks: spoken_text 5 gives `["line 1: spoken_text is not text", "line 1: duplicate id for lang hi"]`. Both Hindi approved pairs resolve to the caption ('ब्याहीं', 'ग़लती'). NFC case: spoken "\u0929" vs caption "\u0928\u093c" counts as equal.

Mutations (scratchpad copies, all caught):
- M1 NFC removed from resolve_caption equality: 1 failed (test_nfc_and_nfd_count_as_equal).
- M2 approval truthy check (`if not approved`): 1 failed (test_resolve_caption_non_boolean_approval_refused).
- M3 whitespace caption treated as present in diff_report: 1 failed (test_diff_report_whitespace_only_caption_is_absent).

Not blocking: the eighth-run order rule (comparison before duplicate) is still not followed; check_lines runs the duplicate check before the comparison. The tenth-run decision says keep this order and the later section overrides the eighth, so this is not a fix item.

## Verdict: READY

## J12 plate_composite (confirm review)

Read-only. No repo file edited. pytest: 28 passed in 0.25 s. Parse OK, no line over 120, no walrus or match.

1. Feather border fix: fixed. `_box_blur` uses `np.pad(mode="edge")`. Full-True with feather_px=2 equals B and full-False equals A on a 6x6 probe, corners included. Covered by test_composite_feather_full_true_and_full_false_on_8x8.
2. save_rgb extension: fixed. Non-.png raises CompositeError before any temp file. Covered by test_save_rgb_refuses_jpg_name (also checks no file left).
3. diff_mask 24/25: fixed (strict `>`). Covered by test_diff_mask_threshold_is_strict_at_24_and_25 (mask sum == 9).
4. min_area 4/5: fixed. 4-pixel blob kept at 4, removed at 5. Covered by test_diff_mask_min_area_keeps_4px_blob_at_4_and_drops_at_5.
5. Half mask at the edge: correct in code (6x6 probe, row values 200, 200, 133, 66, 0, 0), but NOT covered. The only feather test uses one centre pixel.

Timing (768x1344x3 random pair): diff_mask 2.71 s; composite feather_px=4 1.61 s.

Mutations (scratchpad copies, each caught by its own test):
- M1 pad mode back to constant: 1 failed (feather 8x8 test).
- M2 extension check removed: 1 failed (jpg test).
- M3 threshold `>=`: 1 failed (24/25 test).

Gap to close before READY: add a test asserting a half mask blends strictly between A and B at the edge, e.g. `mask[:, :3] = True` on a 6x6 black A and 200 B with feather_px=1, then `0 < row[2] < 200` and `0 < row[3] < 200`, `row[0] == 200`, `row[5] == 0`.

## Verdict: FIX FIRST
Exact fix: add the half-mask edge test above to director/test_plate_composite.py and rerun pytest. The module code needs no change.
