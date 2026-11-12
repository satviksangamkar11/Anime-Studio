- **QA wiring is incomplete.** The new helper is defined, but nothing in `run_colab_batch.py` calls it. The live post-fetch path still calls `post_fetch_qa.run_from_files(a.qa_plan, a.results, a.routes, a.pack, [s["id"] for s in shots])`, so this change never passes the route or saved chain PNG to `qa_shot`. Wire `qa_inputs` into the actual QA caller and pass its `route` and `chain_prev` arguments through to `qa_shot`.

- **The S-route test does not check that the end frame is skipped.** `test_qa_route_maps_start_only_to_S_and_skips_the_end_frame` only asserts that `qa_inputs` returns `"S"`; it never runs `qa_shot` or checks its end-frame behavior. Extend the test to call the QA path with an S-route clip and assert the end-frame check is skipped.

- **The chain test does not check that the clip is checked against the saved PNG.** `test_chained_clip_gets_the_saved_previous_png` only checks that the helper returns a path. It does not verify that `qa_shot` receives or uses that path. Extend it to exercise the QA caller and assert the saved PNG is passed as `chain_prev`.

VERDICT: FIX-FIRST