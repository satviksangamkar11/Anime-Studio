`director/test_build_vo_tracks.py` does not test the case specified by the card:

> `lines = [{"id": "a", "start": 0.5, "natural": 3.0}]`

The card requires start `0` and natural length `3.5`, with results `3.6` and `2.6`. Change the test input to `{"id": "a", "start": 0, "natural": 3.5}` and assert `3.6` at tempo `1.0` and `2.6` at tempo `1.5`.

`director/editorial_by_lang.py` remains, despite the card requiring its deletion with `git rm`. It still re-exports the legacy path:

> `from editorial_legacy import (FILE, MAX_SPEEDUP, TAIL, apply_rows, apply_shots, load, main, needed_sec,`

Delete `director/editorial_by_lang.py` and `director/test_editorial_by_lang.py` as required. The acceptance search also cannot pass while `director/editorial_legacy.py` remains: it contains `MAX_SPEEDUP`, `apply_rows`, and `apply_shots`. Remove that legacy implementation and its tests as part of retiring the path.

VERDICT: FIX-FIRST