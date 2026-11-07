# Anime Studio control UI: PLAN (not built)

Date: 2026-11-06. Scope: this file only. Nothing else was edited. No network, browser, GPU or commit. The Granth folder was not opened.
Owner intent: give a story, see the story analysis, then images, bridge, video and export, all on one simple page with full control.

## 0. What the files say (checked 2026-11-06)
- `h3/` holds only `SPEC.md`. `schema_and_linter.py`, `compile_h3_sing8.py`, `assemble_reel.py`, `render_controller.py` and `post.py` do not exist. The video path that works today is `director/`: `h3_director.py` (settings), `run_kaggle.py --target colab` (batch folder), `t0_pack/run_t0_parallel.py` (Colab run, T0 only).
- The Flow job builder `build_jobs_v2.py` exists only in `granthstudio` (RUN_NOTES build command). The UI cannot call it without touching Granth (gap G1).
- Other Flow scripts exist in `anime_studio\flow\scripts\`: review_shot, neighbour_sheet, download_queue, file_flow_download, bridge_flow_to_h3, tidy_final, progress_log, fingerprint, lama_inpaint, remove_sparkle, make_refs.
- `flow_outputs\anime_kaliya\adhyay_01` on disk: 18 finals in `final\`; 44 `shots\*__review.json`; `download_queue.jsonl` 24 lines; `flow_log.jsonl` 19 lines; `shots_progress.jsonl` 48 lines, none with `decided_by` (legacy); `accepted.jsonl` missing; `keyframes_h3\` 10 files at 864x1536; 4 job files with 22 entries.
- Packs in `stories\kaliya_mardan\`: `pack_dots_full_v22` = 45 shots, episodes 1-5 = 7/9/9/8/12, all mode `fl2va`. `pack_dots_v22` = 56 shots (11/13/12/10/10); two `stage_2_raw_content_filter_*.json` files show stage 2 was retried by hand. `pack_nemotron_v1` = 26 shots, no `bible.json`.
- No shot file exists for LEAP-01..05. `t0_shots.json` covers LEAP-03 arms only (gap G4).
- Owner's video choice: arm C = route `sing8` (Ref2VA, 768x1344, 124 frames). Arm A (`pika6`) is the fallback.
- Reel = episode number (`episode` in shots.json). Scope "reel N" = all shots of episode N.

## 1. Screens (ASCII sketches)

### 1.1 Shell (every page)
```
+----------------------------------------------------------------------+
| ANIME STUDIO  Kaliya Mardan     SPEND [OFF]    job: none   127.0.0.1 |
+-------------+--------------------------------------------------------+
| > Story     |  section content                                       |
|   Images    |                                                        |
|   Bridge    |                                                        |
|   Video     |                                                        |
|   Export    |                                                        |
+-------------+--------------------------------------------------------+
| running job log tail (last 12 lines, redacted)                       |
+----------------------------------------------------------------------+
```
Badges: green OK, grey NOT RUN, amber NEEDS REVIEW, red FAILED, blue RUNNING. SPEND reads OFF unless the server was started with `--allow-spend`.

### 1.2 Story
```
STORY  slug [kaliya_mardan v]  pack [pack_dots_full_v22 v]  writer via: nvidia (fixed)
+------------------------------------------------------------------------+
| paste story text here (max 200 KB)                                     |
+------------------------------------------------------------------------+
[Save as SOURCE.md] [Run writer: new pack] [Resume pack] [Check pack]
Stages  [1 OK] [2 OK] [3e1 OK] [3e2 OK] [3e3 OK] [3e4 OK] [3e5 OK] [5 OK]
Gate 1 (story analysis as written)  <pre> scene list, episode split ... </pre>
Episodes  #   shots  seconds  check        Characters (bible)  Places (bible)
          1    7      ...    PASS/ISSUES   ...                 ...
Shots   id       ep  mode    sec   cut_in -> cut_out         issues
        SHOT-01  1   fl2va   5.2   ...                       0
check_pack JSON: shots 45  modes fl2va 45  total_seconds ...  issues (list)
```

### 1.3 Images (adhyay 1)
```
IMAGES  adhyay [1]   tabs: [Series] [Jobs] [Shots] [Progress] [Queue] [Finals]
Series    sheet / chip          accepted   model
          CHAR-KRISHNA          yes        Nano Banana 2.1 x2
Jobs      shot        method  chips  attempts/cap  status  [Packet] [Build*]
Shots     shot   candA  candB  Q1..Q6 (A)  verdict  [Neighbours] [Run reviewer]
          per candidate row: [Queue kept] [Accept (owner)] [Collect]
