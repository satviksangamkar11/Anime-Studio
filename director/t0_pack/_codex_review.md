**The pipeline can still stop with an incomplete clip accepted as safely downloaded.** Read-only review; embedded blobs were skipped.

1. **HIGH — MP4 download races the writer.** `t0_pack/run_t0_parallel.py:38–47`: any visible MP4 over 100 KB is accepted; subsequent sweeps skip that shot permanently. A partial video or intermediate MP4 can therefore satisfy the final stop gate.  
   **Fix:** Publish a per-shot completion manifest after `wgp.py` exits successfully; download only its final files, verify hash and video decoding, then mark the shot complete.

2. **HIGH — No bounded recovery after execution ends.** `t0_pack/run_t0_parallel.py:69–82`: after the CLI exits, only one final sweep runs; missing clips leave the paid VM running indefinitely. Exceptions or Ctrl+C after allocation also bypass recovery. `--timeout 7200` is an **output inactivity timeout**, not a total runtime budget. [CLI source](https://raw.githubusercontent.com/googlecolab/google-colab-cli/main/src/colab_cli/commands/execution.py)  
   **Fix:** Add a wall-clock watchdog and bounded download retries, with durable backup and explicit recovery handling before teardown.

3. **HIGH — Failed stop still returns success.** `t0_pack/run_t0_parallel.py:83–86`: the stop return code is discarded, and session listing is merely printed; billing can continue despite exit code 0.  
   **Fix:** Check stop success, retry failures, and verify the named runtime is absent before returning 0.

4. **HIGH — Windows CLI launcher currently fails.** `t0_pack/run_t0_parallel.py:11`: invoking this exact launcher with `ls --help` returned `uv trampoline failed to canonicalize script path`. Google currently documents Linux/macOS support only. [Official README](https://github.com/googlecolab/google-colab-cli)  
   **Fix:** Run the orchestrator and CLI together under WSL/Linux, translating local paths, and validate the launcher before allocation.

5. **MED — Logs can disappear during successful teardown.** `t0_pack/run_t0_parallel.py:74–79`: every auxiliary download ignores failure; `setup.log` and copied settings are never fetched. All clips being “home” permits stopping even when diagnostic downloads failed.  
   **Fix:** Download and verify an explicit artifact manifest, including setup/render logs and settings, before stopping.

6. **MED — Retry/resume is broken and can overwrite evidence.** `run_kaggle.py:42` (`colab_batches/t0/run.py:15`): rerunning in the same VM fails because `Wan2GP` already exists. Meanwhile `t0_pack/run_t0_parallel.py:68` truncates the host log, destinations are reused, and `got` resets.  
   **Fix:** Make checkout idempotent, use run-specific output/log directories, and resume from verified completed artifacts.

7. **MED — Six separate model startups waste paid time.** `run_kaggle.py:63`: each shot launches a new Python process, repeating model loading; `--profile 5` also applies the conservative T4 configuration to the 96 GB G4.  
   **Fix:** Benchmark a suitable G4 profile on one shot and use Wan2GP’s supported batch mechanism to retain loaded models where possible.

8. **MED — Listing failures masquerade as empty directories.** `t0_pack/run_t0_parallel.py:19–21`: authentication/network/API failures become `[]`, hiding the actual problem while polling continues; subprocess calls have no host timeout.  
   **Fix:** Distinguish listing errors from empty results, surface stderr, and add bounded subprocess timeouts and retries.

9. **LOW — Success bookkeeping is too weak.** `run_kaggle.py:53–65`: `RESULT.json` appears only after the whole batch, and success requires merely an MP4 filename; stale or invalid files qualify.  
   **Fix:** Atomically checkpoint each shot’s result with validated final filenames, sizes and hashes.

10. **LOW — Official Pika validator omits two invariants.** `h3_director.py:284–287`: `check_combo()` checks steps/shift/phases but accepts changed CFG or LoRA strength. Current `settings_for()` supplies the correct values.  
    **Fix:** Validate `guidance_scale == 1` and `loras_multipliers == "1.0"` for `pika6` too.

The six decoded settings match the requested route combinations: Singularity Ref2VA with the matching 4/8-step Turbo LoRA, Euler, CFG 1, strength 1 and shift 12; official FL2VA with its own six-step adapter and `pika_renoise`. The Turbo choices agree with the [publisher’s instructions](https://huggingface.co/Pika-Labs/Pika-H3-Flex-Turbo-LoRA). `/content` paths, Windows subprocess argument lists, safe image paths, and directory suffix parsing look sound; Google’s [`ls` implementation](https://raw.githubusercontent.com/googlecolab/google-colab-cli/main/src/colab_cli/commands/files.py) does emit trailing `/`.

No files changed or paid sessions started. Exact pinned-commit Turbo loader/scheduler behavior and Blackwell dependency compatibility remain unverified; the pinned upstream source could not be retrieved.