Defect 1 — bad shot `seconds` passes silently and corrupts pacing math.

Faulty line:
```python
    return float(shot["seconds"])
```
in `_seconds` (`director/script_pacing.py`).

Why it is wrong: `_seconds` validates override values but blindly casts `shot["seconds"]`. `script_hook.validate_shots` only asserts the `"seconds"` key exists, so a negative, NaN, or infinite shot duration passes silently and corrupts `total`, the re-hook window, and payoff boundaries.

Exact fix: validate the shot's own seconds before returning:
```python
    value = shot["seconds"]
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("shot %s seconds must be a positive finite number" % (shot["id"],))
    if value <= 0 or value != value or value in (float("inf"), float("-inf")):
        raise ValueError("shot %s seconds must be a positive finite number" % (shot["id"],))
    return float(value)
```

Defect 2 — fixed 60–75 s length window remains when the story gives no target, violating “NO fixed recommended length”.

Faulty line:
```python
        return LENGTH_WINDOW_S, None
```
in `_length_window` (`director/script_pacing.py`).

Why it is wrong: The card requires the length window to come from `story.reel_target_s` with no fixed recommended length. Returning the hardcoded `(60.0, 75.0)` when no story target is supplied imposes a fixed default and emits length warnings for reels without a story, contradicting the card.

Exact fix: return no window when there is no target:
```python
        return (None, None), None
```
and in `inspect_pacing` guard the check so no warning is emitted without a target:
```python
    (len_lo, len_hi), target = _length_window(story)
    if target is not None and (total < len_lo or total > len_hi):
        warnings.append("length warning: reel is %.1f s, story target is %.1f s (+-10%%)" % (total, target))
```
Remove the now-unreachable `if target is None:` warning branch.

Defect 3 — `test_inspect_pacing_is_deterministic` cannot fail.

Faulty line:
```python
    assert script_pacing.inspect_pacing(good, "en") == script_pacing.inspect_pacing(good, "en")
```
in `test_inspect_pacing_is_deterministic` (`director/test_script_pacing.py`).

Why it is wrong: It calls the same function with identical arguments and compares the result to itself. It cannot fail and asserts nothing about pacing behavior.

Exact fix: replace with meaningful assertions, e.g.:
```python
    result = script_pacing.inspect_pacing(good, "en")
    assert result["pass"] is True
    assert result["problems"] == []
```

VERDICT: FIX-FIRST