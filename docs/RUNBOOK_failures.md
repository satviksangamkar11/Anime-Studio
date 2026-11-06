# Runbook: failures and the push checklist

Paths are from the repo root `D:\aai work\anime_studio`. Never paste a key, a token or a story transcript into chat or a file.
Never use `--allow-paid`, `--via nvidia` for Ultra while it returns PENDING_BUDGET, or `colab --logtostderr`.

## 1. Free model: 429 or PENDING_BUDGET

Symptoms: the writer log shows `HTTP 429`, `rate_limited`, `PENDING_BUDGET`, or "every NVIDIA key failed".

What the code already does: `director/retry_policy.py` waits 15 s, 30 s, 60 s ... (cap 180 s, 5 calls, 600 s total) for
429 and 5xx. PENDING_BUDGET does not retry in place: the caller moves to the next route. After 3 failures in a row a model
is skipped for 5 minutes (circuit breaker).

What you do:
1. Wait 10 minutes. A 429 is a shared free-tier limit; it clears by itself.
2. Run the same writer command again with the SAME pack folder (no `PACK.md` yet, so it is not refused). The stages already
   saved as `stage_*_raw.json` are not sent again; the run continues from the first missing stage.
3. PENDING_BUDGET on the NVIDIA route: use the OpenRouter route instead: `--writer super-vl` (default) or `--writer ultra`
   (both OpenRouter `:free`). Do not use `--via nvidia` for Ultra while it answers PENDING_BUDGET.
4. If you switch writer in the middle of a folder, the stages saved by the first writer stay. For a clean pack, start a new
   pack folder named `pack_<writer>_<YYYYMMDD>_v<n>` and keep the old one.
5. Dots review (`flow/scripts/dots_review.py`): if it prints `INCOMPLETE` (no `FINAL:` section), run it again on fewer files.

## 2. Empty or cut-off writer stage

Symptoms: `the model call failed or was cut off (length)`, an empty answer, or a stage file `stage_<name>_validation.json`
(the checks failed after the one repair retry; the file lists the errors).

Cut-off or empty answer (reasoning used the whole token budget, `finish_reason=length`):
1. Look only at the `finish_reason` field of `stage_<name>_raw.json`. Do not open the text in chat.
2. Delete that one bad `stage_<name>_raw.json` (and `stage_<name>_validation.json` if present). Keep the other stage files.
3. Run the same writer command again on the same folder. It resumes at that stage.
4. Still cut off twice: switch writer (see 1.4) or ask for a second look before spending more calls.

Validation failure (the answer came back but the checks failed twice):
1. Read `stage_<name>_validation.json` (error codes and the place in the pack, not the story text).
2. Do not edit a saved raw answer by hand. Fix the cause in the prompt or the source, then delete that stage's raw and
   validation files and rerun.

## 3. Colab failure

Rules: the Colab CLI is `C:\Users\Satvik\.local\bin\colab.exe`. Every session that started must be stopped, whether the run
worked or not. Never `colab --logtostderr` (it breaks the CLI output).

1. Check the session list: `colab sessions`. Check the balance: `colab usage`.
2. If any session is listed that should be closed: `colab stop -s <session>`, then `colab sessions` again. Repeat until none.
3. The UI shows `STOP FAILED` or a spend warning: do step 2 by hand at once. Do not start another run before that.
4. Before any new Colab start: `C:/Python314/python.exe director/ops_checks.py --spend` (today and this week totals) and
   `check_before_render` (disk and the 15-unit cap). The UI refuses a start when the balance is under 1.5 x the estimate.
5. Batch missing `render_manifest.json`: rebuild the batch with `director/run_kaggle.py --target colab`; do not start it as is.
6. A run that crashed still counts its units. Enter the real units by hand from `director/` with Python:
   `import ops_checks; ops_checks.record_spend("ui/runs/colab_spend.jsonl", units=..., session=..., story=..., reason="crashed run, manual entry")`.

## 4. Stale UI server

Symptoms: `/api/registry` answers "unknown path", a new button or panel is missing, a gate shows the wrong state, or the
server was started before the last code change.

1. Check: `C:/Python314/python.exe director/ops_checks.py --health http://127.0.0.1:8765`.
   `stale or unreachable`: restart it. `unverified`: restart it after any code change (the server reports no fingerprint yet).
2. Restart: find the process on port 8765 (`netstat -ano | findstr :8765`), stop it (`taskkill /PID <pid> /F`), then start:
   `cd ui` and `C:/Python314/python.exe server.py --port 8765` (in the background). Spend stays OFF unless the owner gives
   `--allow-spend` in chat.
3. Reload the browser page. Check `/api/registry` again before any gate click.

## 5. Push checklist (the public repo)

Rule: the owner says "push" in chat before any push. Code and docs only.

1. `git status --short`: no images, clips, audio, transcripts, `stories/` files (except tracked `stories/kaliya_mardan/`),
   `secrets/`, `flow_outputs/`. Remove anything unwanted from the commit with `git rm --cached <file>`.
2. `git config core.hooksPath` shows `.githooks` (the owner sets it once, see `tools/README.md`).
3. `C:/Python314/python.exe tools/secret_scan.py --remote origin` exits 0. A finding prints `file:line RULE` only. Fix the file;
   never copy the matched text anywhere. A fake test fixture: add a `path | rule | literal` line to
   `tools/secret_scan_allowlist.txt` only after you confirm it is fake.
4. Run the four suites and check each last line is green: `h3`, `ui`, `flow/scripts`, `director` (commands in `HANDOFF_2026-11-07.md`
   section 8), plus `tools`.
5. Ask the owner for the push in chat. Then `git push origin main`. The pre-push hook runs the scan again.
6. Never use `--no-verify` or any flag that skips the hook. If the hook blocks, fix the finding (step 3).
