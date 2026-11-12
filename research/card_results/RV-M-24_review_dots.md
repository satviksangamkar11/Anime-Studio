**Defects found**

1. **Missing gate: background SSIM**  
   `director/keyframe_gate.py` never calls `background_lock` with `min_ssim=0.80` (the constant `KEYFRAME_MIN_SSIM` is defined but unused). The card requires a masked background SSIM ≥ 0.80; the code only checks `palette_ok` and `area_ok`.  
   *Faulty line:* `bg_result = background_lock(img_a, img_b, ma, mb, min_ssim=KEYFRAME_MIN_SSIM)` — the keyword is ignored because `background_lock` does not accept a `min_ssim` argument (it uses its own default 0.97).  
   *Fix:* Either change `background_lock` to accept `min_ssim` and use it, or add an explicit SSIM check using `diff_mask`/`plan` results. The test suite has no test for SSIM, which is why this slipped through.

2. **Missing gate: g3 cut jump DeltaE ≤ 8 between neighbours**  
   The card’s g3 rule is not implemented anywhere in `keyframe_gate.py`, `build_h3_batch.py`, or `render_controller.py`. There is no function that computes the colour difference between consecutive frames/neighbours and enforces the ≤ 8 limit.  
   *Fix:* Add a `g3_cut_jump` check (e.g. in `keyframe_gate.py` or a new module) that samples neighbouring frames from the rendered clip and fails if DeltaE2000 > 8.

3. **Missing gate: settings lock / render_version hashing**  
   `build_h3_batch.py` has `add_settings_sha` which computes `settings_sha256` and `render_version`, but the card also requires the **profile file sha** and **prompt sha** to be part of the render_version hash. Currently only `{pin, profile: profile_sha, settings: settings_sha256}` is hashed; the prompt hash is absent.  
   *Faulty line:* `sh["render_version"] = _sha({"pin": pin, "profile": profile_sha, "settings": sh["settings_sha256"]})` — missing `"prompt": prompt_sha`.  
   *Fix:* Include the per-shot prompt sha in the dictionary before hashing.

4. **Missing gate: drift iteration order recording**  
   The card says “drift iteration order recorded per render (simplify action, remove camera move, move B closer, split/chain, new seed, route change)”. `render_controller.py` defines `DRIFT_ORDER` and `record_drift_step`, but nothing calls `record_drift_step` during a render, and no field in the manifest or gate record stores the drift log. The requirement is therefore unmet.  
   *Fix:* After each render attempt, call `record_drift_step` with the applied change and persist the resulting list in the shot’s record (e.g. in `render_manifest.json` or the timeline lock).

5. **Missing gate: stop after 3 renders and escalate**  
   `render_controller.py` has `MAX_RENDERS_PER_SHOT = 3` and `render_allowed`, but `render_allowed` is never called in the render pipeline (it is defined but unused). A 4th render is not refused.  
   *Fix:* In the render loop (or in `build_h3_batch.py` / the runner), call `render_allowed(history, shot_id, owner_flag)` before issuing a new render; if it returns `False`, abort and escalate.

6. **Tautological test: `test_min_ssim_is_080_not_the_097_default`**  
   The test only asserts that the constant `KEYFRAME_MIN_SSIM == 0.80`. It does not verify that the gate actually uses this value or that the SSIM check is performed. A change to the constant or its removal would not fail this test.  
   *Faulty line:* `assert kg.KEYFRAME_MIN_SSIM == 0.80` — tautological with respect to the gate behaviour.  
   *Fix:* Add a test that runs `gate()` with two images whose SSIM is, say, 0.75 (below 0.80) and expects `checks["background_lock"]` to be `False`.

7. **Test does not cover the “g3 cut jump” rule**  
   The card lists “g3 cut jump DeltaE <= 8 between neighbours” as a rule, but no test in `test_keyframe_gate_m24.py` (or any other test file) addresses it. The test file is therefore incomplete per the card’s “one per gate/rule” requirement.  
   *Fix:* Add a test that feeds two neighbouring frames with a DeltaE > 8 and expects the gate to fail.

---

VERDICT: FIX-FIRST