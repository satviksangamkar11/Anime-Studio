- [keyframe_gate.py](D:/aai%20work/anime_studio_merge/director/keyframe_gate.py:38): `if not review.get("full_size"):` accepts truthy non-booleans such as `"yes"` or `1`, although the card requires `full_size: true`. Require `review.get("full_size") is True`.

- [keyframe_gate.py](D:/aai%20work/anime_studio_merge/director/keyframe_gate.py:107): `if cast_a != cast_b:` can accept invalid counts when both sides contain the same string, for example `"3"`, and the required count is also `"3"`. Validate that each review `cast_count` is a non-negative integer (excluding booleans) and that the required count has the same valid type before parity checks.

- [keyframe_gate.py](D:/aai%20work/anime_studio_merge/director/keyframe_gate.py:166): `checks["area_ok"]` uses `1 - mb.sum()/mb.size`, which measures the area outside B’s character mask. The card requires the D-IMG area gate; `background_lock` already returns the comparable background `area_fraction`, excluding both frames’ masks. Set this check from `bg_result["area_fraction"] >= MIN_AREA`. The current check can pass when the comparable background area is below the required minimum.

- [keyframe_gate.py](D:/aai%20work/anime_studio_merge/director/keyframe_gate.py:224): `float(seconds)` crashes when the lock has `seconds=None`; `feasible_motion` explicitly accepts `None`, so that accepted input reaches the crash. Record `seconds` without an unconditional float conversion, or reject invalid lock seconds before this point and write a failing gate record.

VERDICT: FIX-FIRST.