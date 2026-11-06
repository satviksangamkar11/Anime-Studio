

# BATCH u1_server (supervl) 11-07 03:05

Brief reasoning: I audited server.py and pipeline.py against the contract addendum (spend OFF by default + typed confirm, story+pack scoped approvals with 409, Gate A blocked by validator errors, Gate D needs Step 9 pass + per-language checks, no Colab/ElevenLabs/model calls from tests/defaults, path sandbox, redaction, Host/Origin + X-UI CSRF guards). Command construction uses a whitelist with validated argv and no shell, so I found no path traversal or command injection. The real defects are a spend-accounting bug, local-path leakage, missing redaction on /api/pack, a story/pack scope mismatch on /api/author/status, and a spend-job stop/verify gap.

medium, server.py:1241-1249
Why: `record_spend(...)` charges the Colab ledger (line 1241-1242) and `rec["used"] = True` (line 1248) both run before `_start()` (line 1249). If `subprocess.Popen` raises (e.g. `cfg.python` is a missing binary), `/api/run` returns 500 but the ledger is already charged and the preview token is consumed for a job that never started.
Click path: Start with `--allow-spend --root-override python=<nonexistent>`; preview a `colab_run`, type the exact confirm text, POST `/api/run` -> 500, yet `ui/runs/colab_spend.jsonl` gains a row and the token is marked used.
Fix: Move `record_spend` and `rec["used"] = True` to after `_start()` returns successfully (same lock).

low, server.py:840 (also 851, 853)
Why: `/api/images` returns `candidates[].path` (and `finals[].path`, `keyframes[].path`) as absolute local paths via `str(p)`, leaking the local directory layout and username.
Click path: `GET /api/images?adhyay=1&story=kaliya_mardan` -> `candidates[].path` = `D:\aai work\flow_outputs\anime_kaliya\adhyay_01\shots\KM_01__candA.png`.
Fix: Return flow-relative paths (like `jobs[].file` at line 824-827) or drop the absolute `path`.

low, server.py:723 (also 735)
Why: `/api/pack` returns raw `gate1` text sliced from PACK.md and unredacted shot fields (`purpose`); `read_pack` output is not passed through `redact`/`redact_obj` like other endpoints, so secrets in story text can leak through the API.
Click path: `GET /api/pack?pack=stories/kaliya_mardan/pack_dots_full_v22&check=1` -> `gate1` echoes any secret string present in PACK.md before "## Gate 2".
Fix: Wrap the `read_pack` return value in `redact_obj(...)` (or redact `gate1` and free-text fields).

low, server.py:1695-1696 (and 1438-1440, 1757-1758)
Why: `GET /api/author/status` reads only `pack` from the query and ignores `story` (contract addendum §23 requires `?story=&pack=`); `POST /api/author/preview` delegates to the same `author_status`, so a mismatched `story` is silently accepted instead of a 409 scope mismatch.
Click path: `GET /api/author/status?story=other_story&pack=stories/kaliya_mardan/pack_dots_full_v22` returns the kaliya pack author status despite `story=other_story`.
Fix: Require `story` and return 409 when it doesn't match the pack's slug.

low, server.py:1284-1288
Why: `job_stop` computes `live` inside the lock, then calls `_verify_stop` only when `not live`. For a spend job that was live and just got killed, `not live` is False, so `_verify_stop` is skipped and `verified` stays not-True; `_active` then blocks all future spend until the owner calls `job_stop` a second time.
Click path: Stop a live `colab_run` via `POST /api/jobs/<id>/stop`; subsequent spend previews return 409 "another job is running" although the job is stopped, until a second stop call.
Fix: Call `_verify_stop` for spend jobs after a stop whenever `verified is not True`, regardless of `live`.

FINAL:
1. medium server.py:1241-1249 — ledger charged and token consumed before `_start`; a failed `Popen` (500) still bills the owner. Fix: charge/mark-used only after `_start` succeeds.
2. low server.py:840/851/853 — `/api/images` leaks absolute local paths (username/layout). Fix: flow-relative paths.
3. low server.py:723 — `/api/pack` returns unredacted `gate1`/shot text. Fix: `redact_obj` the pack response.
4. low server.py:1695-1696 — `/api/author/status` ignores `story`, violating the scoped contract. Fix: require matching `story` (409).
5. low server.py:1284-1288 — stopping a live spend job skips `_verify_stop`, blocking future spend until a second stop. Fix: verify on every spend-job stop.


# BATCH u2_pipeline_js (supervl) 11-07 03:13

