- The required API is missing. The card says `build_cue_sheet(..., lock=None)`, but the function only accepts `timeline_lock` and has no `editorial` parameter. A caller using the specified `lock=` argument gets `TypeError`; the required `LOCK_AND_EDITORIAL` error cannot be returned. Add `lock` and `editorial` parameters, return `LOCK_AND_EDITORIAL` when both are supplied, and return `VO_REPORTS_REQUIRED` when `lock` is supplied and `vo_reports is None`.

- `apply_lock` does not accept `fps`, despite the card requiring `apply_lock(shots, lock, fps)`. It instead reads `lock.get("fps", 24)`, so the supplied `fps` used by `build_cue_sheet` can differ from the lock’s FPS. Add an `fps` argument and use it to calculate `editorial_duration_sec`.

- The required `--editorial` compatibility option is absent. `main` also never prints `"deprecated: use --lock"`. Add the option and emit that message when it is used.

- The card requires lazy loading of `timeline_lock_io` through the specified `director` path, but the module is imported eagerly at line 29. This can fail at module import time when that path is unavailable, before the CLI can report a missing or stale lock. Move the import into the `--lock` path in `main` and use the specified path insertion.

- The listed tests are in `test_cue_sheet_w05b.py`, not the required `score/tests/test_cue_sheet.py`. Move or incorporate them into the named test file so the card’s acceptance command covers the tests.

VERDICT: FIX-FIRST