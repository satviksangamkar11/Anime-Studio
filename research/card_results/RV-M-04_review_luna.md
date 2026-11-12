- [director/blocking.py:28](D:/aai%20work/anime_studio_merge/director/blocking.py:28) adds `"locked"` to the `camera.move` enum. The card’s enum permits `null` or the listed moves; `locked` is not one of them. Remove it from `_CAMERA_11_MOVES` so a 1.1 sheet with `"move": "locked"` fails BLK-S06.

- [director/blocking.py:184](D:/aai%20work/anime_studio_merge/director/blocking.py:184) checks that `cast[].expression` is a string, but BLK-S16 requires it to come from the bible list. Validate membership in that list and reject unknown strings; add a test showing an arbitrary string fails.

- [director/blocking_lint.py:137](D:/aai%20work/anime_studio_merge/director/blocking_lint.py:137) only checks L14 when `beats` is a list. A 1.1 sheet with no `beats` field—or a non-list value—passes L14. Require a list of 2–4 valid beats and emit L14 when it is missing or malformed. Add tests for both cases.

VERDICT: FIX-FIRST.