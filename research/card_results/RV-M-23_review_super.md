Defect 1 — SHAPE-06 payoff duration is not scoped to the final segment.

Faulty line:
```python
        payoff = sum(d for d, b in zip(durs, beats) if b == "payoff")
        if payoff < PAYOFF_MIN or beats[-1] != "payoff":
            add("SHAPE-06", "payoff must cover the last 5 s (payoff shots %.1f s, last beat %s)"
                % (payoff, beats[-1]))
```
Why it is wrong: It sums every shot tagged `payoff` anywhere in the reel. An early payoff shot can inflate the total and mask a final payoff segment shorter than 5 s, while `beats[-1] != "payoff"` only checks the last label. The card requires the last >= 5 s to be payoff.
Exact fix:
```python
        payoff = 0.0
        for d, b in zip(reversed(durs), reversed(beats)):
            if b != "payoff":
                break
            payoff += d
        if payoff < PAYOFF_MIN or beats[-1] != "payoff":
            add("SHAPE-06", "payoff must cover the last 5 s (final payoff %.1f s, last beat %s)"
                % (payoff, beats[-1]))
```

Defect 2 — SHAPE-02 non-numeric `reel_target_s` is always a hard error, violating old-pack warnings-only.

Faulty line:
```python
    target = story.get("reel_target_s")
    if target is not None:
        if not _num(target):
            errors.append("SHAPE-02 reel_target_s must be a number of seconds")
        elif not TARGET_RANGE[0] <= target <= TARGET_RANGE[1]:
            warnings.append("SHAPE-02 reel_target_s %s is outside 25-75 s" % target)
```
Why it is wrong: It bypasses the `new` severity switch used by `add(...)`. An old pack (no premise, no arc_beat) with a non-numeric `reel_target_s` gets an error instead of a warning, so it does not "still load (warnings only)".
Exact fix:
```python
    target = story.get("reel_target_s")
    if target is not None:
        if not _num(target):
            add("SHAPE-02", "reel_target_s must be a number of seconds")
        elif not TARGET_RANGE[0] <= target <= TARGET_RANGE[1]:
            add("SHAPE-02", "reel_target_s %s is outside 25-75 s" % target)
```

VERDICT: FIX-FIRST