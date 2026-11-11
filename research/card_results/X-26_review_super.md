Defect 1 — `stamps_left` is not recorded when a method finishes but leaves stamps.

Faulty lines:
```python
    method, cand, stamps_left, errors = None, None, None, []
    for name, fn in steps:
        try:
            out = fn(rgb)
        except Exception as exc:                          # a failing method is a failed check, not a crash
            errors.append(f"{name}: {exc}")
            continue
        left = sparkle_left(out)
        if left == 0:
            method, cand, stamps_left = name, out, 0
            break
        errors.append(f"{name}: stamps left {left}")
```
Why it is wrong: `stamps_left` stays `None` whenever a method runs but `left != 0` (including the too-small case where `left is None`). The record then reports `stamps_left: null` instead of the measured count, violating the card’s “measured check” requirement and giving wrong data in `watermark_log.jsonl`.

Fix:
```python
        left = sparkle_left(out)
        if left == 0:
            method, cand, stamps_left = name, out, 0
            break
        stamps_left = left
        errors.append(f"{name}: stamps left {left}")
```

VERDICT: FIX-FIRST