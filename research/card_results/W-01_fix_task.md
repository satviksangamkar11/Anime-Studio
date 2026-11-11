Two independent reviewers found problems in the finished gap card below. Fix every finding that is CORRECT (check it against the code first; the Dots review is noisier than the Luna review and may be wrong or describe a line that does not exist: ignore a finding you can show is wrong). For each fixed defect add or strengthen a test in the card's test file so the test fails before the fix. Keep every existing test passing. Edit only the allowed files; keep everything else byte-identical; do not add code that reads files at import time.

CARD:
### W-01: J8 port of the batch builder and Colab runner (git, not a folder diff)
- **Files:** director/build_h3_batch.py NEW; director/run_colab_batch.py NEW; director/test_build_h3_batch.py NEW; director/test_run_colab_batch.py NEW (all four from branch `v4-architecture-2026-11-07`); director/h3_director.py (one line).
- **Change:**
  1. Record in the checklist: `git diff --stat merge-v4-universal-2026-11-07 v4-architecture-2026-11-07 -- director/run_kaggle.py director/t0_pack/run_t0_colab.py director/h3_director.py h3/compile_h3_sing8.py h3/v4_to_h3.py h3/schema_and_linter.py`.
  2. Run `git checkout v4-architecture-2026-11-07 -- <the 4 NEW paths>`. Only those paths, never a whole-tree checkout.
  3. Edit merge h3_director.py:350. The faulty line is `"prompt": prompt_for(shot, frames, bible), "image_mode": 0, ...`. It becomes `"prompt": shot.get("prompt_override") or prompt_for(shot, frames, bible), ...`, which is the other tree's line 350. Without it, every `prompt_override` the builder writes (build_h3_batch.py:141) is silently replaced by the old director prompt.
  4. Keep the merge versions of all h3/* files (MISTAKES W6).
  5. Run the `harden()` anchors check: merge run_kaggle.py lines 40, 44, 51, 68, 69 must hold the exact strings that harden counts (already checked by reading: identical).
- **Tests to add (append to test_build_h3_batch.py):**
  - `test_prompt_override_reaches_settings`: synth story; `rows = legacy_rows(story, ep)`; `s = h3_director.settings_for(rows[0])`. Assert `s["prompt"] == rows[0]["prompt_override"]` and that the prompt does not start with `"[Shot 1] A "` (the prompt_for body).
  - `test_real_compiler_prompt_has_no_blank_line`: the same rows, built with the real compiler (no monkeypatch). Assert `"\n\n" not in prompt_override`. Today the raw compiler output has `"\n\n"` (compile_h3_sing8.py:83) and the builder collapses it.
  - `test_crlf_blank_line_collapsed`: monkeypatched compiler returns `"a\r\n\r\nb"`. Assert the result is `"a\nb"`. Note: the raise at build_h3_batch.py:138 cannot be reached after the regex on line 137. The real guard is the regex, and W-07 adds a compiler guard.
  - The existing `test_wrong_gpu_is_stopped` and `test_prompt_has_no_blank_line` must pass in the merge tree. They are the survival proof for problems 34 and 30.
- **Closes:** 36; 30 and 34 shown to survive the port. Bugs MISTAKES W6; prompt_override drop (new).
- **Depends on:** none.
- **Collisions:** creates the files used by W-09, W-10, W-11.
- **Acceptance:** `python -m pytest director/test_build_h3_batch.py director/test_run_colab_batch.py director/test_h3_director.py -q`; `git status --short director` lists exactly the 4 new files and h3_director.py.
- **Owner decision:** none. **Risk of a second attempt:** low. Note: `test_vendored_wheel_*` needs `D:\aai work\vendor\chumpy_0.71\...whl` to exist.



REVIEW BY LUNA:
`director/run_colab_batch.py`: `while waited <= proof_seconds:` allows one extra `sleep(poll)` after the 180-second proof deadline. With the default 15-second poll, the runner can wait until 195 seconds before stopping the session. Stop at the deadline by changing it to `while waited < proof_seconds:` and avoid sleeping past the remaining time.

VERDICT: FIX-FIRST.

REVIEW BY DOTS:
**Defects found**

1. **`test_crlf_blank_line_collapsed` cannot fail.** The regex on line 137 already collapses `\r\n` and blank lines, so the monkeypatched `"a\r\n\r\nb"` is guaranteed to become `"a\nb"` regardless of any later code. The test asserts the only possible output; it has no discriminating power.  
   **Fix:** the test must exercise the *raise* path that the card says is unreachable today. Replace the body with:  
   ```python
   monkeypatch.setattr(b, "compile_fl2va_prompt", lambda sh, reg: {"compiled_prompt": "a\r\n\r\nb"})
   story = {"registry": {}, "episodes": [{"episode_id": "EP1", "shots": [{"shot_id": "SHOT-001", "timing_and_lattice": {"pixel_frames": 175}}]}]}
   with pytest.raises(ValueError, match="blank line left"):
       b.legacy_rows(story, "EP1")
   ```
   (This documents the current guard; W-07 is expected to change the regex so the raise becomes reachable.)

2. **`test_prompt_override_reaches_settings` uses an unregistered shot id.** `row = dict(rows[0], id="SHOT-01")` is not in the synth story's registry, so `h3_director.settings_for` raises `KeyError` (or returns a prompt that fails the assertion) instead of verifying that `prompt_override` survives. The card requires the test to prove the override reaches settings.  
   **Fix:** use a real shot id from the synth story:  
   ```python
   rows = b.legacy_rows(_synth_story(), "SYN_EP1")
   s = h3_director.settings_for(rows[0])
   assert s["prompt"] == rows[0]["prompt_override"]
   assert not s["prompt"].startswith("[Shot 1] A ")
   ```

3. **`test_pip_install_is_retried_after_a_transient_failure` executes arbitrary hardened script fragments.** `exec(s[...])` runs whatever `harden()` injected (the `run_limited` helper, the `sh_retry` function, the HF token line, etc.) in a bare namespace. Any future change to `harden()` (e.g. an accidental `os.system` call) would execute with no sandbox. The test also depends on `harden()`'s exact slicing rather than importing `sh_retry` directly.  
   **Fix:** extract `sh_retry` into a module-level helper in `build_h3_batch.py` (e.g. `def sh_retry(cmd, log, tries=4, sh=None, note=None, time=None):`) and have `harden()` inject only that function. The test then imports `b.sh_retry` and passes stubs explicitly, with no `exec`.

4. **`test_script_reads_the_hf_token_when_present` contains a tautological negative check.**  
   `assert "hf_" not in s.replace("HF_", "").replace("/content/.hf_token", "").replace("hf_home", "")`  
   strips the very substrings that contain `"hf_"`, so the assertion can never fail; it tests nothing.  
   **Fix:** remove the assertion, or replace it with a check that the token value is absent, e.g. `assert "hf_token" not in s` (if the token is written elsewhere) or simply drop the line.

5. **`test_vendored_wheel_is_shipped_and_the_install_points_at_it` asserts a path that does not exist on this PC.**  
   `WHEEL = Path("D:/aai work/vendor/chumpy_0.71/chumpy-0.71-py3-none-any.whl")` is used by `write_wheel_upload` (called via `tmp_path` in the test, so this is not triggered), but the card explicitly notes the test needs that file to exist. On a CI runner without that drive the module import and any test calling `write_wheel_upload()` with the default argument will fail.  
   **Fix:** make the default wheel path configurable via an environment variable (e.g. `CHUMPY_WHEEL`) and skip the test if it is unset:  
   ```python
   WHEEL = Path(os.environ.get("CHUMPY_WHEEL", "D:/aai work/vendor/chumpy_0.71/chumpy-0.71-py3-none-any.whl"))
   ...
   @pytest.mark.skipif(not WHEEL.exists(), reason="vendored wheel not on this machine")
   def test_vendored_wheel_is_shipped_and_the_install_points_at_it(tmp_path): ...
   ```

VERDICT: FIX-FIRST