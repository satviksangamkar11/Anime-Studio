You are the coder hardening two existing modules of a story-agnostic video-prompt engine: h3/render_controller.py and h3/schema_and_linter.py (both in context, complete; the spec is h3/SPEC.md; tests in h3/tests are context and must keep passing).
A Dots review (context: _dots_review_controller.md) found path-traversal and robustness problems. Fix ALL of them, with minimal changes, keeping every public function name and behaviour that the existing tests rely on:
1. IDs from the story JSON (episode_id, shot_id) are used in file names: allow only the pattern ^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$. In schema_and_linter add a lint error with code ID-01 (message starts with the shot id or "episode") for any id that does not match, and in render_controller refuse (exit 1, nothing written or deleted) when an id is unsafe BEFORE any path is built. The controller must also assert, before every write or delete, that the resolved target stays inside its own out/build folder (Path.resolve().is_relative_to).
2. Picture paths (picture_1_path, picture_2_path, flow_source_*) and reuse resolution: reject absolute paths, drive letters and any ".." segment (lint code KF-07). asset_root may be absolute only when it is given by the caller (CLI/story file field is allowed), but a picture path never may be.
3. Replace fragile dict indexing (kf[label], kf["reused"], other direct [] on optional keys reported by the review) with .get and a clear lint/controller error instead of a KeyError traceback.
4. NEW RULE (owner decision 2026-11-06: the video model generates ALL the sound effects; background music is added by the owner later, so the video prompt must not ask for music): in the linter add code SD-01: sound_plan.overall_soundscape must be a non-empty single sentence of at least 40 characters (after sanitize_single_line) describing the sound effects of the shot, and sound_plan.non_diegetic_music must equal "N/A" (case-insensitive) unless the profile sets "allow_model_music": true; add SD-02 as a WARNING when the soundscape does not contain any of the words sound, hiss, rustle, splash, wind, water, step, breath, hum, whoosh, roar, crack, thud, drip, flow, ring, voice (case-insensitive) to catch empty placeholders. The assembly plan must KEEP the video model's audio (it already does; do not drop it).
5. Add tests in a NEW file h3/tests/test_hardening.py (use the existing fixtures/helpers in h3/tests/synth.py and conftest.py, read them from context): unsafe episode/shot ids (../x, a/b, absolute, empty, 70 chars) refused by lint and by the controller with nothing written; picture path with .. and absolute rejected; the controller never writes or deletes outside its out folder even if the story tries; SD-01 failing cases (empty, short, music other than N/A) and passing case; SD-02 warning; allow_model_music profile flag.
Return ALL allowed files complete. Test gate: the whole h3 test folder must pass.

STATE: the three allowed files already exist (context) and 114 tests pass; 22 tests in h3/tests/test_hardening.py fail. The fixture h3/tests/synth.py is already updated to the sound rule (music N/A). Keep the existing code; make the MINIMAL edits so ALL h3 tests pass (fix the modules, or the new tests if a test itself is wrong). Failing output follows:
        res = lint_story(story)
>       assert any("KF-07" in e and "flow_source_a" in e for e in res["errors"])
E       assert False
E        +  where False = any(<generator object test_flow_source_path_with_traversal_rejected_by_lint.<locals>.<genexpr> at 0x0000024B7418ACF0>)

h3\tests\test_hardening.py:67: AssertionError
____ test_flow_source_path_with_traversal_rejected_by_lint[/absolute.png] _____

tmp_path = WindowsPath('C:/Users/Satvik/AppData/Local/Temp/pytest-of-Satvik/pytest-1769/test_flow_source_path_with_tra2')
bad_rel = '/absolute.png'

    @pytest.mark.parametrize("bad_rel", ["../evil.png", "sub/../evil.png", "/absolute.png", "C:\\evil.png"])
    def test_flow_source_path_with_traversal_rejected_by_lint(tmp_path, bad_rel):
        story = build_story(str(tmp_path))
        story["episodes"][0]["shots"][0]["fl2va_keyframes"]["flow_source_a"] = bad_rel
        res = lint_story(story)
