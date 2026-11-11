Defect 1 — `director/clip_qa.py`, `extract` ffmpeg command
```python
    cmd = ["ffmpeg", "-v", "error", "-i", str(clip), "-vf", vf, "-fps_mode", "passthrough",
           "-f", "rawvideo", "-pix_fmt", "gray", "-"]
```
Why: The card mandates `-vsync 0`. The code substitutes `-fps_mode passthrough`, which is not the specified invocation and can be rejected by ffmpeg builds that do not expose that option for rawvideo output, turning extraction into a crash path.
Fix: Replace `"-fps_mode", "passthrough"` with `"-vsync", "0"`.

Defect 2 — `director/clip_qa.py`, `features` lpips record
```python
        "end": {"ssim": end_ssim, "lpips": 0.0, "cosine": cosine},  # ponytail: lpips not measured
```
Why: The card requires passing `lpips=0.0` and recording "lpips not measured". A comment is not a record; nothing in the returned `end` dict or `results` documents that lpips was skipped.
Fix: Add `"lpips_note": "lpips not measured"` to the `end` dict, e.g. `"end": {"ssim": end_ssim, "lpips": 0.0, "cosine": cosine, "lpips_note": "lpips not measured"}`.

Defect 3 — `director/clip_qa.py`, `accept` record field name
```python
    rec = {"code": code, "note": str(note), "by": "owner", "at": datetime.datetime.now().isoformat(timespec="seconds")}
```
Why: The card specifies `owner_accept {code, date, note}`. The code writes the timestamp under `"at"` instead of `"date"`.
Fix: Change `"at":` to `"date":`.

Defect 4 — `director/test_clip_qa.py`, `test_owner_accept_unblocks_and_is_recorded`
```python
    assert "at" in updated_qa["owner_accept"][0]
```
Why: The test asserts the wrong field name (`at` instead of the card's `date`), so it cannot catch Defect 3 and does not cover the card's `owner_accept` record format.
Fix: Change to `assert "date" in updated_qa["owner_accept"][0]`.

Defect 5 — `director/clip_qa.py`, `CRITICAL_CODES` unacceptability
```python
CRITICAL_CODES = frozenset({"FRAME_COUNT", "CORRUPT"})
```
```python
    if code in CRITICAL_CODES:
        raise ClipQAError("critical code cannot be accepted: " + str(code))
```
```python
    crit = [c for c in codes if c in CRITICAL_CODES]
    if crit:
        return ["verdict failed on critical code, no owner accept can clear it: " + ", ".join(crit)]
```
Why: The card says `clip_ok` blocks on "verdict fail without owner_accept" and `accept` records owner accept; it creates no unacceptable codes. `CRITICAL_CODES` makes `clip_ok` block even when an owner accept exists (wrong result) and makes `accept` refuse codes the card allows.
Fix: Delete `CRITICAL_CODES`, delete the critical-code refusal in `accept`, and rewrite `_uncleared` as:
```python
def _uncleared(codes, records):
    accepted = {_canon(r.get("code")) for r in records}
    rest = [c for c in codes if _canon(c) not in accepted]
    return ["verdict failed, not cleared by owner accept: " + ", ".join(rest)] if rest else []
```

VERDICT: FIX-FIRST