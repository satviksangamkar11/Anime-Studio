Defect 1 — `camera.move` accepts `"locked"`, which is not in the card's enum, and L11 builds its moving flag around it.

- Faulty line (`director/blocking.py`): `_CAMERA_11_MOVES = ("locked", "push_in", "pull_back", "pan_left", "pan_right", "tilt_up", "tilt_down", "track_left", "track_right", "orbit_left", "orbit_right", "crane_up", "crane_down", "handheld_drift")`
- Why wrong: The card fixes `camera.move` to `(null, push_in, pull_back, pan_left/right, tilt_up/down, track_left/right, orbit_left/right, crane_up/down, handheld_drift)`. `"locked"` is absent, so BLK-S06 admits an out-of-spec value silently instead of rejecting it.
- Fix: drop `"locked"`:
  `_CAMERA_11_MOVES = ("push_in", "pull_back", "pan_left", "pan_right", "tilt_up", "tilt_down", "track_left", "track_right", "orbit_left", "orbit_right", "crane_up", "crane_down", "handheld_drift")`

- Faulty line (`director/blocking_lint.py`): `moving_camera = move not in (None, "locked")`
- Why wrong: L11 is "mode fixed <=> move null", so moving must be `move is not None`; special-casing `"locked"` is wrong now that `"locked"` is not a legal move.
- Fix: `moving_camera = move is not None`

Defect 2 — `cast[].expression` is only type-checked, not validated against the bible list (BLK-S16).

- Faulty line (`director/blocking.py`): `if "expression" in member and not _is_str(member["expression"]):\n        problems.append("%s: BLK-S16 cast expression must be str" % shot_id)`
- Why wrong: BLK-S16 requires `expression` from the bible list; the code accepts any string, so a non-bible expression passes silently.
- Fix: add `_EXPRESSIONS` from the project expression bible (it must contain `"resolve"` so the Opus sheet still validates) and replace the check with:
  `if "expression" in member and member["expression"] not in _EXPRESSIONS:\n        problems.append("%s: BLK-S16 cast expression not in bible list" % shot_id)`

VERDICT: FIX-FIRST