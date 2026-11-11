`director/run_colab_batch.py`: `while waited <= proof_seconds:` allows one extra `sleep(poll)` after the 180-second proof deadline. With the default 15-second poll, the runner can wait until 195 seconds before stopping the session. Stop at the deadline by changing it to `while waited < proof_seconds:` and avoid sleeping past the remaining time.

VERDICT: FIX-FIRST.