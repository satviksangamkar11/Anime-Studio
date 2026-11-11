Defect 1: wrong test file path.
Card: `director/test_shot_router.py` (append; Haiku finds the existing file with Glob). Acceptance: `python -m pytest director/test_shot_router.py director/test_blocking.py -q`.
Provided: `TEST FILE director/test_shot_router_x04.py`.
Why it is wrong: a file named `test_shot_router_x04.py` is not collected by `pytest director/test_shot_router.py`, so the card's tests never run and acceptance cannot pass.
Exact fix: rename the file to `director/test_shot_router.py` (or append its contents to the existing `director/test_shot_router.py`).

Defect 2: `test_every_gpu_route_has_h3_mode` does not implement the card's known-set check.
Quote:
```python
    from h3.router import REF2VA  # the h3 name the sing8 compiler uses
```
```python
            assert res["h3_mode"] in ("FL2VA", REF2VA, "I2VA")
```
Why it is wrong: the card requires that for FL2VA/Ref2VA the name is in `compile_h3_sing8.py:147`'s known set. This test never reads `compile_h3_sing8.py:147`; it imports from `h3.router` and asserts against a hardcoded tuple, so it does not cover the requirement the card lists for that test name.
Exact fix: replace the `h3.router` import and the hardcoded tuple with an import of the known set exported at `compile_h3_sing8.py:147` and assert `res["h3_mode"] in <that known set>` for FL2VA/Ref2VA routes.

VERDICT: FIX-FIRST