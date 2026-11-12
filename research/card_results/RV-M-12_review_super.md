Defect:

- File: `director/test_timeline_lock_m12.py`
- Faulty lines:
```python
@pytest.mark.xfail(
    strict=True, raises=ValueError,
    reason="H3 rules (MO-03 impact span, CN-05 tail) reject a 60-frame DYNAMIC cut from 107; needs an h3 owner decision",
)
def test_trimmed_short_shot():
```
- Why: Card M-12 requires `edit_frames` down to 60 frames to be accepted with trim records. This test asserts the opposite: it expects `plan_pixels(["a","b"], [60,120])` to raise `ValueError`. With `strict=True`, once the code accepts the short edit the test fails as an unexpected pass; as written it validates rejection, contradicting the card. It does not cover `test_trimmed_short_shot` as a passing test.
- Fix: Delete the `@pytest.mark.xfail(...)` decorator (all three lines) so `test_trimmed_short_shot` runs as a normal test asserting success.

VERDICT: FIX-FIRST