Progress  shot  status(badge)  attempts  decided_by  note   (legacy rows greyed)
Queue     pending N    filed N     accepted N     (live counts)
Finals    [thumb] [thumb] [thumb] ... 18 tiles; click = full size
```
`Build*` is disabled with the reason shown until gap G1 is closed.

### 1.4 Bridge
```
BRIDGE  source: adhyay_01\final (10 LEAP keyframes expected)  target [768x1344 v]
[Dry run]  [Write keyframes]
file            status   crop box               removed px
LEAP-01A ...    DRY      (...)                  ...
output: keyframes_h3\  10 files at 864x1536 already present (not overwritten)
```

### 1.5 Video
```
VIDEO  shot file [stories\...\shots.json v]  batch [leap01_05_sing8]  route [sing8 v]
Scope  (o) shots [SHOT-01, SHOT-02 ...]   ( ) reel [1 v]   ( ) all
Keyframes root [...]   profile 5   target colab   resolution [768x1344 v]
[1 Prepare batch (no GPU)]  -> shots 15, routes, frames, run.py bytes, embed MB, errors
Colab  sessions: none   balance: read live   rate: G4 10.05/h (estimate table)
       [Check Colab] [Run on Colab... (spend gate)] [Stop session <name>]
Live   log tail (redacted)            clips home: 3 of 15
Clips  shot/take   file          seconds  size   QA
       SHOT-T0-C   C_S42.mp4     5.17     ...    [Sheet] [Visual QA]
