- The card requires `director/test_build_vo_tracks.py`, but the supplied tests are in `director/test_build_vo_tracks_w04b.py`. The card’s acceptance command therefore won’t run these tests. Move or rename the file to `director/test_build_vo_tracks.py`.

- The card lists tests named `test_exact_boundary`, `test_stale_lock_exit_2`, `test_lock_wins_over_editorial_file`, and `test_tempo_limit_is_one`; the supplied tests use different names. Rename them to the listed names so the card’s test coverage is directly verifiable.

VERDICT: FIX-FIRST