# UI audit and update plan (2026-11-07)

Auditor: read-only pass over the UI and the director/h3/flow modules it calls. Only this file was written.
Scope read: HANDOFF_2026-11-07.md (sections 1, 2, 3, 8, 9, 9b, 10, 11), research/H3_V4_CONTRACT_2026-11-07.md (+ ADDENDUM), research/GAP_REVIEW_SUPER_VL_2026-11-07.md, research/OWNER_MASTER_PROMPT_V4_2026-11-07.txt, ui/server.py, ui/pipeline.py, ui/static/{pipeline.js, app.js, index.html, style.css}, ui/test_static.py (+ grep of test_ui/test_pipeline/test_registry names).
Not run: the four test suites (read-only audit). Not touched: anything under D:\aai work\granthstudio.
Live probe (GET only, port 8765): the server running now is STALE. `/api/status` 200, `/api/pipeline` 200, `/api/registry` returns `{"error": "unknown path"}` (confirms handoff item S3).
Files not present yet (in progress by other agents): director/story_state.py, director/story_links.py, director/ops_checks.py. The UI plan below codes against the contract named in section 4.
Git: ui/server.py, ui/pipeline.py, ui/static/*, ui/test_ui.py are modified and uncommitted in the working tree; this audit reads the working tree.

## 1. CURRENT UI MAP

### 1a. Screens and panels (wizard = `#wizard`, advanced = `<details id="advanced-tools">`, collapsed by default)

| Screen / panel | Where | What it does | Endpoints used |
|---|---|---|---|
| Top bar | index.html:11-18 | Project name (static "Kaliya Mardan" until JS runs), SPEND ON/OFF badge, job badge, server state | GET /api/status (app.js tick) |
| Error / success bar | index.html:20-23; pipeline.js:1399-1424 | One shared bar for errors and success, auto-hides after 8 s | none |
| Stepper | index.html:26-59; pipeline.js:425-435 | Six stages, status text only (not links) | from /api/pipeline |
| 1 Story card | pipeline.js:490-618 | Pick slug, new slug, edit text, Save story | GET /api/story, GET/POST /api/story/<slug>, POST /api/pipeline/project |
| 2 Analysis card | pipeline.js:626-777 | Pack name, Run analysis (writer, fixed super-vl), Gate-A tables (shots, episodes, names, check JSON) | POST /api/pipeline/project, POST /api/preview (write_pack), POST /api/run, GET /api/pack |
| 3 Images card | pipeline.js:779-870, 885-936 | Build image jobs (build_spec then build_jobs_cmd, adhyay 1 fixed), Flow agent packet, counts | POST /api/preview, POST /api/run, GET /api/jobs, GET /api/images, GET /api/pack, POST /api/packet |
| 4 Read-out card | pipeline.js:989-1109 | Stat tiles, episode table, warnings, checks | GET /api/pipeline/summary |
| 5 Render card | pipeline.js:1111-1162 | Prepare render (h3_prepare, sends shots.json), clips count | POST /api/preview, POST /api/run |
| 6 Export card | pipeline.js:1164-1169 | Placeholder text only | none |
| Gate cards A-D | pipeline.js:1180-1307 | Approve / reject, note, START for Gate C | POST /api/pipeline/gate |
| Runs & documents | pipeline.js:1426-1554 | Story table, run list, steps, RUN_REPORT text | GET /api/registry, GET /api/registry/<slug> |
| Confirm / preview modal | pipeline.js:1309-1396; app.js:407-419 | Confirm argv before run (two separate implementations on #modal) | POST /api/preview, POST /api/run |
| Polling | pipeline.js:1557-1583 | Every 5 s, paused when tab hidden | 4 GET requests per tick |
| Advanced: Story | index.html:85-138; app.js:585-709 | Slug/pack selects, load/save text, writer run, Check pack | GET /api/story, GET/POST /api/story/<slug>, GET /api/pack[?check=1], preview/run write_pack |
| Advanced: Images | index.html:141-195; app.js:711-1013 | Series, Jobs, Shots (review, neighbour sheet, queue, accept), Progress, Queue (collect, tidy), Finals | GET /api/images, GET /api/review, POST /api/packet, preview/run of neighbour_sheet, review_shot, queue_add, queue_accept, queue_collect, tidy_plan |
| Advanced: Bridge | index.html:198-212; app.js:1040-1066 | Bridge dry run / write keyframes | preview/run bridge_dry, bridge_write |
| Advanced: Video | index.html:215-278; app.js:1069-1300 | Shot file, scope, prepare batch, h3 prepare, clips and QA, Colab check, Run on Colab (spend gate), stop session | GET /api/video, GET /api/h3, GET /api/colab, preview/run run_kaggle_prepare, h3_prepare, clip_qa, visual_qa, colab_run, colab_stop |
| Advanced: Export | index.html:281-301; app.js:1315-1335 | Reel clips in order, assembly "not built" | GET /api/export?reel= (no pack sent) |
| Job log bar | index.html:306-313 (inside collapsed details) | Last 12 log lines, stop job | GET /api/jobs/<id>/log, POST /api/jobs/<id>/stop |

### 1b. Server endpoints (ui/server.py dispatch, L1274-1333)

| Method | Path | Purpose |
|---|---|---|
| GET | / , /static/*.css|js , /<file>.css|js | static UI files |
| GET | /api/status | studio/flow/Colab CLI presence, spend flag, running job |
| GET | /api/h3 | h3 engine built or not |
| GET | /api/story | slugs with packs, latest model |
| GET/POST | /api/story/<slug> | read / save SOURCE.md (overwrite flag) |
| GET | /api/pipeline, /api/pipeline/summary | wizard state (project.json pointer) / summary numbers |
| POST | /api/pipeline/project | set story_slug, pack, images_dir, results_dir, takes |
| POST | /api/pipeline/gate | record gate decision (no story/pack in request) |
| GET | /api/registry, /api/registry/<slug> | run log summary / detail + RUN_REPORT |
| GET | /api/pack?pack=&check= | pack read (stages, episodes, bible names, shots) |
| POST | /api/preview, /api/run | two-step command runner (token, 60 s, spend gate) |
| GET | /api/jobs, /api/jobs/<id>/log, /api/jobs/<id>/result | job list, log tail, parsed result |
| POST | /api/jobs/<id>/stop | stop local process |
| GET | /api/images?adhyay= | series, jobs, shots, progress, queue, finals (Kaliya paths) |
| GET | /api/review?shot=&cand=&adhyay= | one review verdict |
| POST | /api/packet | Flow agent packet markdown |
| GET | /api/video, /api/colab, /api/export?reel=&pack= | video batches and clips / Colab sessions and balance / export view |
| GET | /api/file?path= | bytes of allowed files (png, jpg, mp4, json, md, txt, jsonl, log) |

## 2. DEFECTS

Severity: H = blocks the owner's end-to-end or risks cost, data or wrong approvals. M = wrong or confusing, or a real gap. L = polish.

### 2a. High

| ID | Sev | File:line | Why | One-line fix |
|---|---|---|---|---|
| D1 | H | ui/pipeline.py:65-80, 83-112, 483-510; ui/server.py:1263-1271 | Approvals are one global `runs/approvals.jsonl`. Records have no story or pack, so Gate A approved for story X shows approved for story Y. | Add `story` and `pack` to every record; filter reads by scope; ignore legacy records without them; POST gate requires story and pack. |
| D2 | H | ui/static/pipeline.js:511-535, 153-160 | Story select changes only local state. The 5 s poll sets the slug back to the server project, reloads the old story text, and the select flips back. | On select change POST /api/pipeline/project, then reload; render the select from server state only. |
| D3 | H | ui/pipeline.py:568-576 | summary() iterates `bible["characters"|"environments"|"props"]` as lists. The V4 canonical bible is a dict keyed by id, so `.get` on a string raises: /api/pipeline/summary returns 500 on every poll. | Normalise bible sections: `list(x.values()) if dict else x`. |
| D4 | H | ui/server.py:669-670, 686-688; ui/pipeline.py:546-549, 554-555; ui/static/pipeline.js:709-710 | Readers use legacy keys `mode` and `seconds`; V4 rows have `route` and `editorial_duration_sec`. Bible read as list only. V4 packs show blank modes and 0 seconds and fail "every shot has seconds>0". (Current super-vl pack is still legacy: shots have mode/seconds.) | One field map helper: `route or mode`, `editorial_duration_sec or seconds`; accept both bible layouts (same rule as pack_to_spec.py:172). |
| D5 | H | ui/server.py:33, 47, 486, 725, 1313; ui/static/index.html:220 | One project only: FLOW_ROOT is `flow_outputs/anime_kaliya`, STORY_PACK default, run_kaggle `--style kaliya_mardan --profile 5` hard-coded, series read from `flow_series_kaliya.json`, default batch `leap01_05_sing8`. | Take style and profile from the story; roots per story from story_links; keep Kaliya only as an explicit legacy project. |
| D6 | H | ui/server.py:1221-1230 (clips filter at 1225); ui/static/app.js:1317-1319 | Export never sends `pack`, so it reads the Kaliya pack. Clips are matched by shot id across all stories (`read_video` is global), so two packs with SHOT-01 mix. | Require story and pack; select clips only from that pack's results folder. |
| D7 | H | ui/static/pipeline.js:1127-1131; ui/server.py:500-506; h3/render_controller.py:70-74, 115-147 | "Prepare render" passes `shots.json` as `--story-file`; render_controller needs an H3 story JSON with `episodes` and `registry.execution_profile`, so it always fails. Reel scope sends `1`; controller expects an episode id such as `EP_01`. No builder from pack to H3 story exists. | Disable Prepare with the reason until an H3 story builder exists; map reel N to its episode id from that file. |
| D8 | H | ui/server.py:865-866, 1111-1119, 1148-1159; jobs kept in memory (826-830) | Single-job lock counts only "running". A stopped or stop_failed $ job no longer blocks, and a server restart forgets all jobs. A new Colab spend can start while an old session still runs. | Spend lock = any $ job not verified stopped; rebuild the job table from runs/jobs/*.json at start. |
| D9 | H | ui/server.py:854-863, 1076-1078, 1113-1114 | No cumulative spend ledger; the 15-unit cap is per execute only. The estimate uses the manifest at preview time, not at run time. | Append-only runs/spend_ledger.jsonl; cap on rolling total; re-read manifest at run and compare with preview digest. |
| D10 | H | ui/server.py:560-562, 888-900 | Colab session check runs only after colab_stop. A finished colab_run is not checked, so a session the runner did not stop shows nothing unless rc != 0. | Set post=colab_verify for every $ job; after end, list sessions and warn if the session is still listed. |
| D11 | H | ui/static/pipeline.js:805-819, 854-866; ui/server.py:1042-1044 (GET /api/images reads all generated folders, 742-743) | Flow packet picks the first jobs file that lists the shot ids, across all stories. | Pass story and pack; accept only jobs files in flow/generated/<slug>/. |
| D12 | H | ui/static/pipeline.js:1180-1284; 1289-1291 | Gate cards and approve call show no story or pack, so the owner cannot see what is approved. | Show "Story X - Pack Y" in the card header; send story and pack with every decision. |
| D13 | H | ui/pipeline.py:470-510 | Gate A can be approved with validator errors (no validator yet). Gate D can be approved with no Step 9 QC or audio/caption check (ui/pipeline.py:380-392 counts clips only). | Gate A needs validator ok (or owner override with note); Gate D needs QC pass + per-language checks. |
| D14 | H | .gitignore (`!stories/kaliya_mardan`, `stories/*`); git index | `stories/kaliya_mardan/SOURCE.md` and `milestone_leap/DIRECTION.md` are TRACKED. `RUNS.jsonl`, `RUN_REPORT.md`, `story.json` of kaliya_mardan are untracked and NOT ignored (git check-ignore finds no rule), so `git add -A` would publish them. | Ignore `stories/**` with an explicit allowlist; owner decides on the already-tracked files (git rm --cached needs a yes); check origin/main. |
| D15 | H | ui/server.py:1403-1414, 1436, 946-953 | Stale server (confirmed live: /api/registry unknown path). `status()` has no version, pid or start time. A new start on a busy port dies with a raw OSError. | Add GET /api/version (pid, started, server.py mtime at start vs now, stale flag); UI red banner; catch bind error with a clear message. |

### 2b. Medium

| ID | File:line | Why | One-line fix |
|---|---|---|---|
| M1 | ui/server.py:41, 1232-1236 | /api/file serves raw .log and .jsonl (ui/runs/jobs/*.log, stories/*/writer_run*.log) without redaction. | Redact text on read, or exclude ui/runs from /api/file. |
| M2 | ui/server.py:1021-1024 | story_save overwrite replaces SOURCE.md with no backup. | Write `SOURCE.md.bak-<timestamp>` first. |
| M3 | ui/server.py:1155 | `proc.kill()` kills only the parent on Windows; colab CLI, ffmpeg or Whisper children keep running. | `taskkill /T /F /PID <pid>` on Windows. |
| M4 | ui/server.py:946-953 | status has no disk free (C: nearly full, D: about 9 GB). | Add `shutil.disk_usage` for C: and D: to status. |
| M5 | ui/pipeline.py:51-52, 55-59 | Bad project.json silently becomes the default (story forgotten); save is not atomic. | Write to tmp and os.replace; report parse errors instead of defaults. |
| M6 | ui/pipeline.py:159-160 | expected_images = 2 x shots and planned_clips = shots x takes, whatever the route (T2VA has 0 images). | Take counts from `route` per shot. |
| M7 | ui/pipeline.py:546-556 (summary) | Warning above 80 s; the studio preset is 60-75 s (shot_table_spec STUDIO_REEL_RANGE). | Use STUDIO_REEL_RANGE. |
| M8 | ui/server.py:1041-1057 | project pack name is not checked to exist. | Check the pack folder exists or warn. |
| M9 | ui/static/app.js:272-273 | Every 403 is replaced by the spend/guard text, so "preview expired" shows as a spend message. | Prefix the guard text only for host, origin or X-UI refusals. |
| M10 | ui/static/app.js:1383; pipeline.js:1559-1564 | Two pollers (2.5 s and 5 s, 6-7 requests); app.js ignores visibility. | One poller with visibility handling. |
| M11 | ui/static/pipeline.js:291-323 | Whole wizard rebuilt on any change; buttons have no ids, so focus is lost; new-slug and other typed text not kept. | Patch cards in place, or restore focus by id for buttons. |
| M12 | ui/static/pipeline.js:1213-1215, 1295-1297 | Gate notes keyed by gate id only; they survive a story switch. | Key drafts by story|pack|gate. |
| M13 | ui/static/index.html:90, 106; pipeline.js:58, 661 | Stale copy: "writer via nvidia (fixed)", "free NVIDIA tier"; writer is free OpenRouter super-vl, fixed. | Show the real route from write_pack_route; remove fixed text. |
| M14 | ui/static/pipeline.js:668-672; index.html:66, 306-313 | Analysis run shows no running state in the wizard; job log is only in the collapsed advanced panel. | Job bar at the top of the wizard, always visible. |
| M15 | ui/static/pipeline.js:873, 896, 900-911 | Image build fixed to adhyay 1; build_spec sends overwrite=false, so a second build fails with no route to rebuild. | Show "spec exists" and offer rebuild with an explicit confirm. |
| M16 | ui/static/pipeline.js:1317-1319, 1379-1386; app.js:408-419 | Confirm dialog focuses Run first (Enter runs it); app.js modal has no focus trap or focus return; two implementations share #modal. | Focus Cancel first; one modal module. |
| M17 | ui/static/pipeline.js:1164-1169 | Export card is a placeholder. | Export panel (see feature g) or an honest "not built" with the next step. |
| M18 | ui/static/pipeline.js:1237-1250 | Gate D approve needs no extra confirm; approval is recorded and drives the next stage. | Confirm dialog with the story, pack and gate text. |
| M19 | ui/static/index.html:165; app.js:759-764 | "Build jobs disabled ... gap G1" is stale (builder exists in the wizard); test_static.py:246 pins the text. | Update copy and that test together. |
| M20 | ui/test_static.py:153-158, 169-184 | ES2018 and endpoint checks read app.js only; pipeline.js endpoints are untested. | Extend both checks to pipeline.js and to every new endpoint. |
| M21 | ui/static/style.css:491-502; index.html:306-313 | Sticky log bar inside details takes ~10 rem on a phone. | Collapsed by default on phone; one-line summary bar. |
| M22 | ui/static/pipeline.js:130-133 | api() calls r.json() on any response; a non-JSON 5xx shows "Unexpected token". | Read text, parse if JSON. |
| M23 | ui/static/pipeline.js:946-949 | waitForJob gives up after about 140 s while the job still runs. | Keep polling while running, with a visible status. |
| M24 | ui/server.py:791-809, 1223-1225 | read_video globs the whole stories tree on each export and video call (up to 300 files). | Cache per request or scope to the pack. |
| M25 | ui/pipeline.py:509 (apply_gate) | Gate decisions are written to runs/approvals.jsonl and to the story RUNS.jsonl only when the project has a story (ui/pipeline.py:507). | Record story and pack from the request, not from the project pointer. |
| M26 | director/run_registry.py:240-241, 454-460 | Run id is read then appended with no lock (threads and two processes). | Lock on RUNS.jsonl (owner: registry agent S1). |
| M27 | ui/static/app.js:1286 | Copy says "the runner stops the session only after every clip is home"; not verified in code. | Remove, or verify in run_kaggle.py. |
| M28 | ui/server.py:1266-1268 vs approvals | No single-pack check: a gate POST for a pack other than the project's is accepted. | Covered by D1 fix (409 on mismatch). |

