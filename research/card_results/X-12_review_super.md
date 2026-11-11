Defect:

- Faulty line: `TEST FILE director/test_lock_rows_x12.py:` (delivered test location). The card requires `director/test_timeline_lock_io.py` (append).
- Why it is wrong: The card explicitly lists `director/test_timeline_lock_io.py` as the test file to append to, and acceptance is `python -m pytest director/test_timeline_lock_io.py -q`. Delivering the tests under `test_lock_rows_x12.py` means that command does not execute them, so the card’s acceptance cannot pass as delivered.
- Exact fix: Move the three test functions into `director/test_timeline_lock_io.py` (append) or rename the delivered file to `director/test_timeline_lock_io.py` so the acceptance command discovers and runs them.

VERDICT: FIX-FIRST