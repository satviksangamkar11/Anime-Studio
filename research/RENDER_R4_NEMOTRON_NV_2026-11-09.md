# RENDER R4 Nemotron Super (NVIDIA), 3 slices

## slice A_runner
1. HIGH, `started()`/`run_cli()` (`usage`, `new`, `ls`, `download`, `exec list`), most `colab` calls lack `timeout`; a hung CLI blocks the 180 s proof and the whole batch indefinitely, wasting units and hanging. Add a 30 s timeout to every `run_cli` call.
2. HIGH, `fetch_ready()`, each `ls` line is used verbatim as a remote filename; if `colab ls` prefixes size/metadata the download path is wrong and finished clips are never fetched early, risking clip loss. Parse only the last whitespace token of each line.
3. HIGH, `run_cli(["exec", "-s", name], stdin=t0.LIST_CODE)`, no timeout; it can hang after `run.py` exits, blocking final fetch/stop and leaving the session running. Add `timeout` and fail/kill on hang.
4. MEDIUM, `fetch()`, skips `.mp4` when a local file >50 KB exists; a corrupt or stale clip is not re-downloaded, giving wrong video. Always re-download or verify hash.
5. MEDIUM, `finally`, when `keep=True` the local `proc` is not killed, leaving orphaned `colab exec` processes (B4). Kill `proc` unconditionally in `finally`.
6. LOW, `run_cli(["stop", ...], check=False)` in `finally` has no timeout and can hang at exit. Add `timeout`.

## slice B_vm_script
1. HIGH, run_limited/sh, shell=True timeout kills only the shell, not the wgp.py process group; a hung render keeps GPU burning past 7200 s. Fix: start_new_session=True and os.killpg on TimeoutExpired.
2. HIGH, finish/results, files reflects only the last attempt; a valid mp4 from an earlier attempt or non-zero exit with mp4 is marked failed and fetch_ready skips it, losing the clip. Fix: rescan od for mp4 after the loop and mark ok if any exists.
3. MEDIUM, ckpts symlink, a broken /content/Wan2GP/ckpts symlink from a prior run makes os.symlink raise FileExistsError and crash setup. Fix: remove existing APP/ckpts entry before symlinking.
4. MEDIUM, git clone, re-running into an existing /content/Wan2GP fails setup with no cleanup. Fix: rm -rf {APP} before clone.
5. MEDIUM, results, any .mp4 passes without integrity check; zero-byte/corrupt clip is marked ok, giving wrong video. Fix: ffprobe duration > 0 before marking ok.
6. LOW, nvidia-smi Popen, handle discarded; background logger lingers across re-runs. Fix: keep Popen handle and terminate at exit.
7. LOW, input write, nested blob keys lack parent dirs and crash write_bytes. Fix: mkdir parents for each input path.
8. LOW, timeline.txt, append mode lets fetch_ready read stale entries from prior runs. Fix: open timeline.txt with "w".

## slice C_builder
1. HIGH, `jpg_embedder`, keyframe JPEG bytes are computed into a local dict but may never be written into `run.py` or upload blobs, so the VM can reference missing inputs and all shots fail after GPU start. Fix: emit `b64decode(...)` literals from the embedder (or confirm `run_kaggle.build` embeds via the monkeypatched `png_b64`) before `split_blobs`.
2. HIGH, `split_blobs`, `run.py` reads `/content/_blobK.txt` but the batch ships no executor for `upload_NN.py`; a missed upload wastes a paid G4 session. Fix: prepend upload steps to `run.py` or fail fast if any blob is absent.
3. MEDIUM, `harden`, `run_limited` waits 7200 s per command; a hung shot burns ~2 h of units and may orphan processes that keep the session alive. Fix: cap at ~1800 s and kill the process group on `TimeoutExpired`.
4. MEDIUM, `harden`, only the first `subprocess.run` is patched; extra shell calls in a changed runner run unhardened. Fix: replace all occurrences or assert exactly one match.
5. MEDIUM, `legacy_rows`, `\r\n` blank lines survive the `\n`-only collapse and can trigger Wan2GP's two-request refusal (rc=1). Fix: normalize `\r\n` → `\n` before the regex.
6. MEDIUM, `split_blobs`, stale `/content/_blobK.txt` from a prior batch on the same VM can be reused, silently yielding wrong keyframes/video. Fix: delete `/content/_blob*.txt` at the top of `run.py`.
7. LOW, `jpeg_b64`, `Image.LANCZOS` raises on Pillow ≥10. Fix: use `Image.Resampling.LANCZOS` with fallback.
8. MEDIUM, `main`, positional `None, None, False` to `run_kaggle.build` can silently misconfigure route/profile if the API changed. Fix: use keyword arguments.