### 2c. Low and accessibility / phone

| ID | File:line | Issue | Fix |
|---|---|---|---|
| L1 | index.html:13 | Static "Kaliya Mardan" before JS runs. | Empty or "(no story)". |
| L2 | index.html:26-59 | Stepper is not keyboard reachable; no aria-current. | Links or buttons with aria-current. |
| L3 | index.html:20 | error-bar has role=alert and aria-live (double announce); every poll error re-announces. | Announce only new errors. |
| L4 | index.html:227, 229 | video-ids and video-reel inputs have no label. | Add labels. |
| L5 | index.html:318 | #modal has no tabindex, so modal.focus() does nothing. | tabindex -1 on dialog. |
| L6 | index.html:328-330 | Lightbox has no close button (Escape and click only). | Visible close button. |
| L7 | style.css:546 | Dialog outline removed by focus-within rule. | Keep a visible focus ring. |
| L8 | style.css:252-256, 465 | Focus ring only on buttons; clickable table rows have background only. | :focus-visible for inputs, selects, rows. |
| L9 | style.css:572-588 | .success-toast unused. | Delete or use for success. |
| L10 | index.html:61-63 | No h1 on the wizard; page title is a span. | Heading structure. |
| L11 | app.js:61-62, 263 | Port 8765 hard-coded in messages. | Use location.host. |
| L12 | pipeline.js:1266 | Reject length check counts UTF-16 units, server counts characters. | Use the same count. |

