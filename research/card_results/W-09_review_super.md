Defect 1 — `add_settings_sha` does not decode the `__SETTINGS__` blob required by the card.

Faulty line:
```python
SETTINGS_RE = re.compile(r'for sid, settings in json\.loads\(base64\.b64decode\("([A-Za-z0-9+/=]+)"\)\)')
```
Why: W-09 requires decoding the `__SETTINGS__` blob before `split_blobs`. This regex matches a `for sid, settings in json.loads(...)` loop literal instead. Against the real runner it raises "settings blob not found" and writes no `settings_sha256`, breaking W-11's canary proof.
Fix:
```python
SETTINGS_RE = re.compile(r'__SETTINGS__\s*=\s*base64\.b64decode\("([A-Za-z0-9+/=]+)"\)')
```

Defect 2 — `legacy_rows` validates `input_video_strength` on the route input before `frame_row` instead of on `frame["input_video_strength"]` after.

Faulty lines:
```python
        strength = route.get("input_video_strength")
        if strength not in (None, 1.0):
            raise ValueError(f"{sid}: route {route.get('route')} needs input_video_strength {strength}, which Wan2GP bd1ff59 drops "
                             "(research/WAN2GP_SOFT_END_TRACE_2026-11-11.md); owner decision D4")
```
Why: Card step 5 requires checking `frame["input_video_strength"]` after `frame = shot_mode.frame_row(...)`. Checking the route value before `frame_row` lets any `frame_row` transformation/normalization pass silently or misreport the offending value.
Fix: Delete the pre-`frame_row` block and move the check after `frame = shot_mode.frame_row(shot, env)`:
```python
        frame = shot_mode.frame_row(shot, env)
        if frame["input_video_strength"] not in (None, 1.0):
            raise ValueError(f"{sid}: route {route.get('route')} needs input_video_strength {frame['input_video_strength']}, which Wan2GP bd1ff59 drops "
                             "(research/WAN2GP_SOFT_END_TRACE_2026-11-11.md); owner decision D4")
```

Defect 3 — `main` calls `routes.get(...)` without ensuring `routes` is a dict, so malformed JSON crashes with `AttributeError` instead of `ValueError`.

Faulty line:
```python
    if routes.get("lock_sha256") != lock.get("input_sha256"):
```
Why: `routes` comes from `json.loads` and may be a list or scalar; `routes.get` raises `AttributeError` before `legacy_rows` can validate it and raise the required `ValueError`.
Fix:
```python
    if not isinstance(routes, dict):
        raise ValueError("routes must be a JSON object with a 'routes' map")
    if routes.get("lock_sha256") != lock.get("input_sha256"):
        raise ValueError("stale routes: the routes file was made from another lock; rerun shot_router.py")
```

Defect 4 — Test asserts `ValueError` when `lock` is omitted, but `lock` is optional.

Faulty lines:
```python
def test_se_without_lock_end_position_refused():
    with pytest.raises(ValueError):
        b.legacy_rows(_story(("SHOT-001",)), "EP1", routes=ROUTES, env={})
```
Why: The card makes `lock` optional; omitting it must not raise. This test asserts the opposite, cannot pass, and is not one of the card's listed tests.
Fix: Delete the test (or replace it with a lock-provided success case).

VERDICT: FIX-FIRST