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