Checked and not found: innerHTML, outerHTML, insertAdjacentHTML, document.write, eval, new Function (zero matches in ui/static). All text goes in with textContent. Links and sources use encodeURIComponent (app.js:1026, 1097). Host and Origin checks, X-UI on POST, loopback bind, safe_path, no shell (subprocess shell=False), command whitelist, token TTL and single use, typed confirm for $ runs: present and working as designed. Owner gate C START is enforced on the server (ui/pipeline.py:503-505).

## 3. FEATURES THE OWNER ASKED FOR (work items with endpoints, fields, acceptance)

| Feature | What the UI gets | Endpoints / fields | Acceptance test |
|---|---|---|---|
| (a) Language selector | Story card: checkboxes EN / HI / MR (order = priority, shown as chips), "All" button, at least one required. Story row shows languages. Read-out shows languages. Gate D shows one row per language. | POST /api/story/<slug>/languages {languages:["en","hi"]} -> {output_languages}; story.json `output_languages` (subset, ordered), `output_language` = first. write_pack preview args `out_lang` ("en,hi" or "all") -> argv `--out-lang en,hi` (staged only, already supported by write_pack.py:848). | languages "hi,en" keep order; "all" -> en,hi,mr; "mr,mr" and "" refused; argv contains `--out-lang`; story.json round-trip; checkboxes restored after reload. |
| (b) Where it stopped + Continue | Story card header: "Next: Gate A for pack_x (2 validator errors)" and a Continue button. Story list rows show state. | GET /api/story rows gain `state` = story_state.summarize_all(studio); GET /api/story/<slug>/state = story_state.summarize(studio, slug) -> {next_step:{stage, gate, label, pack}, warnings[], packs[], output_languages}. Continue = POST /api/pipeline/project {story_slug, pack} then jump to step. | Two stories each show own next step; Continue changes project and the stepper; a fake story_state returning an error shows the warning, not a crash. |
| (c) Gates scoped by story+pack, re-evaluated on switch | Gate cards show scope; approve sends scope; switching story re-fetches and clears drafts. | GET /api/pipeline?story=&pack= (default = project); POST /api/pipeline/gate {story, pack, gate, decision, note, confirm?} (409 if story/pack differs from the one shown); records carry story, pack, time, by. | Approve A on X/p1: Y/p2 shows open, X/p1 approved; legacy record without story is ignored; mismatch -> 409; switching story clears note drafts. |
| (d) Validator between analysis and Gate A | Panel after Analysis: ok chip, errors table (code, where, message), warnings count, stats, mode (v4 or legacy), "Run validator" button, repair status (from registry steps of kind validator). Gate A approve disabled while errors. | POST /api/pack/validate {pack} -> Report {ok, errors[{code,where,message}], warnings[], stats, mode, exit}; runs `director/pack_validator.py <dir> --json [--legacy]` (exit 0/1/2). GET /api/pack/validate?pack= -> last Report or 404. | Fixture pack with one S55-3 error shows code S55-3 and disables Gate A; a legacy pack runs with --legacy; button reruns; apply_gate A refuses with errors. |
| (e) YouTube link | Story card: "YouTube link" input, language choice (auto, en, hi, mr), ASR choice (auto, off, force), Run. If language unclear, buttons with the candidates; SOURCE.md exists -> overwrite choice. Result line: "captions used" or "Whisper used". | POST /api/story/<slug>/link {url, lang, asr, overwrite} -> preview then run command `yt_transcript` (risk N W, no spend). GET /api/jobs/<id>/result -> {status: ok\|needs_choice\|refused\|failed, candidates[], engine: captions\|whisper, chars, file}. Exit map: 0 ok, 3 needs_choice, 2 refused (stdout). | rc 3 shows candidate buttons and reruns with --lang; rc 2 "exists" offers overwrite; non-YouTube URL refused; argv has no spend flag. Needs machine-readable output from yt_transcript (see section 4 blockers). |
| (f) Render panels | Render stage: image jobs count, asset manifest status (blocking problems), per-shot fallback rung with attempts and next action, the 4 human choices as buttons, Step 9 QC result (or "not run", fails closed). | GET /api/render/status?story=&pack= -> {images, asset_manifest:{blocking_problems[], clips, placeholders, stale}, fallback:[{shot_id, attempts, rung, action, human_choices}], step9:{status, checks[]}, gate_d}. POST /api/render/choice {story, pack, shot, choice, note} (choice in shot_table_spec.HUMAN_CHOICES) -> append `<pack>/render/human_choices.jsonl`. | Stale hash shows blocking; a choice outside the 4 is refused; missing step9 result shows "not run" and Gate D stays closed. |
| (g) Gate D audio and captions per language | One row per selected language: VO files present/expected (audio/vo/<lang>/), captions .ass, final mp4 (export/<reel>_<lang>.mp4), checks (VO fit, dead air, loudness after AAC, BGM presence). | Same /api/render/status, field gate_d.languages[] from h3.gate_d_audio.plan_language_outputs (plan only; no ffmpeg run in v1). | Two languages -> two rows; missing mr VO -> that row shows missing and Gate D blocked. |
| (h) Ops panel | Disk free C: and D:, UI server health (pid, started, stale), Colab spend ledger (total units, cap, last runs, sessions listed). | GET /api/version; GET /api/ops -> {disk:{C:{free_gb}, D:{free_gb}, ok}, server:{pid, started, stale, build}, colab:{ledger_total_units, cap_units, runs[], sessions_listed}}. Disk from shutil.disk_usage (stdlib, no need to wait for ops_checks). | Free < 2 GB shows banner; server.py newer than start -> stale true and banner; ledger total equals sum of $ runs. |
| (i) Runs and documents | Story row links to its RUN_REPORT.md; "no report yet" when missing. | GET /api/file?path=stories/<slug>/RUN_REPORT.md (already allowed: .md). | Link opens text; 404 shows message. |
| (j) Visual pass | See section 3j below. | CSS and index.html only (U3). | Phone 375 px: no horizontal page scroll; every button >= 44 px high; focus ring visible on every control. |

