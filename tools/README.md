# tools/

## secret_scan.py: pre-push guard for the public repo

Blocks a push when the files it would send contain a key-shaped string, a `secrets/` path, a `stories/` path (except the tracked
files of `stories/kaliya_mardan/`), a `SOURCE.md` transcript, a `flow_outputs/` path, a media or image file type
(.mp4 .mov .wav .mp3 .safetensors .gguf .pt .ckpt .zip .png .jpg .jpeg .webp .vtt), or a file over 1 MB.
Findings print as `file:line RULE` only. The secret text is never printed.

```
C:/Python314/python.exe tools/secret_scan.py --remote origin      # exit 0 clean, 1 findings, 2 git error
C:/Python314/python.exe tools/secret_scan.py --no-worktree        # only the commits to push
```

- Scanned set: commits in `origin/main..HEAD` (every file of HEAD when that remote branch does not exist), plus the working-tree
  list (modified, staged and untracked files that git does not ignore). Untracked files count, so a `git add -A` cannot slip one in.
- Allowlist: `tools/secret_scan_allowlist.txt`, lines `path | rule | literal`. Fake test fixtures only. A real-looking key never belongs there.
- Rules: see `RULES` in `secret_scan.py` (nvapi-, sk-or-v1-, sk-, hf_, AIza, gsk_, GitHub, Slack, private key blocks, Bearer tokens,
  and a long mixed letter-digit token after key/token/secret/password).

### Install the hook (the owner runs this once; the hook never changes git config)

```
git config core.hooksPath .githooks
git update-index --chmod=+x .githooks/pre-push      # once, then commit the mode
```

`.githooks/pre-push` runs the scan with `$ANIME_PY` (default `C:/Python314/python.exe`, else `python`) and blocks the push on any
non-zero exit. Test it without pushing: `sh .githooks/pre-push origin`.

## Tests

```
C:/Python314/python.exe -m pytest -q -p no:cacheprovider tools
C:/Python314/python.exe -m pytest -q -p no:cacheprovider director/test_retry_policy.py director/test_ops_checks.py
```

All offline. The scanner tests build their fake keys at run time so no key-shaped literal sits in the source.

## director/retry_policy.py: one policy for free model calls

- `classify_exception(exc)` / `classify_http(status, body)`: rate_limited (429), server (5xx), timeout, network, pending_budget
  (body says PENDING_BUDGET), fatal (everything else).
- `answer_kind(text, finish_reason)`: empty or empty_cut_off (finish_reason `length`) for a blank answer.
- `call_with_retry(fn, model=, policy=, breaker=, sleep=, clock=, rng=, check=)`: in-place retries for rate_limited, server,
  timeout, network (exponential backoff 15 s doubling, equal jitter, cap 180 s, 5 calls, 600 s total wait; a Retry-After
  attribute on the exception is honoured). pending_budget, empty and empty_cut_off, and fatal, give up at once.
- `CircuitBreaker`: opens after 3 failures in a row, lets one trial through after 300 s (half-open).
- `call_chain(FREE_CHAIN, make_call, catalog=...)`: super-vl -> ultra -> dots. Every model must be in the catalog with all
  prices 0, else `PaidModelRefused` before any call. `ChainExhausted` when all fail.

Integration points (NOT wired yet; for the integrating step, do not edit the owned files from here):
1. `director/write_pack.py`: `call_openrouter` and `call_nvidia` (or the caller of `call_path`) wrap their request in
   `call_with_retry(..., check=lambda r: answer_kind(*r))`. `openrouter_is_free` can become `is_free_model(model, catalog)`.
   A `ModelGaveUp` with kind `pending_budget` should move to the next writer route, not retry in place.
2. `flow/scripts/dots_review.py`: its own loop (5 tries, 30 s x attempt) can become `call_with_retry` with
   `Policy(max_attempts=5, base_delay=30, max_delay=180)`.
3. `ui/server.py`: `_spend_gate` calls `ops_checks.check_spend(est)`; a Colab start calls `ops_checks.record_spend(...)`;
   `Api.pipeline`/`/api/pipeline` adds `"code_fingerprint": ops_checks.code_fingerprint()` so `ui_server_health` can confirm the
   running code. Without that field the health check reports `unverified`.

## director/ops_checks.py: checks before a render or a big download

```
C:/Python314/python.exe director/ops_checks.py --disk "D:/aai work/anime_studio"
C:/Python314/python.exe director/ops_checks.py --health http://127.0.0.1:8765
C:/Python314/python.exe director/ops_checks.py --spend
```

- `disk_free(path)`: blocks under 2 GB free, warns under 5 GB, and refuses the C: drive for big files.
- `ui_server_health(url)`: GET `/api/pipeline` and `/api/registry` (3 s timeout). `stale or unreachable` when a request fails or the
  fingerprints differ; `unverified` when the server reports no fingerprint; `ok` when they match.
- `record_spend(ledger, units=, session=, story=, reason=)`: one append per start, under a lock file (a lock older than 60 s is removed).
  Ledger: `ui/runs/colab_spend.jsonl` (git-ignored).
- `colab_spend_total(ledger)`: total, today and this week (ISO week).
- `check_spend(units)`: refuses above 15 units per run; day and week caps are checked once set.
- `check_before_render(render_dir, estimate_units=, session=)`: disk + spend + the `colab stop` reminder, in one dict.
  Call it before any Colab start or big download.

Open owner decision: `DAY_CAP_UNITS` and `WEEK_CAP_UNITS` in `director/ops_checks.py` are `None` (totals reported, not capped).

## Known gap in .gitignore (reported by the scan, not changed here)

`.gitignore` has `stories/*` then `!stories/kaliya_mardan`, so new files in that folder (RUNS.jsonl, RUN_REPORT.md, story.json) are
not ignored and would be flagged as `P-STORIES` until they are ignored or removed from the commit.
