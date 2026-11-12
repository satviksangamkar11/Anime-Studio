# W2-B (G3, G7)
- G3: compile_h3_sing8._fl2va start_only header = official I2VA first-frame line; body unchanged (linter PR-01 needs the old body start). FL2VA golden unchanged. Also edited h3/schema_and_linter.py (PROMPT_I2VA_RE header + PR-02 ignores "(from [Shot 1])"), required, outside the listed files.
- G7: build_h3_batch.legacy_rows refuses pixel_frames<124 (allow_107 / --allow-107 override); timeline_lock_core.plan_pixels/plan_shots take preset="pika"/"pika6" -> n>=7.
- Finding: at 124 frames H3 handle rules (head 8..35, MO-03 impact 89..105) reject edits <~89 frames, so the 80-frame trimmed edit does NOT fit under Pika (ValueError "pixel 124"); review claim wrong.
- Tests added: test_s_header_is_official_i2va_line, test_s_prompt_has_no_picture_2 (h3/tests/test_m02_start_only.py), test_pika6_refuses_107 (test_build_h3_batch_w09.py), test_lock_picks_124_for_short_shot (test_timeline_lock_m12.py).
- Not wired: write_timeline_lock.py does not yet pass preset to plan_shots.
