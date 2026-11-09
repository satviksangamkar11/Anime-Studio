# RENDER R4 (supervl) 11-09 01:26

Reasoning: The runner fixes the start proof, per-shot fetching, and session stop on most paths, but `run_cli` still issues every `colab` command with no timeout, so a hung CLI call can block the runner and leave a billable session running. GPU identity is requested but never verified, so a non-G4 VM can be billed. `fetch` is not per-file resilient: one failed download aborts the rest and stops the session, stranding clips. Setup (`git clone`/`pip install`) has no retry. Per-shot `run_limited` allows 7200 s, letting one hung shot consume the batch cap. HF 429 sleeps stack across 10 shots. The prompt duplicates its final sentence and mixes pronouns; settings double T0’s frame count (243 vs 124) with an untested alignment template.

B1-B10 fix sufficiency: B1 Sufficient. B2 Sufficient. B3 Sufficient. B4 Not sufficient (external Colab termination is not detected or recovered). B5 Sufficient. B6 Not sufficient (G4 is only requested, never verified; owner’s T4 remains unmanaged). B7 Sufficient. B8 Not a render defect (review tooling only). B9 Partially sufficient (caught manually, no automated gate). B10 Sufficient.

T0 check: settings match T0 except `video_length` 243 vs 124; prompt uses unproven H3 V4 FL2VA alignment text instead of T0 alignment text; JPEG keyframes are low risk; no HF token means 429 retry only.

FINAL:
1. HIGH — director/run_colab_batch.py:196-206 — `run_cli` calls `subprocess.run` with no timeout, so `colab new/stop/download/ls` can hang indefinitely and leave a billable session running — add a default timeout (e.g. 300 s) and raise `RunError` on `TimeoutExpired`.
2. HIGH — director/run_colab_batch.py:258-259 — `colab new --gpu G4` is never verified, so the VM may be a T4/L4 and waste units or fail the render — after `new`, query GPU identity (nvidia-smi or gpu.csv) and stop unless it is G4.
3. MEDIUM — director/run_colab_batch.py:240-241 — `fetch_ready` matches `.mp4` with `endswith` on raw `ls` output; if `colab ls -s` prefixes file sizes, finished clips are missed and stranded on the VM — parse the filename token robustly (e.g. regex `\S+\.mp4`).
4. MEDIUM — director/run_colab_batch.py:215-223 — `fetch` aborts on the first failed download and the session is stopped, abandoning not-yet-fetched clips — wrap each file download in try/continue and stop only after best-effort transfer of all listed files.
5. MEDIUM — run.py:481-483 — `git clone` and `pip install` have no retry, so a transient network error fails setup and wastes the session — retry setup 2-3 times via `run_limited` before `SETUP FAILED`.
6. MEDIUM — run.py:509 — a shot is marked `failed` when the last attempt returns rc!=0 even if an earlier attempt left a valid mp4, discarding a good clip — mark `ok` if any attempt produced an mp4.
7. MEDIUM — run.py:504-508 — HF 429 retries sleep up to 180 s per attempt; across 10 shots this can consume the 3 h wall cap and unit budget — cap total 429 wait time or fail fast after two attempts.
8. MEDIUM — run.py:473 — `run_limited` defaults to 7200 s per shot, so one hung generation can consume the entire batch cap — lower the per-shot limit to about 1800 s.
9. MEDIUM — SHOT-001 prompt line 544 — the prompt duplicates its final sentence and mixes "his"/"Her" pronouns, which can confuse the model and produce wrong video — deduplicate the sentence and align pronouns.
10. MEDIUM — settings SHOT-005 line 532 — `video_length` is 243 vs T0's 124; untested long clips may OOM or exceed the 45-60 min estimate — reduce to 124 or provision extra units/time.
11. MEDIUM — SHOT-001 prompt line 543 — uses H3 V4 FL2VA alignment text instead of the proven T0 alignment text; the untested template may produce wrong video — validate against T0 structure or revert to T0 alignment wording.
12. MEDIUM — director/build_h3_batch.py:129-131 — blank-line hardening is a post-hoc regex with no automated gate, so heredoc newline slips (B9) can still reach run.py — add an `ast.parse` pre-flight gate in the builder.
13. LOW — run.py:480 — the `nvidia-smi` background monitor is never terminated and runs for the whole session — stop it in `finish()` or on exit.
14. LOW — director/run_colab_batch.py:220 — `fetch` skips re-download of any existing mp4 >50 KB, so a partial or corrupt clip is kept as-is — re-download or verify size against the VM.
15. LOW — run.py:491 — if `/content/_blob0.txt` is missing or truncated, `run.py` crashes with an uncaught exception — treat a missing/short blob as a fatal setup error with a clear message.