3j. Concrete design:
- Layout: one column on phone (<760 px), two columns from 900 px (stepper left). Sticky header with project chips: story, pack, languages, spend badge.
- Stage cards: status chip = colour plus text (never colour alone): locked grey, ready orange, running blue, waiting amber, approved green, rejected or failed red. Current card gets a 6 px left bar (existing).
- Gate card: header shows "Story - Pack - Gate", then decision buttons full width on phone, approve left and reject right on desktop.
- Tables: on phone, shot and episode tables become stacked label/value blocks (td data-label), not horizontal scroll; sticky header row on desktop.
- Language checkboxes: pill toggles 44 px high, with "All" as a separate pill.
- Focus: 3 px outline for all controls (inputs, selects, textareas, table rows with tabindex), visible in both light colours.
- Empty states say what to do next ("Save the story to begin").
- Motion: keep the reduced-motion rule; remove unused toast or use it for success.
- Log bar: a one-line job bar at the top of the wizard, expanding to the last 12 lines on tap.

## 4. WORK-PACKAGE SPLIT (3 parallel coder agents, disjoint files)

| WP | Files owned (only these) | Tasks | Acceptance tests (must pass) |
|---|---|---|---|
| U1 backend | ui/server.py, ui/pipeline.py, ui/test_ui.py, ui/test_pipeline.py, ui/test_registry.py (new test file names allowed inside ui/) | Scoped approvals and gate API (D1, D12, M25, M28); project pointer on switch (D2 backend); V4-aware pack read and summary, dict bible (D3, D4, M6, M7); remove Kaliya hard-codes, per-story roots (D5); export and packet scoped (D6, D11); H3 prepare guard and reel mapping (D7); spend lock, ledger, post-verify, persisted job table (D8, D9, D10); validator endpoints and apply_gate A rule (D13); yt_transcript command (feature e); languages endpoint and out_lang arg (feature a); story_state wiring (feature b); render status and choice endpoints (f, g); /api/version, /api/ops, bind error (D15, h); file endpoint redaction and ui/runs block (M1); story_save backup (M2); kill tree (M3); atomic project.json (M5) | test_gate_scoped_by_story_and_pack; test_legacy_approval_without_story_ignored; test_gate_409_on_mismatch; test_summary_dict_bible_no_500; test_read_pack_v4_fields; test_reel_scope_maps_to_episode_id; test_prepare_refuses_shots_json; test_spend_lock_after_stop_failed; test_spend_ledger_cap_is_cumulative; test_run_colab_verifies_session_after_end; test_persisted_jobs_survive_restart; test_validator_endpoint_report_shape; test_gate_A_refused_with_errors; test_out_lang_argv_order_and_validation; test_yt_exit_codes_mapped; test_images_no_kaliya_fallback_for_other_story; test_version_stale_flag; test_file_endpoint_redacts_logs; test_story_save_keeps_backup. All offline; no model call, no spend (use fake Colab CLI and fake validator outputs). |
| U2 front end JS | ui/static/pipeline.js, ui/static/app.js | Story select posts project (D2); scope header and scoped gate calls (D12, M12); languages checkboxes + All (a); next-step card + Continue (b); validator panel and Run validator (d); YouTube link box (e); Render panels and human-choice buttons (f, g); Export via scoped endpoint (D6, M17); ops panel and stale banner (h, D15); single poller with visibility (M10); focus-safe render and draft keys (M11); modal: focus Cancel first, one implementation (M16); 403 message fix (M9); job bar in wizard (M14); api() text-first (M22); stale copy removed (M13, M19); i) RUN_REPORT link | node --check both files; test_static.py extended by U3 (ES2018 for pipeline.js, every literal endpoint in the contract table); manual Browser check on the fixture server: two stories, approve A on one, other shows open; Continue jumps; language All sends ["en","hi","mr"]. |
| U3 design and static tests | ui/static/style.css, ui/static/index.html, ui/test_static.py | Visual pass (3j); index.html copy fixes (L1, L2, L4, L5, L6, M13, M19 copy, M21); phone log bar; focus rules (L7, L8, L9); extend test_static: pipeline.js endpoints in plan list, ES2018 for pipeline.js, every label has a control, no "Kaliya" literal outside legacy paths, gitignore check for stories/**/RUNS.jsonl, RUN_REPORT.md, story.json | pytest ui/test_static.py green; screenshot check at 375 px and 1280 px in the Browser pane (no page-level horizontal scroll, every control focusable). U3 finishes test_static last, after U2 merges, because it pins JS text. |

