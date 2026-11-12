- **Background SSIM does not use the required 0.80 threshold.** Faulty line: `bg_result = background_lock(img_a, img_b, ma, mb, min_ssim=KEYFRAME_MIN_SSIM)`. `background_lock` ignores that keyword and uses its default threshold, so the required gate is not enforced. Fix `background_lock` to accept and apply `min_ssim`, or perform an explicit masked SSIM check in `gate()`. The test `test_min_ssim_is_080_not_the_097_default` checks only the constant, not the gate behavior.

- **The three render cap is not enforced.** Faulty line: `ok, reason = render_allowed(history, sid, owner_flag)` in `run_colab_batch.py`’s `render_gate` (near line 359). It checks the count, but the count comes from `attempts_for(history, sid)`, while this runner records completed fetches in `record_render` as `kind: "render"`. Confirmed only if `attempts_for` excludes those records; its behavior must be checked to establish this defect. The card requires refusing a fourth render without an owner flag.

- **Drift order is not recorded per render.** `record_drift_step` only produces an updated list in the preflight log; the render history record stores only the latest step: `"... \"drift_step\": drift_step"`. Fix `record_render` to persist the full ordered drift list for that shot with each render.

- **No M-24 test covers the G3 cut-jump rule.** The M-24 test files shown cover palette thresholds and render-version changes, but none asserts that neighboring clips with dE2000 above 8 fail. Add a test for `h3.assemble_reel.colour_seams` using a failing neighboring cut.

- **Render-version hash omits the prompt SHA and A/B content SHA.** Faulty line: `sh["render_version"] = _sha({"pin": pin, "profile": profile_sha, "settings": sh["settings_sha256"]})`. The settings hash may contain prompt text and A/B paths, but it does not hash the prompt explicitly or the A/B image bytes. Fix by including the prompt SHA and A/B SHA values in the version input.

VERDICT: FIX-FIRST