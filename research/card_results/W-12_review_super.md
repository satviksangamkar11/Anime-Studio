Defect 1 — Card requirement not met: `director/editorial_by_lang.py` is not deleted.
- Faulty line: the entire module `director/editorial_by_lang.py` is still present (source provided in full).
- Why: Card Files: `director/editorial_by_lang.py DELETE` (with `git rm`). Acceptance: `Select-String ... -Pattern 'editorial_by_lang|apply_rows|apply_shots|MAX_SPEEDUP'` finds nothing; this file alone matches `editorial_by_lang`.
- Fix: `git rm director/editorial_by_lang.py director/test_editorial_by_lang.py` and remove both files.

Defect 2 — Acceptance gate fails: `director/editorial_legacy.py` still defines banned identifiers.
- Faulty lines in `director/editorial_legacy.py`: `MAX_SPEEDUP = 1.03`, `def apply_rows(rows, ext, fps=24):`, `def apply_shots(h3_shots, ext):`.
- Why: Acceptance pattern `apply_rows|apply_shots|MAX_SPEEDUP` must find nothing in `director\*.py`; these names are defined there, so the gate cannot pass.
- Fix: Delete `director/editorial_legacy.py` (the retired editorial path has no remaining consumers).

Defect 3 — `test_needed_sec_at_a_speed_up_is_shorter` does not cover the case the card names.
- Faulty lines in `director/test_build_vo_tracks.py`:
  ```python
  def test_needed_sec_at_a_speed_up_is_shorter():
      lines = [{"id": "a", "start": 0.5, "natural": 3.0}]
      assert abs(b.needed_sec(lines, 1.0) - (3.5 + b.TAIL)) < 1e-6
      assert abs(b.needed_sec(lines, 1.5) - (2.5 + b.TAIL)) < 1e-6
  ```
- Why: Card: "lines (start 0, natural 3.5) at tempo 1.0 give 3.5 + TAIL = **3.6**; at 1.5 give 2.5 + TAIL." The test uses start 0.5, natural 3.0, so it does not cover the specified input. (With start 0, natural 3.5 at tempo 1.5 the correct value is 3.5/1.5 + TAIL ≈ 2.433 s, not 2.5 + TAIL, so the card's stated 1.5 expectation is inconsistent with its stated inputs; the test must be aligned to one consistent specification.)
- Fix: Replace with the card's specified inputs and matching assertions:
  ```python
  def test_needed_sec_at_a_speed_up_is_shorter():
      lines = [{"id": "a", "start": 0, "natural": 3.5}]
      assert abs(b.needed_sec(lines, 1.0) - (3.5 + b.TAIL)) < 1e-6
      assert abs(b.needed_sec(lines, 1.5) - (3.5 / 1.5 + b.TAIL)) < 1e-6
  ```
  If the owner intended 2.5 + TAIL at 1.5, the inputs must be start 0.5, natural 3.0 (as currently coded) and the card text corrected.

VERDICT: FIX-FIRST