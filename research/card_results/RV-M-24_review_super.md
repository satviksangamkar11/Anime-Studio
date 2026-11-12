defect 1 — director/keyframe_gate.py
Faulty line:
```python
    pm = posture_matches(chars_a, chars_b, expect_posture)
```
Why wrong: `posture_matches` raises `ValueError` for a malformed `(start, end)` pair, and because `expect_posture or {}` does not coerce a bare string, a legacy string shape makes `expect_posture[cid]` raise `TypeError` (string indices must be integers). `gate` catches neither, so a malformed sheet crashes the gate instead of writing a failed record and returning `False`.
Exact fix: validate the mapping inside `posture_matches` before the loop, and guard the call in `gate`:
```python
    try:
        pm = posture_matches(chars_a, chars_b, expect_posture)
    except (ValueError, TypeError):
        pm = False
```
and in `posture_matches`, replace `expect_posture = expect_posture or {}` with:
```python
    if not isinstance(expect_posture, dict):
        raise ValueError("expect_posture must be a dict of (start, end) pairs")
```

defect 2 — director/build_h3_batch.py
Faulty line:
```python
        sh["render_version"] = _sha({"pin": pin, "profile": profile_sha, "settings": sh["settings_sha256"]})
```
Why wrong: M-24 requires `render_version` to hash {Wan2GP pin, profile file sha, steps, cfg, sampler, seed, resolution, prompt sha, A/B sha}. This omits prompt sha and A/B sha entirely, so a prompt or keyframe swap can leave `render_version` unchanged.
Exact fix: include the shot’s prompt and A/B image identities:
```python
        sh["render_version"] = _sha({
            "pin": pin,
            "profile": profile_sha,
            "settings": sh["settings_sha256"],
            "prompt_sha": _sha(sh.get("prompt_override", "")),
            "a_sha": _sha(sh.get("start", "")),
            "b_sha": _sha(sh.get("end", "")),
        })
```

defect 3 — director/build_h3_batch.py
Faulty line:
```python
        sh["seed"] = settings[sh["id"]].get("seed", 42)          # M-29: the seed that renders (h3_director default 42)
```
Why wrong: M-24 requires seed fixed per shot and stored. `legacy_rows` already stores a per-shot seed; this line discards it for the runner seed or constant 42, so shots are not seeded per shot and a missing settings seed collapses every shot to 42.
Exact fix: preserve the existing per-shot seed:
```python
        sh["seed"] = sh.get("seed", settings[sh["id"]].get("seed", shot_seed(sh["id"])))
```

defect 4 — director/build_h3_batch.py
Faulty line:
```python
    profile_sha = _sha(h3_director.PRESET)
```
Why wrong: M-24 requires the profile *file* sha. Hashing the in-memory `h3_director.PRESET` object is not the profile file on disk and will not change when the profile file changes.
Exact fix: accept the profile file sha as a parameter and use it directly:
```python
def add_settings_sha(manifest, script, pin=WAN2GP_PIN, profile_sha=""):
    ...
    if not profile_sha:
        raise ValueError("profile file sha is required")
```
and remove the `_sha(h3_director.PRESET)` line, using the `profile_sha` parameter in place of `profile_sha`.

VERDICT: FIX-FIRST