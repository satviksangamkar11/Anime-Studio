`h3/v4_to_h3.py:152` indexes the camera clause map directly: `motion, clause = CAMERA_MOVE_CLAUSES[cam.get("move")]`. An unknown `camera.move` is reported by blocking validation, but conversion continues and this line raises `KeyError`.

Use `motion, clause = CAMERA_MOVE_CLAUSES.get(cam.get("move"), CAMERA_MOVE_CLAUSES[None])` so invalid input cannot crash conversion; alternatively, stop processing that shot after recording the validation error.

VERDICT: FIX-FIRST