**Defect 1 — `test_approved_diff_used` is tautological and does not test the card requirement.**

In `director/test_build_final_reel_captions.py` the test calls `b.spoken_cues_real(...)` but never checks that the unapproved caption was rejected. The `caption_diff_approved` flag is read by `caption_fields` inside `cf.caption_lines(lines)`; the test only inspects the returned words. Because `caption_fields` silently falls back to `spoken_text` when `caption_diff_approved` is missing or false, the test passes whether or not the approval gate is enforced.

**Faulty line (test):**
```python
cues = b.spoken_cues_real(rw, report_for("SHOT-010", "SHOT-010-D1"), "hi", manifest_for("SHOT-010-D1", spoken))
words = [w["text"] for c in cues for w in c["words"]]
assert words == ["ग़लती", "हुई"]
```

**Fix:** the test must assert that an unapproved diff raises, and that the approved diff is used. Add a `pytest.raises(SystemExit, match="not approved")` block for `approved=False` (which already exists in `test_unapproved_caption_diff_raises`, so this test is redundant as written) or, better, drop this test and keep only `test_unapproved_caption_diff_raises` plus a positive check that the approved caption text appears in the cues.

---

**Defect 2 — `test_unapproved_caption_diff_raises` matches the wrong error message.**

The test expects `SystemExit` matching `"not approved"`, but `caption_fields` raises `CaptionError` with a message that does not contain that phrase. The test cannot fail unless the message is changed, so it is a weak test.

**Faulty line (test):**
```python
with pytest.raises(SystemExit, match="not approved"):
```

**Fix:** change the match to the actual message emitted by `caption_fields` (e.g. `"caption_diff_approved"` or the exact wording from `core/caption_fields.py`).

---

**Defect 3 — `test_crop_before_ass_in_argv` asserts on a substring that is always present.**

The assertion `"[0:v]scale=1098:1920:flags=lanczos,crop=1080:1920:9:0,ass=filename=" in graph` is true by construction of the graph string; it does not verify ordering. The second assertion (`graph.index("crop=1080:1920:9:0") < graph.index("ass=filename=")`) does verify ordering, but the first assertion is tautological and should be removed or replaced with a check that `pre_vf` actually appears before `ass=`.

**Faulty line (test):**
```python
assert "[0:v]scale=1098:1920:flags=lanczos,crop=1080:1920:9:0,ass=filename=" in graph
```

**Fix:** remove this line; the index comparison already covers the requirement.

---

**Defect 4 — `test_gate_d_default_unchanged` compares against a string built with `build_subtitles_filter`, so it cannot detect a regression in `build_final_mux_argv`.**

The test reconstructs the expected graph by calling `gd.build_subtitles_filter(...)`. If the implementation of `build_final_mux_argv` changes the order or the filter text, this test will still pass because it derives the expected value from the same helper. It is a tautology for the very change it is meant to guard.

**Faulty line (test):**
```python
assert graph == "[1:a]anull[master];[0:v]" + gd.build_subtitles_filter("c.ass", "styles/fonts") + "[vsub]"
```

**Fix:** hard-code the expected string:
```python
assert graph == "[1:a]anull[master];[0:v]ass=filename=c.ass:fontsdir=styles/fonts:shaping=complex[vsub]"
```

---

**Defect 5 — `test_export_probes_1080x1920` does not exercise the `delivery_vf` branch it is named for.**

The test calls `b.mux_argv(..., pre_vf=b.delivery_vf(b.probe_size(video)))`. `probe_size` returns `(768, 1344)`, so `delivery_vf` returns `DELIVERY_VF`. This is fine, but the test never checks that `delivery_vf` was actually called or that the filter contains the crop; it only checks the final frame size. A regression in `delivery_vf` (e.g. returning `None` for 768×1344) would still produce a 1080×1920 output because the ASS `PlayRes` is 1080×1920 and libass would letterbox. The test therefore passes silently on a wrong code path.

**Faulty line (test):**
```python
assert b.probe_size(export) == (1080, 1920)
```

**Fix:** also assert that the filter graph in `argv` contains the crop:
```python
graph = argv[argv.index("-filter_complex") + 1]
assert "crop=1080:1920:9:0" in graph
```

---

**Defect 6 — `build_final_reel.py` `spoken_cues_real` does not enforce `caption_diff_approved` before calling `caption_fields`.**

The card requires that an unapproved caption diff stops the build. The code builds the `lines` list with `caption_diff_approved` from the shot dict, but the enforcement is delegated to `cf.caption_lines`. If `caption_fields` does not raise on `approved=False`, the build continues with the spoken text instead of the caption — a silent pass.

**Faulty line (`build_final_reel.py`):**
```python
lines.append({"id": line_id, "lang": lang, "spoken_text": spoken, "caption_text": src[line_id].get("caption_text"),
              "caption_diff_approved": src[line_id].get("caption_diff_approved", False)})
```

**Fix:** add an explicit guard before the `caption_fields` call:
```python
if src[line_id].get("caption_text") is not None and not src[line_id].get("caption_diff_approved", False):
    raise SystemExit(f"{line_id}: caption diff not approved by the owner")
```

---

**Defect 7 — `gate_d_audio.py` `build_final_mux_argv` default `pre_vf=None` is not preserved for existing callers.**

The card says "Default None leaves other callers unchanged." The function signature already defaults to `None`, but the graph construction uses `pre = f"{pre_vf}," if pre_vf else ""`, which is correct. However, the guard `if pre_vf and not burn_captions: raise ValueError(...)` raises when `pre_vf` is set and `burn_captions=False`. This is intended, but the test `test_gate_d_default_unchanged` calls with `burn_captions` defaulting to `True` and `pre_vf` defaulting to `None`, so the guard is not exercised. The default path is unchanged, so this is not a defect in the code, but the test does not cover the `pre_vf=None` + `burn_captions=False` combination that other callers may use.

No fix needed; the test coverage gap is noted but does not violate the card.

---

**Defect 8 — `test_no_caption_fixes_symbol` checks `hasattr(b, "CAPTION_FIXES")` but the card also requires the loop at lines 168-170 to be deleted.**

The test only checks for the symbol's absence. If the loop were still present but the constant renamed, the test would pass while the card requirement is not met.

**Faulty line (test):**
```python
assert not hasattr(b, "CAPTION_FIXES")
```

**Fix:** also assert that the source file does not contain the old loop pattern:
```python
assert "for _fix in CAPTION_FIXES" not in (HERE / "build_final_reel.py").read_text()
```

---

VERDICT: FIX-FIRST