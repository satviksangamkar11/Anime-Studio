

# BATCH r6_router (supervl) 11-07 12:59

Reasoning: I checked the two files against the owner spec and the round-2 fix list. The router’s `ref_inventory` and `ref2va_limit_problems` already normalize non-dict `fl2va_keyframes` to `{}`, but `route_shot` was not updated the same way. `video_shift_for` indexes the profile directly with no fallback. The remaining router logic matches the documented mode table and Ref2VA limits. In the test file I could not find any “assert True” / cannot-fail tests; the one suspicious RF-03 test depends on `lint_story`, which is not provided, so it is unverified.

- **high, router.py:33** — `route_shot` crashes on non-dict, truthy `fl2va_keyframes`. `k = shot.get("fl2va_keyframes") or {}` passes through non-empty strings, lists, or ints, and the next line `k.get(...)` raises `AttributeError`. `ref_inventory` and `ref2va_limit_problems` guard with `isinstance(k, dict)`; `route_shot` was missed. Failing input: `route_shot({"fl2va_keyframes": "x"})` or `route_shot({"fl2va_keyframes": [1]})`. Fix: `k = shot.get("fl2va_keyframes"); k = k if isinstance(k, dict) else {}`.

- **medium, router.py:73** — `video_shift_for` does `profile["model_sampling_av"]["video_shift"]` directly, raising `KeyError` on an un-linted or hand-edited profile instead of degrading safely. `lint_profile` reports PO-04, but nothing guards this call. Failing input: a profile missing `model_sampling_av.video_shift`. Fix: guard with nested `.get` / `or {}` or require `lint_profile` before compile.

- **unverified, test_router.py:83-87** — `test_ref2va_label_without-reference_is_RF03` asserts `RF-03` for a compiled-prompt picture-label swap (`<Picture 1>` → `<Picture 7>`), but `router.py` defines `RF-03` for non-list/non-dict reference values, not dangling picture labels. Without `lint_story` source I cannot confirm whether `lint_story` maps this to `RF-03`; the test may assert the wrong code or pass for the wrong reason. Fix: align the expected code with `lint_story`’s actual mapping or test `router.ref2va_limit_problems` directly for `RF-03`.

No other real defects found in these files.

FINAL:
1. high, router.py:33 — `route_shot` crashes on non-dict truthy `fl2va_keyframes`; use `isinstance(k, dict)` guard like the other router functions.
2. medium, router.py:73 — `video_shift_for` raises `KeyError` on missing profile shift keys; guard with `.get` / fallback.
3. unverified, test_router.py:83-87 — `test_ref2va_label_without-reference_is_RF03` may assert the wrong error code for a picture-label mismatch; confirm against `lint_story`.