```

### 1.6 Export
```
EXPORT  reel [1 v]
Clips in order   SHOT-01 (take picked)  SHOT-02 (take picked) ...
Assembly plan    NOT BUILT (needs h3\assemble_reel.py or post.py; gap G12)
Reel files       none yet   [Open folder]
```

### 1.7 Spend dialog (opens for every `$` control; nothing starts before it)
```
+-- CONFIRM SPEND ----------------------------------------------------+
| argv   C:\Python314\python.exe director\t0_pack\run_t0_parallel.py  |
|        --go --gpu G4 --name <name>                                   |
| GPU G4, session <name>, clips 15 (LEAP-01..05 x 3 takes)             |
| estimate ~7.5 units (section 3), balance read live, cap 15 units     |
| Stop rule: runner stops the session only after every clip is home   |
| Type EXECUTE 7.5 to start: [______]   [Start]  [Cancel]             |
+----------------------------------------------------------------------+
```

## 2. Controls: exact command, inputs, outputs, risk
Conventions: `P` = `C:\Python314\python.exe`; `S` = `D:\aai work\anime_studio`; `F` = `D:\aai work\flow_outputs\anime_kaliya`; `<J>` = a job file under `S\flow\`; `<ID>` = shot id; `<A>`/`<B>` = candidate PNG under `F\adhyay_01\shots\`. Every subprocess gets `PYTHONDONTWRITEBYTECODE=1`, a list argv and `shell=False`.
Risk: **R** read-only; **W** writes local files (never deletes); **N** free NVIDIA model call (network, rate-limited); **$** spends Colab units or GPU time (spend gate and typed confirm); **X** not available yet.

### 2.1 Story
| Control | Exact command | Inputs | Shown after | Risk |
|---|---|---|---|---|
| Load story | none (file read) `S\stories\<slug>\SOURCE.md` | slug | text, bytes | R |
| Save story | none (file write, refuses overwrite unless ticked) | slug, text | path, bytes | W |
| Run writer (new pack) | `P S\director\write_pack.py S\stories\<slug>\SOURCE.md S\stories\<slug>\<pack> --staged --writer super-vl` (or `--writer ultra`; legacy: `--via nvidia --model <M>`) | slug, new pack name, writer from list (default super-vl) | stage badges (from `stage_*_raw.json`), log tail, `PACK.md` | N, W |
| Resume pack | same command, existing `<pack>` (saved stages are not sent again) | pack | same | N, W |
| Analysis | none (reads `PACK.md`, `bible.json`, `shots.json`) | pack | Gate 1 text, episodes, characters, places, shots | R |
| Check pack | `P S\director\check_pack.py <pack>` | pack | JSON: shots, modes, episode_seconds, total_seconds, issues | R |

### 2.2 Images
| Control | Exact command | Inputs | Shown after | Risk |
|---|---|---|---|---|
| Series and sheets | none (read `S\flow\flow_series_kaliya.json`) | none | characters, places, chip, accepted flags | R |
| Build jobs | BLOCKED until G1: `P S\flow\scripts\build_jobs_v2.py --adhyay 1 --spec <spec> --out <J> --series S\flow\flow_series_kaliya.json` (argv from RUN_NOTES) | spec file, out name | job count, warnings | W |
| Jobs and chips | none (read `S\flow\A_KM_flow_jobs_*.json`) | none | table per job: chips, prompt hash, attempts/cap | R |
| Agent packet | none (UI builds text from the job file, saved to `S\ui\runs\packets\`) | shots or one scene | Markdown with Copy button | W |
| Neighbour sheet | `P S\flow\scripts\neighbour_sheet.py --jobs <J> --shot <ID> --candidate <A> [<B>] --out F\adhyay_01\shots\<ID>__neighbours.jpg` | shot, candidates | image | W |
| Run reviewer | `P S\flow\scripts\review_shot.py --jobs <J> --shot <ID> --candidate <A> [<B>]` | shot, 1-2 candidates | Q1-Q6 table, verdict, fix, regen sentence; exit 0 PASS, 1 BLOCK, 3 UNSURE | N, W |
| Queue kept tile | `P S\flow\scripts\download_queue.py add --root F --adhyay 1 --shot <ID> --version <vNN> --edit-id <36 chars> --jobs <J> --model "Nano Banana 2.1 x2" --decided-by owner --note <text>` | shot, version, edit id (regex), note | queued line | W |
| Queue status | `P S\flow\scripts\download_queue.py status --root F --adhyay 1` | none | pending, filed, accepted lists | R |
| Collect from Downloads | `P S\flow\scripts\download_queue.py collect --root F --adhyay 1 --downloads C:\Users\Satvik\Downloads` | none | FILED / REFUSED / WAITING per item | W (writes `final\`) |
| Accept | `P S\flow\scripts\download_queue.py accept --root F --adhyay 1 --shot <ID> --version <vNN> --by owner --note <text>` | owner ticks "looked at full size" and types a note | accepted badge | W (owner decision) |
| Progress | none (read `F\adhyay_01\shots_progress.jsonl`) | none | badges, attempts, notes | R |
| Finals viewer | none (serves `final\*__final.png`) | none | 18 tiles, full size | R |
| Tidy finals | plan: `P S\flow\scripts\tidy_final.py --root F --adhyay 1`; apply: same plus `--apply` (only if plan is not empty) | none | moves plan | R, W (moves, never deletes) |

### 2.3 Bridge (Flow 2K to video keyframes)
| Control | Exact command | Inputs | Shown after | Risk |
|---|---|---|---|---|
| Bridge dry run | `P S\flow\scripts\bridge_flow_to_h3.py --final-dir F\adhyay_01\final --out-dir F\adhyay_01\keyframes_h3 --size <WxH> --dry-run` | size (enum 768x1344, 864x1536) | OK / SKIP / DRY / REFUSED lines | R |
| Bridge write | same without `--dry-run` | size | same, files written | W |

### 2.4 Video
| Control | Exact command | Inputs | Shown after | Risk |
|---|---|---|---|---|
| Shot file pick | none (list `S\stories\**\shots*.json` and `S\director\t0_pack\t0_shots.json`) | none | file list | R |
| Prepare batch (no GPU) | `P S\director\run_kaggle.py <shots.json> <keyframes_root> <batch> --ids <csv> --style kaliya_mardan --target colab --profile 5` | shot file, root, new batch name, scope ids | per-shot route and frames, settings count, run.py bytes, embed MB, errors | W (`S\director\colab_batches\<batch>\`) |
| Scope mapping | shots: `--ids` = chosen ids; reel N: `--ids` = ids with episode N; all: no `--ids` | scope | count shown before prepare | none |
| Colab sessions and balance | `colab.exe sessions` and `colab.exe usage` (fixed path `C:\Users\Satvik\.local\bin\colab.exe`) | none | sessions table, balance, rate | R (network read, no spend) |
| Colab execute, T0 runner today | `P S\director\t0_pack\run_t0_parallel.py --go --gpu G4 --name <name>` (dry run = same without `--go`) | GPU enum (G4 default), session name (regex), token, typed confirm | live log, clips home n of N, stop verification | $ |
| Colab execute after G2 | `P S\director\t0_pack\run_t0_parallel.py --batch <batch> --results <dir> --gpu G4 --name <name> --go` | same, plus batch dir and results dir | same plus `status.json` | $ |
| Colab stop | `colab.exe stop -s <name>`, then `colab.exe sessions` | session name from the list | "no sessions" or red STOP FAILED banner | R-ops (cuts spend, no confirm) |
| Clip QA sheet | `P S\director\clip_tools.py qa <clip.mp4> <out_dir>` | clip | frames, fps, duration, loudness | W |
| Visual QA | `P S\director\visual_qa.py <clip> <direction.json> <out_dir> --via nvidia --model <M> [--bible <bible.json>]` | clip, direction file, model | 9 scores, total, accept or not | N, W |

### 2.5 Export and ops
| Control | Exact command | Inputs | Shown after | Risk |
|---|---|---|---|---|
| Clips by reel | none (read the batch results folder) | reel N | clips in shot order | R |
| Assembly plan | X (not built, G12) | none | banner | X |
| Reel files | none (list the reel folder when it exists) | reel N | files, or "none yet" | R |
| Stop running job | kills the local process only | job id | job state, warning | ops |

Writer list (Q4, updated 2026-11-06): `super-vl` (default, `nvidia/nemotron-3.5-super-vl:free` on OpenRouter) and `ultra` (`nvidia/nemotron-3-ultra-550b-a55b:free` on OpenRouter); both free-only. The legacy NVIDIA model argument is still accepted. The reviewer model is fixed in `review_shot.py`; the UI only shows it.
Not exposed in v1: Kaggle push (`run_kaggle.py --push/--fetch`), any `--via claude` or `--via openrouter`, `--allow-paid`, `--stage-via`, `--logtostderr`.

## 3. Cost estimate rule (for every `$` control)
- Rates from HANDOFF 2026-11-05 23:45: G4 10.05 units/h, A100 6.73 units/h. Live check with `colab.exe usage` before the token is issued.
- Estimate = rate x (7 min cold model download + clips x 2.2 min + 5 min setup allowance) / 60. The 7 min and 2.2 min come from STATUS.md and the T0 timings (estimates, not measured here). The 5 min allowance is an assumption.
- Example, LEAP-01..05 x 3 takes on G4: 7 + 15 x 2.2 + 5 = 45 min = 0.75 h, about 7.5 units.
- Refuse the run when the balance is unknown or below 1.5 x estimate. The run also refuses above the cap (Q3).

## 4. Local API (127.0.0.1:8765)
Shared rules: every POST needs header `X-UI: 1` and a JSON body. `Host` must be `127.0.0.1:8765` or `localhost:8765`. Errors are JSON `{error}`: 400 bad input, 403 guard or spend gate, 404 unknown, 409 conflict (another job, file exists).

| Method | Path | Request | Response |
|---|---|---|---|
| GET | `/`, `/static/*` | none | HTML, JS, CSS |
| GET | `/api/status` | none | `{studio_ok, flow_ok, python, colab_cli, nvidia_key_files (count only), spend_allowed, job}` |
| GET | `/api/story` | none | `{slugs: [{slug, packs: [name], has_source, latest_pack, latest_model}]}` (latest_model = the model of the newest pack; from the run registry) |
| GET | `/api/story/{slug}` | none | `{text, bytes}` |
| POST | `/api/story/{slug}` | `{text, overwrite: false}` | `{saved, bytes}`; 409 if the file exists |
| GET | `/api/registry` | none | `{stories: [run-log summary per story: slug, title, source, latest_pack, packs, pack_models, run_count, status, last_run_at, last_run_id, next_pack]}`; read only; 503 if the registry module is missing |
| GET | `/api/registry/{slug}` | none | `{slug, story, summary, runs, steps, report}`; `report` is the RUN_REPORT text; 400 for a bad slug, 404 for no such story; read only |
| GET | `/api/pack?pack=stories/<slug>/<name>` | none | `{stages: {"1": bool, "2": bool, "3e1": bool, ..., "5": bool}, gate1, episodes: [{n, shots, seconds}], characters, places, shots, check}` |
| POST | `/api/preview` | `{command, args}` | `{argv, risk, estimate, token, expires_s: 60, needs_confirm}` |
| POST | `/api/run` | `{token, confirm}` (`confirm` for `$` commands, e.g. "EXECUTE 7.5", and for `write_pack_claude` the typed word "CLAUDE") | `{job_id}`; 403 if spend is off or claude is off; 409 if a job runs |
| GET | `/api/jobs` | none | `[{id, command, state, rc, started, ended}]` |
| GET | `/api/jobs/{id}/log?tail=200` | none | text, redacted |
| GET | `/api/jobs/{id}/result` | none | parsed lines for known commands (bridge, reviewer exit, queue, collect) |
| POST | `/api/jobs/{id}/stop` | `{}` | `{state, warning}`; warning on `$` jobs: check Colab sessions |
| GET | `/api/images?adhyay=1` | none | `{series, sheets, jobs, shots: [{id, candidates, reviews}], progress, queue, filed, accepted, finals}` |
| GET | `/api/review?shot=<ID>&cand=<file>` | none | `{verdict, fix, regen_sentence, edit_instruction, answers: {Q1..Q6}}` |
| POST | `/api/packet` | `{jobs, shots}` | `{path, markdown}` |
| GET | `/api/video` | none | `{shot_files, batches: [{name, run_py_bytes, settings, embed_mb}], clips: [{shot, take, file, bytes, seconds, qa}]}` |
| GET | `/api/colab` | none | `{sessions: [{name, gpu, status}], balance, rate}` (two read-only commands, 60 s timeout) |
| GET | `/api/export?reel=N` | none | `{clips_in_order, assembly: "not built" or plan, reel_files}` |
| GET | `/api/file?path=...` | none | bytes; allowed roots and extensions only; max 60 MB |
| GET | `/api/writers` | none | `{default, claude_allowed, confirm_word, checks: {nvidia_key_files, openrouter_key_file, claude_cli}, options: [{id, group, command, args, cost, speed, quality, tested, available, reason}]}`; read only; never key text or paths |
| GET | `/i18n/{lang}.json` | none | the UI string table for en or mr (JSON); 404 for any other name |
| GET | `/fonts/NotoSansDevanagari-Variable.ttf` | none | the bundled Devanagari font (font/ttf) |

## 5. Files and data
```
anime_studio\ui\
  PLAN.md             this file
  server.py           the one server file: stdlib http.server, whitelist,
                      validators, readers, job runner, redactor, audit
  static\index.html   one page, left section list
  static\app.js       fetch calls, tables, spend dialog
  static\style.css    plain CSS, no framework, no CDN
  test_ui.py          offline tests with fake tools (pytest)
  runs\               GITIGNORED (add `ui/runs/` to .gitignore in M1):
                      jobs\<id>.json and .log, packets\, audit.jsonl
```
Read (read-only unless marked):
- `S\stories\<slug>\SOURCE.md` and `S\stories\<slug>\<pack>\`: `PACK.md`, `bible.json`, `shots.json`, `stage_*_raw.json`
- `S\director\style\kaliya_mardan.json` (names only, optional)
- `S\director\colab_batches\<batch>\`: sizes of `run.py` and `run.ipynb` (never the content, 7 MB)
- `S\director\t0_pack\results\` and later batch results: mp4 names, `timeline.txt`, `wgp_*.log` names
- `S\flow\flow_series_kaliya.json`, `S\flow\A_KM_image_spec_*.json`, `S\flow\A_KM_flow_jobs_*.json`
- `F\adhyay_01\`: `final\`, `shots\` (`*__review.json`), `references\`, `refs_video\`, `keyframes_h3\`, `download_queue.jsonl`, `flow_log.jsonl`, `shots_progress.jsonl`, `accepted.jsonl` (when present)
- `C:\Users\Satvik\Downloads`: file names only, to preview collect

Written: `S\stories\<slug>\SOURCE.md` (save), new pack folders, `S\ui\runs\*`, `S\director\colab_batches\<batch>\`, `F\adhyay_01\` (`shots\`, `final\`, `download_queue.jsonl`, `accepted.jsonl`), `keyframes_h3\` (bridge).

Never read: `secrets\`, any `.env`, `kaggle.json`, Colab auth files, `animation_research_tool\` key files, anything under `granthstudio\`.

## 6. Security
- **Local only.** Bind `127.0.0.1` only, port 8765. Refuse any `Host` other than `127.0.0.1:8765` or `localhost:8765` (DNS-rebinding guard). Every POST needs `X-UI: 1` (a cross-site form cannot set it).
- **Whitelist.** One `COMMANDS` table in `server.py`: id, script path (built from `S`, never from input), argument schema, risk, `needs_spend`. Nothing else can run. `subprocess.run/Popen` with a list argv and `shell=False`. Banned flags are never added: `--logtostderr`, `--allow-paid`, `--push`, `--fetch`, `--stage-via`, `--via claude`, `--via openrouter`.
- **Argument schema.** slug `^[a-z0-9_]{1,40}$`; shot id `^[A-Z0-9][A-Z0-9_-]{0,39}$`; version `^v\d{2}b?$`; edit id `^[0-9a-f-]{36}$`; size in enum; model in enum; note up to 200 printable characters, no newlines; batch and pack names `^[a-z0-9_-]{1,40}$`. Any other value gives 400.
- **Path checks.** Resolve with `realpath`; the result must be under `S` or `F` (or the Downloads folder for collect only). Refuse `granthstudio`, `animation_research_tool`, any `secrets` folder, `.env`, `kaggle.json`. Refuse any path that leaves its root after resolution (symlinks included).
- **No secrets.** The UI never opens key or credential files. Status shows the count of NVIDIA key files by name only. Log tail, packets and audit lines pass a redactor: `ya29\.\S+`, `Bearer\s+\S+`, `nvapi-\S+`, `hf_[A-Za-z0-9]{20,}`, `sk-[A-Za-z0-9_-]{16,}`, `AIza[0-9A-Za-z_-]{30,}`, `token=\S+`. A packet with a key-like match is not written.
- **Spend gates (for `$`).** Server starts with spend OFF; `--allow-spend` turns it on (owner runs it). Preview returns a token (60 s, bound to the argv hash, single use). Run needs the token and the typed confirm text. One job at a time. Refuse on unknown balance or balance below 1.5 x estimate. Cap per run (Q3).
- **Stopping paid jobs.** Stop kills only the local process. A `$` job then shows a red banner "the session may still run" and offers `colab stop` plus a `colab sessions` check. Lesson from HANDOFF 2026-11-06: killing the runner leaves the VM running.
- **No overwrite.** The writer resumes from saved stage files; bridge, filer and collect refuse existing outputs; save story refuses without `overwrite`. No delete command exists in the whitelist.
- **Audit.** `runs\audit.jsonl`: one line per preview, run and stop (time, command id, redacted argv, rc). No keys.
- **No Claude.** The UI never starts the `claude` CLI. Writer `--via` is fixed to `nvidia`. Visual QA `--via claude` is refused in the UI (and removed from the script, G11).
- **Network.** The UI makes no outbound calls itself. Only the listed scripts do: writer, reviewer and visual QA (free NVIDIA tier, shared 10 calls per key per minute rule), and the Colab CLI.
- **File serving.** `/api/file` serves only `.png .jpg .jpeg .mp4 .json .md .txt .jsonl .log` from allowed roots, max 60 MB, no directory listings.

## 7. Test plan (offline, fake runners)
Run from `D:\aai work`: `C:\Python314\python.exe -m pytest -q -p no:cacheprovider anime_studio\ui`.
Fake tools: tiny Python scripts written into pytest `tmp_path`. They print lines and write files like the real ones. The `COMMANDS` table takes a test override. Tests never run the real scripts (they would write into the repo) and never call the network, Colab, NVIDIA or Claude.
1. **Argv builders:** one test per command id; exact argv list compared.
2. **Refusals:** unknown command; shell characters in slug; `..` in paths; `granthstudio` path; symlink out of root (skipped if the OS refuses symlinks); `--logtostderr` smuggled in a note; bad shot id, version, edit id (35 chars), size not in enum, `claude` as via.
3. **Guards:** wrong `Host` gives 403; POST without `X-UI` gives 403.
4. **Preview token:** expiry with a fake clock; second use refused; changed args refused.
5. **Spend gate:** spend off gives 403 even with a valid token; spend on with a wrong confirm gives 400; right confirm starts the fake Colab job.
6. **Job runner:** log tail; state changes; second job gives 409; stop kills the fake process; stop on a `$` job returns the session warning.
7. **Colab failure path:** fake `stop` leaves the session listed, so the page shows STOP FAILED.
8. **Redaction:** fixture log, packet and audit containing fake tokens; none reach the output.
9. **Readers:** synthetic pack (2 episodes, 4 shots, bible with 2 characters) gives the expected counts. Synthetic adhyay folder (2 jobs, 3 reviews, queue 3 lines, flow_log 2, 3 legacy progress lines) gives pending/filed counts equal to `download_queue.py status` on the same fixture.
10. **Scope mapping:** shots, reel N, all give the expected `--ids`.
11. **Colab parsers:** text fixtures of `sessions` and `usage` (empty list and one session).
12. **Bridge output:** OK, SKIP, DRY, REFUSED lines parsed; `--dry-run` present in the dry argv.
13. **Static checks:** `index.html` has no `http(s)://` links; `server.py` has no `shell=True` or `os.system`; imports are stdlib plus Pillow only.
14. **Optional read-only smoke:** if the real folders exist, parse `pack_dots_full_v22` (45 shots) and `adhyay_01` (18 finals). No writes.

## 8. Build order (5 milestones)
- **M1 Safe shell.** Build: `server.py` with the whitelist, validators, guards, preview token, spend flag, job runner, redactor, audit; static page with the section list and the spend dialog; `.gitignore` entry. Done when: tests 1-8 pass with fake tools, `grep -n "shell=True\|os.system" ui\server.py` is empty, and the server refuses a POST without `X-UI`.
- **M2 Story.** Build: load and save story; writer run and resume (`--via nvidia` only); stage badges from files; analysis view (Gate 1 text, episodes, characters, places, shots); check pack JSON. Done when: test 9 passes for the story part, and the real `pack_dots_full_v22` shows 45 shots and episodes 7/9/9/8/12. A live writer run waits for the owner's OK.
- **M3 Images.** Build: series, jobs, shots, review Q1-Q6, progress, queue, finals viewer; packet generator; neighbour sheet; reviewer; queue kept; collect; accept; tidy dry run. Build-jobs stays disabled until G1 and Q5. Done when: the real `adhyay_01` shows 18 finals, 44 reviews, 24 / 19 / 48 lines with the 48 progress rows flagged legacy; queue status matches `download_queue.py status` on the fixture; the owner has approved the packet text for one job.
- **M4 Bridge and video prepare.** Build: bridge dry run and write; shot file picker; scope mapping; prepare batch with a summary; read-only Colab panel; clip list from the results folder. Done when: tests 10-12 pass; prepare on a 2-shot synthetic fixture writes only into a temp batch root; the execute control is absent or disabled while spend is off.
- **M5 Video execute, QA, export.** Prerequisites: G2 (runner with `--batch`, `--results`, `status.json`) and G4 (LEAP shot file) done. Owner rule: Codex gpt-6.1-sol review of the runner change before any unit-spending run. Build: Colab execute behind the spend gate with live log, clips home count, stop and verify; clip QA sheet; visual QA (N); export view showing "not built". Done when: the fake-Colab end-to-end test passes, including the failure path (red banner and stop button); the first real G4 run (about 7.5 units) happens only after the owner types the confirm text.

## 9. Gaps (existing scripts or files lacking what the UI needs)
- **G1 Job builder not in the studio.** `build_jobs_v2.py` exists only in `granthstudio`. Change: owner-approved frozen copy into `S\flow\scripts\` with its own test (Q5). Granth stays untouched.
- **G2 Colab runner is T0-only.** `t0_pack/run_t0_parallel.py` hardcodes `colab_batches\t0\run.py`, session `t0-kaliya` and `t0_pack\results`; it prints text only. Change: add `--batch` and `--results`; write `status.json` (clips home and missing, session, rc, usage before and after). Keep dry run as default.
- **G3 No render manifest.** `run_kaggle.py --target colab` prints only "built <folder>". Change: write `render_manifest.json` in the batch folder (per shot: route, resolution, frames, settings file, embed MB).
- **G4 No LEAP-01..05 shot file.** `t0_shots.json` covers LEAP-03 arms only; `DIRECTION.md` is prose. Change: a small expansion like `t0_variants.py` (route `sing8`, 768x1344, 3 takes) or an owner-written shot file.
- **G5 Writer has no JSON progress and no dry plan.** Stage progress is only file presence; Gate 1 analysis is prose, so episodes come from a regex on "Episode N"; stage 2 needed manual content-filter retries. Change: Gate 1 ends with a ```json analysis``` block (episodes, characters, places, reels) saved as `analysis.json`; `write_pack.py --plan` lists stages and call count without calling.
- **G6 check_pack mixes layout problems into text.** Change: add `layout_issues: [{shot, code, text}]` to its JSON.
- **G7 Acceptance not recorded.** `accepted.jsonl` does not exist; the 18 finals have no accept record (sheets have `accepted` flags in `flow_series_kaliya.json`). Change: owner runs `accept --by owner` per final (or an owner-approved one-time backfill); `status` gets `--json`.
- **G8 Progress file drift.** All 48 lines of `shots_progress.jsonl` lack `decided_by`, so `progress_log.check` would reject them. Change: UI shows them as legacy; add a read-only legacy mode to `progress_log.py`.
- **G9 Bridge output and pattern.** Text lines only; file pattern hard-coded to `LEAP-*`. Change: `--json` output and `--pattern` flag.
- **G10 Reviewer depends on an outside folder.** `review_shot.py` imports `animation_research_tool\nvidia_scheduler.py` from `D:\aai work` with no setting. Change: env var or flag for the folder; the UI checks it exists.
- **G11 Visual QA lists `--via claude`.** The docstring says it is refused. Change: remove the choice.
- **G12 Video engine and assembly missing.** `h3/` modules and `post.py` do not exist. Change: owner decision (Q1), then build. Until then assembly shows "not built".
- **G13 `clip_tools.py` CLI is ambiguous.** Any command other than `qa` runs last-frame. Change: explicit subcommands `qa` and `last`.
- **G14 Colab CLI has no JSON.** `sessions` and `usage` are text. Change: UI parser with captured fixtures; confirm the format on the first owner-run check.

## 10. Open questions for the owner (max 5)
- **Q1 Video engine for v1.** OK to drive the proven `director/` chain (Wan2GP, Ref2VA `sing8`) now and leave `h3/` (SPEC only; ComfyUI route with unverified node names, not adopted per HANDOFF 2026-11-06) for later?
- **Q2 Resolution for LEAP-01..05.** 768x1344 (tested in T0) or 864x1536 (bridge default; untested on `sing8`, about 28% more compute)? Plan default: 768x1344 until one test clip is checked.
- **Q3 Spend cap.** Maximum units one Colab execute may start (plan default 15), and G4 as the only GPU offered in the UI?
- **Q4 Model calls from buttons.** Writer default `nvidia/nemotron-3-ultra-550b-a55b`. May the reviewer and visual QA NVIDIA calls run from buttons (free tier, shared rate limit)?
- **Q5 Build jobs.** May a frozen copy of `build_jobs_v2.py` be placed in `anime_studio\flow\scripts\` (copy only, Granth unchanged) so "Build jobs" works?

## 11. Review amendments and decisions (Claude, 2026-11-06; binding for the build)
Reviewed against the real scripts and the owner's rules. The plan is sound (whitelist, spend gate, offline tests, no secrets). Changes and defaults for the five open questions:
1. **Reviewer is Dots, not Codex.** Every "Codex review" in this plan means `flow/scripts/dots_review.py` (owner rule 2026-11-06). Section 8 M5 prerequisite becomes: Dots review of the runner change before any unit-spending run.
2. **Q1 = yes.** v1 drives the proven `director/` chain (Wan2GP, Ref2VA `sing8`) for real renders. ADD a read-only/prepare panel for the new `h3` engine: whitelisted command `P -m h3.render_controller --story-file <f> --scope shots|reel|all [ids] --mode prepare-only` (cwd = S). `h3/render_controller.py` is being built separately; if `h3\render_controller.py` is missing the panel shows "h3 engine not built yet" (test this with a fake). `--mode execute` is NEVER exposed in v1.
3. **Q2 = 768x1344 default**, 864x1536 selectable; label it "untested on sing8, about 28% more compute".
4. **Q3 = cap 15 units per execute; GPU enum = G4 and A100** (both proven), default G4.
5. **Q4 = yes**: reviewer and visual-QA NVIDIA calls may run from buttons (free tier, one job at a time keeps the 10-calls-per-key-per-minute rule; the reviewer already uses the 14-key scheduler).
6. **Q5 = no for now**: "Build jobs" stays disabled with its reason (G1). Do not copy anything from granthstudio.
7. **Agent packet** (section 2.2) must state the owner rule: Flow generation and download agents run on **Haiku, effort LOW**; pass one scene per agent, own tab id; model chip Nano Banana 2.1 x2; no downloads in phase 1.
8. **Gaps to close in this build (small, each with a test):** G2 (`run_t0_parallel.py --batch/--results`, `status.json`, dry run stays the default), G3 (`render_manifest.json` from `run_kaggle.py --target colab`), G7 (`download_queue.py status --json`), G9 (`bridge_flow_to_h3.py --json`), G11 (remove the claude choice from `visual_qa.py` if present), G13 (`clip_tools.py` explicit subcommands `qa` and `last`, old no-argument behaviour kept working). Leave G1, G4, G5, G6, G8, G10, G12, G14 as documented gaps shown in the UI as "not available yet".
9. **Story analysis view** shows what exists now (Gate 1 text, episodes, characters, places, shots, check_pack result); a "story analysis" JSON (G5) is future.
10. **Everything the owner asked must be visible on one page:** Story -> Images -> Bridge -> Video (prepare, Colab status, clips) -> Export (shows "not built" where true). Keep it plain: no framework, no CDN.
11. **Hard rules for the build:** no real network/Colab/NVIDIA/Claude call in any test; the server is NOT started by the build agent except a 3-second local smoke on 127.0.0.1 with spend OFF; never run a spend command; no commit.