Brief reasoning: I audited pipeline.js against the addendum (routes, field names, gates, spend defaults, voice/BGM/author behavior) and the defect classes in scope. All untrusted text is written via `textContent`/`createTextNode` (no `innerHTML`), the fetch is same-origin with no cookies and a custom `X-UI` header (preflight-protected, no cross‑origin CSRF vector), and I saw no secrets echoed in output — so no XSS/CSRF/secrets findings. Real defects found: a validator method mismatch that can block Gate A, an unvalidated pack name enabling path traversal, overlapping polls with no in‑flight guard (stale state can clobber a just‑approved gate), a fetch with no timeout that can leave `busy=true` forever (unexitable UI), an `/api/images` query that likely diverges from the contract, a slug‑built `/api/file` path that can traverse, and a link confirm that wrongly promises "no model call" when Whisper may run.

Findings:

- high, pipeline.js:313 — `loadDetail` fetches `GET /api/pack/validate?pack=...`, but the contract/Run‑validator button (line 1101) uses `POST /api/pack/validate {pack}`. If the server only accepts POST, the GET errors, `State.validatorError` is set, `validatorBlocks()` stays true, and Gate A cannot be approved on first load. Concrete path: open a story/pack; the validator panel shows an error/not‑available and Gate A Approve stays disabled until the user manually clicks "Run validator". Fix: change line 313 to `post('/api/pack/validate', { pack: pp })`. unverified (server method).

- high, pipeline.js:972–1000 — The Analysis pack name (`analysis-pack`) is never validated against `SLUG_PAT`; typing `../../tmp/evil` and running analysis sends it to `/api/pipeline/project` and `/api/preview write_pack`, which join it via `packPath` → `stories/<slug>/../../tmp/evil`, a path traversal out of the project. Concrete path: Analysis card → Pack name = `../../tmp/evil` → Run story analysis. Fix: validate `pack` with `/^[a-z0-9_]{1,40}$/` before posting and error otherwise.

- medium, pipeline.js:1951–1963 — `tick()` launches overlapping polls (`loadStatus`, `loadSummary`, `loadRegistry`, `loadPipeline`+`loadDetail`) every 5 s with no in‑flight guard; slow responses can arrive out of order and overwrite fresher state. Concrete path: approve Gate A while a poll started earlier is still in flight; the older `loadDetail` resolves last and restores the previous failing validator, re‑blocking/flickering Gate A. Fix: serialize polls with an in‑flight flag so a new tick does not start until the previous one completes.

- medium, pipeline.js:175–199 — `api()` uses `fetch` with no timeout/abort; a hanging state‑changing POST never settles, so `State.busy` stays `true` (the `finally` never runs) and every action button remains disabled — a state that cannot be exited without reloading. Concrete path: click "Run story analysis" then hang/disconnect the server; all buttons stay disabled indefinitely. Fix: add an `AbortController`/timeout to `api()` and reset `State.busy` on timeout.

- medium, pipeline.js:1140 — "Make Flow agent packet" calls `GET /api/images?story=&pack=`, but contract deviation 66 specifies `GET /api/images?adhyay=&story=` (default kaliya_mardan); for other stories the `pack` query may be ignored and no jobs are found. Concrete path: open a non‑kaliya story/pack, build image jobs, then click "Make Flow agent packet" → "Image jobs are not built yet" even after building. Fix: call `GET /api/images?adhyay=BUILD_ADHYAY&story=<slug>` per the contract. unverified.

- low, pipeline.js:1941 — `registryDetail` builds `/api/file?path=stories/<slug>/RUN_REPORT.md`; `encodeURIComponent` does not encode `/` and the slug comes from the server registry, so a slug containing `..` traverses via `/api/file`. Concrete path: registry story slug `../secret` → click "Open RUN_REPORT.md as text" → requests `stories/../secret/RUN_REPORT.md`. Fix: reject slugs containing `..` or `/` (or validate with `SLUG_PAT`) before building the path. unverified.

- low, pipeline.js:928 — `runLink` confirm says "This makes no model call and costs nothing," but `yt_transcript` may run Whisper (a model) when captions are absent (ASR auto/force). Concrete path: paste a captionless YouTube link, ASR = Auto, click "Get transcript from link" → the confirm wrongly promises no model call. Fix: reword the confirm to note Whisper may be used. unverified.

FINAL:
1. high, pipeline.js:972–1000 — unvalidated pack name enables path traversal out of `stories/` via `packPath`; validate with `SLUG_PAT` before posting.
2. high, pipeline.js:313 — `GET /api/pack/validate?pack=` mismatches the POST contract and can block Gate A approval on first load; use `POST /api/pack/validate {pack}`.
3. medium, pipeline.js:175–199 — fetch has no timeout, so a hanging request leaves `busy=true` and disables all buttons permanently; add timeout/abort and reset `busy`.
4. medium, pipeline.js:1951–1963 — overlapping polls let stale responses overwrite newer state (e.g., re‑block Gate A after approval); serialize the poll loop.
5. medium, pipeline.js:1140 — `GET /api/images?story=&pack=` likely diverges from the contract `?adhyay=&story=`, breaking the packet flow for non‑kaliya stories; align the query per the contract.
