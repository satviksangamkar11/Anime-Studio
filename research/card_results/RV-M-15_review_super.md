Defect 1 — test asserts exact hit placement, card requires ±1 frame

File: score/tests/test_cue_sheet_rows.py
Faulty line:
```python
    assert set(hits) == expected
```
Why it is wrong: The card requires hits on the impact frame ±1 frame. Exact set equality fails a correct implementation that places a hit at impact+1 (within tolerance), and it does not verify that every impact is covered by some hit within tolerance. It asserts a stricter, wrong result.
Exact fix: Replace the equality with a two-way tolerance check:
```python
    rows = cs.cue_rows(kalika_sheet)["rows"]
    hits_by_shot = {}
    for r in rows:
        if r["kind"] == "hit":
            hits_by_shot.setdefault(r["shot"], []).append(r["t_frame"])
    expected_by_shot = {}
    for s in kalika_sheet["shots"]:
        for i in s["impacts"]:
            expected_by_shot.setdefault(s["id"], []).append(i["at_frame"])
    for shot_id, frames in expected_by_shot.items():
        got = hits_by_shot.get(shot_id, [])
        for f in frames:
            assert any(abs(tf - f) <= 1 for tf in got), (shot_id, f, got)
    for shot_id, frames in hits_by_shot.items():
        for tf in frames:
            assert any(abs(tf - f) <= 1 for f in expected_by_shot.get(shot_id, [])), (shot_id, tf)
    assert all(r["tolerance_frames"] == 1 for r in rows if r["kind"] == "hit")
```

Defect 2 — `_rest_window` swallows bad `voice_rest` silently

File: score/cue_sheet.py
Faulty lines:
```python
def _rest_window(raw, t0, length_s):
    """The shot's voice_rest [t0, t1] (shot-relative in the pack) in reel seconds, or None."""
    rng = parse_range(raw.get("voice_rest"))
    if rng is None or rng[0] >= length_s:
        return None
    return [_r(t0 + rng[0]), _r(t0 + min(rng[1], length_s))]
```
Why it is wrong: A malformed or out-of-range `voice_rest` returns None with no warning, so bad input passes silently and no rest row is reported. This breaks the module's "never raises ... it reports" contract and is inconsistent with `_voice_lines`/`_sfx_cues`, which warn on bad ranges.
Exact fix: Add `where` and `warnings` parameters and report before returning None:
```python
def _rest_window(raw, t0, length_s, where, warnings):
    """The shot's voice_rest [t0, t1] (shot-relative in the pack) in reel seconds, or None."""
    raw_rest = raw.get("voice_rest")
    if raw_rest is None:
        return None
    rng = parse_range(raw_rest)
    if rng is None:
        warnings.append(_err("VOICE_REST_BAD", where, f"voice_rest unreadable: {raw_rest!r}"))
        return None
    if rng[1] > length_s:
        warnings.append(_err("VOICE_REST_OUTSIDE_SHOT", where,
                             f"voice_rest {rng[0]:g}-{rng[1]:g}s runs past shot end {length_s:g}s; clamped"))
    return [_r(t0 + rng[0]), _r(t0 + min(rng[1], length_s))]
```
Update the caller in `cue_rows` to pass the shot id and the warnings list.

VERDICT: FIX-FIRST