### 4a. Endpoint contract (U1 provides, U2 consumes; U2 may code against fixtures in the meantime)

| # | Method and path | Request | Response (main fields) | Status and notes |
|---|---|---|---|---|
| 1 | GET /api/version | - | {pid, started, server_mtime_at_start, server_mtime_now, stale, build} | new |
| 2 | GET /api/ops | - | {disk:{C,D:{free_gb}}, server:{...}, colab:{ledger_total_units, cap_units, runs[], sessions_listed}} | new |
| 3 | GET /api/status | - | existing fields + disk + build | extend |
| 4 | GET /api/pipeline?story=&pack= | optional query | {scope:{story,pack}, project, stages[], gates[], current, output_languages} | extend (default = project) |
| 5 | GET /api/pipeline/summary?story=&pack= | optional query | existing summary plus validator summary | extend |
| 6 | POST /api/pipeline/project | {story_slug, pack?, images_dir?, results_dir?, takes?} | {ok, project, scope} | exists; must be called on every switch |
| 7 | POST /api/pipeline/gate | {story, pack, gate, decision, note, confirm?} | gate state | changed: story and pack required; 409 on mismatch |
| 8 | GET /api/story | - | {slugs:[{slug, packs, latest_pack, output_languages, state}]} | extend |
| 9 | GET /api/story/<slug>/state | - | story_state.summarize(...) = {next_step:{stage, gate, label, pack}, warnings[], packs[], output_languages} | new (depends on director/story_state.py) |
| 10 | POST /api/story/<slug>/languages | {languages:[...]} | {output_languages} | new |
| 11 | GET/POST /api/story/<slug> | existing | existing | overwrite keeps backup (M2) |
| 12 | POST /api/story/<slug>/link | {url, lang, asr, overwrite} | {preview token, argv} then /api/run | new (command yt_transcript) |
| 13 | GET /api/jobs/<id>/result | - | yt_transcript: {status, candidates[], engine, chars, file} | extend |
| 14 | POST /api/preview (write_pack) | args + out_lang | argv with --out-lang | extend |
| 15 | GET /api/pack?pack=&check= | - | rows with route and editorial_duration_sec, bible normalised | extend (V4-aware) |
| 16 | POST /api/pack/validate | {pack} | Report {ok, errors[{code,where,message}], warnings[], stats, mode, exit} | new |
| 17 | GET /api/pack/validate?pack= | - | last Report or 404 | new |
| 18 | GET /api/render/status?story=&pack= | - | {images, asset_manifest, fallback[], step9, gate_d{languages[]}} | new |
| 19 | POST /api/render/choice | {story, pack, shot, choice, note} | {ok, recorded} | new |
| 20 | GET /api/images?adhyay=&story=&pack= | query | series, jobs, shots, finals for that story | extend (no Kaliya default for other stories) |
| 21 | GET /api/export?reel=&story=&pack= | query | clips of that pack only | extend (story and pack required) |
| 22 | POST /api/packet | {jobs, shots, story, pack} | {path, markdown} | extend |
| 23 | GET /api/colab | - | sessions, balance, ledger | extend |
| 24 | GET /api/file?path= | - | bytes; text redacted; ui/runs blocked | extend |

