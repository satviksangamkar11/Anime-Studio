# W2-D (G8, G9, G10)
- G8: run_colab_batch --go refuses without --qa-plan; --no-qa recorded as qa_skipped in history (doc + render records). Existing --go tests got --no-qa.
- G9: clip_qa.identity_check (first/mid/last kept frame, fail only on last "no", code IDENTITY, owner-acceptable); qa_plan stub_identity_ask (histogram corr, deterministic), nvidia_identity_ask, pick_identity_ask, add_identity, --identity; post_fetch_qa passes master for S when plan entry has "identity".
- G10: features.sim_prev; S route scene_cut on neighbour SSIM; SE unchanged.
- Tests: director/test_clip_qa_g9_g10.py, appended to test_run_colab_batch_w11.py. 150 pass in touched files.