>       assert any("KF-07" in e and "flow_source_a" in e for e in res["errors"])
E       assert False
E        +  where False = any(<generator object test_flow_source_path_with_traversal_rejected_by_lint.<locals>.<genexpr> at 0x0000024B7418B920>)

h3\tests\test_hardening.py:67: AssertionError
_______________ test_controller_does_not_write_outside_out_dir ________________

tmp_path = WindowsPath('C:/Users/Satvik/AppData/Local/Temp/pytest-of-Satvik/pytest-1769/test_controller_does_not_write0')
capsys = <_pytest.capture.CaptureFixture object at 0x0000024B741B62C0>
monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x0000024B7417B0B0>

    def test_controller_does_not_write_outside_out_dir(tmp_path, capsys, monkeypatch):
        # Even if a shot_id passes ID validation, _safe_join guards the write.
        story = build_story(str(tmp_path))
        path = tmp_path / "story.json"
        path.write_text(json.dumps(story))
        out = tmp_path / "out"
        # Monkey-patch _safe_join to simulate a traversal attempt (should not happen in real code)
        import h3.render_controller as rc
        original_safe_join = rc._safe_join
        def bad_safe_join(base, *parts):
            if parts and parts[0] == "SYN_A":
                raise ValueError("path traversal attempt")
            return original_safe_join(base, *parts)
        monkeypatch.setattr(rc, "_safe_join", bad_safe_join)
        code, text = rc_main(["--story-file", str(path), "--scope", "all", "--out-dir", str(out)], capsys)
>       assert code == 1
E       assert 0 == 1

h3\tests\test_hardening.py:98: AssertionError
=========================== short test summary info ===========================
FAILED h3/tests/test_e2e_sample.py::test_offline_end_to_end_is_3_of_3_ready
FAILED h3/tests/test_e2e_sample.py::test_offline_main_prints_the_summary_line
FAILED h3/tests/test_e2e_sample.py::test_repair_loop_fixes_on_the_second_round
FAILED h3/tests/test_e2e_sample.py::test_unparseable_reply_is_a_repair_round
FAILED h3/tests/test_e2e_sample.py::test_think_block_and_code_fence_are_stripped
FAILED h3/tests/test_hardening.py::test_unsafe_ids_rejected_by_lint[../x] - a...
FAILED h3/tests/test_hardening.py::test_unsafe_ids_rejected_by_lint[a/b] - as...
FAILED h3/tests/test_hardening.py::test_unsafe_ids_rejected_by_lint[/absolute]
FAILED h3/tests/test_hardening.py::test_unsafe_ids_rejected_by_lint[C:\\abs]
FAILED h3/tests/test_hardening.py::test_unsafe_ids_rejected_by_lint[] - asser...
FAILED h3/tests/test_hardening.py::test_unsafe_ids_rejected_by_lint[aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa]
FAILED h3/tests/test_hardening.py::test_unsafe_ids_rejected_by_lint[aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa]
FAILED h3/tests/test_hardening.py::test_unsafe_ids_rejected_by_lint[a-b_c] - ...
FAILED h3/tests/test_hardening.py::test_unsafe_ids_rejected_by_lint[123] - as...
FAILED h3/tests/test_hardening.py::test_unsafe_ids_rejected_by_lint[aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa]
FAILED h3/tests/test_hardening.py::test_picture_path_with_traversal_rejected_by_lint[../evil.png]
FAILED h3/tests/test_hardening.py::test_picture_path_with_traversal_rejected_by_lint[sub/../evil.png]
FAILED h3/tests/test_hardening.py::test_picture_path_with_traversal_rejected_by_lint[/absolute.png]
FAILED h3/tests/test_hardening.py::test_flow_source_path_with_traversal_rejected_by_lint[../evil.png]
FAILED h3/tests/test_hardening.py::test_flow_source_path_with_traversal_rejected_by_lint[sub/../evil.png]
FAILED h3/tests/test_hardening.py::test_flow_source_path_with_traversal_rejected_by_lint[/absolute.png]
FAILED h3/tests/test_hardening.py::test_controller_does_not_write_outside_out_dir
22 failed, 114 passed in 2.64s