Error shape stays {"error": "..."}; 403 for guards, 409 for scope mismatch or busy, 400 for bad input.

### 4b. Blockers and dependencies (not UI work; need the owner of those files)

1. director/story_state.py and director/story_links.py do not exist yet. U1 codes against summarize(studio, slug) and summarize_all(studio) and a fake in tests. Features b and per-story links wait for them.
2. director/yt_transcript.py prints text only (NEEDS_CHOICE candidates, "written ..."). Add `--json` or one final line `RESULT {json}` before feature e.
3. director/run_registry.py: KINDS (L26-27) has no `validator`; update_story (L203) has no `output_languages` field. Add both (registry agent S1).
4. No pack-to-H3-story builder exists; render_controller (L70-74) needs episodes and registry.execution_profile. Feature f's Prepare button stays disabled until one exists.
5. No Step 9 runner writes a result file, and no Gate D assembly runner exists. Panels show "not run" until they do (fail closed).
6. No Colab spend ledger file yet (ops_checks.py missing). U1 can own runs/spend_ledger.jsonl if the ops agent agrees on the format.
7. writer_prompts.py:36 DEFAULT_OUT_LANG = "hi": the CLI default is Hindi only. The UI must send an explicit choice (decision 1 below).

## 5. WHAT THE OWNER MUST DECIDE

1. Languages: no default, the owner must tick at least one (recommended), or default to en? The writer CLI default is hi today.
2. Gate A: block approval while the validator has errors (recommended), or allow an owner override with a note?
3. Gate D: require Step 9 QC pass and per-language checks before approve (recommended)?
4. Spend: rolling cap (per run 15 units is there now; add a daily or total cap?) and must a stopped $ job be verified before any new spend (recommended yes)?
5. Public repo: remove the already-tracked stories/kaliya_mardan/SOURCE.md and milestone_leap/DIRECTION.md from the git index (git rm --cached) and check whether origin/main already has them. No push until you say push.
6. Render: hide "Prepare render" until an H3 story builder exists (recommended), or assign that builder now?
7. Kaliya: keep as a legacy project with its own roots, or move its paths into story_links?
8. Reel scope: confirm reel N = episode EP_0N in the H3 story file.
9. Where the Mahadev violence or rating level is stored (story.json field or pack field).
