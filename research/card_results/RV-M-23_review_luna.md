- `director/story_shape.py`: `if any(b < a for a, b in zip(idx, idx[1:])):` checks only that beats never move backward. It accepts `hook → payoff` and `hook → setup → payoff`, so a new-format story can omit required arc stages while passing the arc lint. Require the ordered beat sequence to include `hook`, `setup`, `escalation`, and `payoff` in that order, and add a test showing a missing stage is rejected.

- `director/test_story_shape.py` has no test for `voice_rest` longer than 4 seconds. The card requires a test per rule, and the current under-2-second test does not exercise the upper bound. Add a case such as `[12.0, 16.1]` and assert `SHAPE-10`.

VERDICT: FIX-FIRST