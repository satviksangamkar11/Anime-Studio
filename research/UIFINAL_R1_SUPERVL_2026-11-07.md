

# BATCH f1_backend (supervl) 11-07 21:02

FINAL:
high: 4
medium: 6
low: 1

High, server.py:1332-1338, The spend ledger row is written before the job process is started, so a Popen failure charges units but creates no job. Input: start a $ command (e.g. colab_run) when C:\Python314\python.exe is missing or unlaunchable. Wrong result: runs/colab_spend.jsonl gains a row for est units, _start raises, no job_id is returned, and the preview token stays unused while the ledger says the spend happened. Fix: move record_spend to after a successful self._start(...) (or delete/compensate the ledger row on Popen failure), then set rec["used"] = True.

High, server.py:763, read_pack returns the raw gate1 slice of PACK.md without redaction. Input: a PACK.md containing an API key or token. Wrong result: GET /api/pack?pack=stories/slug/pack leaks the secret in the gate1 field. Fix: redact gate1 with redact() before placing it in the returned dict.

High, server.py:1204, story_get returns the raw SOURCE.md bytes decoded without redaction. Input: SOURCE.md containing secrets. Wrong result: GET /api/story/<slug> leaks secrets in the text field. Fix: return redact(text) instead of the raw decode.

High, server.py:1293, preview returns the raw argv list unredacted. Input: any command preview whose arguments contain user text (e.g. a secret in queue_add note) or sensitive paths. Wrong result: POST /api/preview exposes command-line arguments including user-supplied secrets to the UI caller. Fix: redact the argv list before sending (return redact_obj on the response, matching _persist).

Medium, server.py:1284, preview returns balance as the string "not checked (spend is OFF)" when spend is disabled. Input: server started without --allow-spend; preview a spend command. Wrong result: balance is a string, so JS that compares it numerically (e.g. balance >= estimate) gets NaN or unexpected behavior. Fix: return null for balance when spend is OFF and let the UI key off spend_allowed.

Medium, pipeline.py:505-518, The Images stage can enter the Gate-B approval branch when shots_ready is false because expected_images is 0. Input: a pack with leftover final/*.png files but missing/incomplete shots.json. Wrong result: Images shows "waiting for Gate B" or "approved" although shots are not ready. Fix: guard the completion branch with f["shots_ready"] and f["expected_images"] > 0 (or treat expected_images == 0 as not ready).

Medium, pipeline.py:588-592, current never advances past "story" when every stage is approved/done. Input: all gates approved and all stages complete. Wrong result: pipeline_state / /api/pipeline reports current: "story" instead of "export" or "complete". Fix: after the loop, if no stage matched, set current to the last stage id ("export") or "complete".

Medium, server.py:1378-1379, job_stop calls _verify_stop on a finished non-live spend job, which can overwrite its terminal state to "stop_failed". Input: a completed colab_run job whose Colab session is still listed (or the session check fails). Wrong result: job.state becomes "stop_failed" even though the job itself finished successfully (rc == 0). Fix: only run _verify_stop / overwrite state for jobs that are not already in a terminal state, or preserve done/failed when rc is known.

Medium, pipeline.py:858, _per_language filters Gate D reasons with f" {lang}: " requiring a leading space. Input: gate_d reasons formatted as "en: missing audio" (no leading space). Wrong result: the language audio-plan check incorrectly reports ok: true because the reason is not matched for that language. Fix: match the language prefix without requiring a leading space (e.g. r.startswith(lang + ":")).

Medium, server.py:707, parse_sessions skips any session whose first whitespace token is NAME, SESSION, SESSIONS, or ID (case-insensitive). Input: a Colab session literally named Name, ID, or SESSIONS. Wrong result: that session is omitted from /api/colab and /api/ops session listings. Fix: skip only the header line (e.g. the first line) rather than any token matching those words.

Low, pipeline.py:724-725, summary rounds minutes before computing g4_units, while server.estimate_units computes units directly and rounds once. Input: large clip counts where intermediate rounding changes the result. Wrong result: the summary estimate disagrees with the preview/estimate for the same batch by up to 0.1 units. Fix: compute units the same way as estimate_units (rate * minutes / 60, rounded once).

Possible: server.py:1318 requires confirm to exactly match rec["confirm"], which for spend is "EXECUTE {est:.1f}"; if the JS sends a differently formatted float (e.g. "EXECUTE 12" vs "EXECUTE 12.0"), a normal execute is rejected. Check app.js/pipeline.js to confirm they send confirm_text verbatim.


# BATCH f2_wizard_js (supervl) 11-07 21:11

medium — pipeline.js:1544-1567
Why: The analysis "Run" button uses `disabled: !canRun`, but `canRun` ignores `readyToRun` (stage must be ready/rejected); `readyToRun` only changes the button class, so the button stays enabled in non-ready stages.
Failure: Analysis stage is running/locked/approved, a free writer is available, Claude ack is set, and the UI is not busy → the enabled Run button is clicked → `showError(t('plan.err_not_ready'))`, an error on a normal action.
Fix: `var canRun = !!(opt && opt.available) && !needAck && !State.busy && readyToRun;`

medium — pipeline.js:2605-2618
Why: `tick()` launches loadStatus/loadSummary/loadRegistry/loadStoryList/loadOps/loadWriters/refreshWizard with no in-flight guard, and user actions do not pause polling.
Failure: A user saves/switches story or runs a gate while a slower tick is in flight; the tick's last response overwrites `State.pipeline`/`State.storyState`/storyList with older values, reverting the UI.
Fix: Add a poll generation/AbortController guard so only the latest tick's writes apply, and suspend polls while `State.busy`/a user action is in flight.

possible, medium — index.html:67-114; pipeline.js (no listener)
Why: The stepper step buttons (`step-btn-story` … `step-btn-export`) are `<button>` elements but pipeline.js attaches no click handler to them; only in-card `open-step-*` buttons call `openStep`.
Failure: Clicking a step in the stepper (e.g. "Pictures") does nothing; the owner cannot jump to that step via the stepper.
Fix: Verify app.js wires `step-btn-*`; if not, add click handlers calling `openStep(stage.id)`.

possible, medium — pipeline.js:660 (and 1091-1093)
Why: The UI reads `output_languages`, `next_step.{stage,key,pack}`, `warnings`, `voice_engine`, and `bgm` from `/api/story/<slug>/state`, but the server code is not provided to confirm these fields exist.
Failure: If `/api/story/<slug>/state` omits `output_languages`, `savedLangs()` is always empty, so the story step never offers the "next" action and is stuck on "save languages".
Fix: Confirm `/api/story/<slug>/state` returns `output_languages` and `next_step` (else adjust the JS to match the server).

possible, low — pipeline.js:660-710
Why: `/api/pack`, `/api/pack/validate`, `/api/author/status`, and `/api/pack/voices` are called with `packPath(slug,pack)` (`stories/slug/pack`), while `/api/render/status` and `/api/images` are called with bare `project.pack`.
Failure: If the server expects one pack format for all endpoints, the mixed calls return 404/empty data (pack, render, author, voices, images panels show missing data).
Fix: Verify each endpoint's expected `pack` identifier and make all calls use the same format.

possible, low — index.html:42
Why: `#spend-badge` uses `class="badge b-grey"`, but `b-grey` is not in `RUN_BADGE` and tokens.css/style.css are not provided, so the token may be undefined.
Failure: The spend badge renders with no defined badge styling (contrast/appearance broken).
Fix: Verify `.b-grey` is defined in tokens.css/style.css, or switch to a defined badge token.

possible, low — pipeline.js:2482
Why: `runBadge` falls back to `b-notrun` for the 'no runs' status, and `b-notrun` is not in `RUN_BADGE`; CSS is not provided.
Failure: A run with status 'no runs' gets an undefined badge class (no styling).
Fix: Verify `.b-notrun` is defined in CSS or add it to `RUN_BADGE`/CSS.

possible, high — index.html:345
Why: `#colab-run` is a paid Colab GPU action, but the visible markup has no tick/typed-word gate, and app.js (not provided) must enforce the owner rule that no paid run starts without a tick and the typed word.
Failure: If app.js does not gate it, clicking "Start a paid GPU session" spends Colab units without the required ack/typed-word confirmation.
Fix: Verify app.js requires an ack plus typed confirmation before `colab-run`; otherwise add the same gate used for Claude.

FINAL:
high=1 medium=4 low=3


# BATCH f3_expert_theme (supervl) 11-07 21:22

high — app.js:1432 — colab_run is a paid command (risk "$") but its runCommand config has no `check` checkbox, so doPreview never enforces the owner-required tick; only the typed confirm word is required.
Input -> wrong result: user opens the Colab run preview, types the confirm word, and starts a paid colab_run without ticking the required confirmation box.
Fix: add a `check` label to the colabRun runCommand options (e.g. `check: t('adv.colab.confirm_run')`) so doPreview requires the checkbox; verify the i18n key exists in en/mr.

high — app.js:1527 — choosing a story POSTs to /api/pipeline/project, which is not in the documented server contract.
Input -> wrong result: changing the story picker (a normal action) can trigger showApiError if the server lacks POST /api/pipeline/project, violating "the wizard must never show an error for a normal action."
Fix: implement POST /api/pipeline/project in server.py, or remove the POST call and keep only selectSlug() plus StudioWizard.refresh(). (possible: confirm server.py implements the route.)

medium — app.js:1482 — loadExport requests GET /api/export?reel=N&story=&pack=, sending story and pack query parameters that are not in the /api/export contract.
Input -> wrong result: if the server rejects unknown query parameters, clicking export-load returns a 400/error for a normal action.
Fix: request /api/export?reel=N only, or confirm server.py accepts story and pack on /api/export. (possible)

medium — app.js:461/468 — openModal shows the command-preview modal without moving focus into it, and closeModal does not restore focus to the opening element.
Input -> wrong result: a keyboard/screen-reader user opens a preview and focus stays on the trigger behind the backdrop, so Tab can escape the modal.
Fix: in openModal store document.activeElement, give #modal tabindex="-1" and focus it; in closeModal restore focus to the stored element.

medium — app.js:404 — pollJobs keeps a tracker in S.trackers whenever the job is absent from /api/jobs (`!j`), so onEnd never runs for that job.
Input -> wrong result: a job that finishes and leaves the jobs list before being polled never triggers its onEnd refresh (e.g. loadImages after review_shot), leaving the UI stale.
Fix: treat a missing job as finished (invoke onEnd with a not-found marker and drop the tracker) or stop re-tracking after several polls. (possible: confirm /api/jobs retains finished jobs.)

low — app.js:1431 — `var cap = (S.status && S.status.spend_cap_units) || 15;` coerces a server spend_cap_units of 0 to 15 because 0 is falsy.
Input -> wrong result: server spend_cap_units = 0 is displayed and summarized as cap 15.
Fix: `var cap = (S.status && typeof S.status.spend_cap_units === 'number') ? S.status.spend_cap_units : 15;`

low — app.js:1314 — scopeArgs validates the reel input with t('adv.export.reel_bad'), an export-section key used for video/h3 reel validation.
Input -> wrong result: the reel-validation message may be export-phrased or wrong in context, visible in Marathi mode if keys diverge.
Fix: use a shared/video-specific i18n key for the reel validation and verify the key exists. (possible)

low — app.js:259 — fmtBytes appends hard-coded English units "B", "KB", "MB" without going through t().
Input -> wrong result: byte sizes are shown in English units even in Marathi mode.
Fix: translate the unit suffix via t() (or confirm units are intentionally English). (possible)

low — app.js:343 — the spend badge uses t('app.spend_off'), a key not confirmed in the i18n tables.
Input -> wrong result: if "app.spend_off" is missing, the badge shows "[app.spend_off]" instead of a label.
Fix: verify "app.spend_off" exists in i18n/en.json and i18n/mr.json or add it. (possible)

low — tokens.css:84/123 — the dark default --control-border (#808C86 on --app-bg #181B1A) is below the stated 3:1 control-border target; the prefers-contrast: more block already substitutes #A7B1AA, implying the default is weak.
Input -> wrong result: dark-mode control borders can fail the 3:1 contrast requirement.
Fix: set the dark default --control-border to the stronger #A7B1AA (matching prefers-contrast: more) or verify contrast with a tool. (possible: verify contrast)

FINAL:
high: 2, medium: 3, low: 5


# BATCH f4_contract (supervl) 11-07 21:26

FINAL:
high=2, medium=2, low=0

high — pipeline.js:962, 1032–1039, 1396, 1417–1418, 1491, 1669–1675, 2193, 2258, 2288, 2356 — `render()` wipes and rebuilds the wizard DOM (line 962) on every poll/refresh, but `captureDraft()` (1032–1039) is never attached to any element, so `State.drafts` stays empty and `draftOr()` always returns the fallback; every unbound input loses its typed value on the next render. Input → wrong result: owner types a custom pack name (`analysis-pack`, 1669) or a YouTube URL (`link-url`, 1491), toggles a language or a poll fires, and the input reverts to the suggested/empty value, so Run/Save submits stale or empty data. Fix: attach `captureDraft` to the wizard via `input`/`change` event delegation (or bind each unbound input to `State`) so typed values survive re-renders.

high — server.py:572–581; pipeline.js:2134 — `h3_prepare` is built by `b_h3`, which requires the story JSON to contain `episodes` and `registry` and explicitly rejects `shots.json`, yet the wizard's Prepare button calls `h3_prepare` with `shots.json` (pipeline.js:2134) and no substitute story file. Input → wrong result: when `render_status.prepare_ready` is true, clicking Prepare (a normal action) returns 400 "shots.json is not accepted here" instead of preparing. Fix: have the UI pass the H3 story file (with `episodes`/`registry`) to `h3_prepare`, or make `b_h3` accept `shots.json`.

medium — server.py:1554; pipeline.js:2259 — `author_status` hardcodes `"run_allowed": False` (server.py:1554), and the wizard enables `author-run` only when `a.run_allowed` (pipeline.js:2259, `disabled: !allowed`). Input → wrong result: even after typing the correct author phrase, `author-run` can never be enabled, so the author command can never be launched from the UI. Fix: compute the real `run_allowed` on the server, or hide/remove the button until live author runs are wired.

medium — server.py:756–810, 1262–1266 — `read_pack` (served by `GET /api/pack`) returns raw `PACK.md` text (`gate1`) and shot `purpose` fields without `redact`/`redact_obj`, unlike the registry and job endpoints. Input → wrong result: a secret-like string in a story's `PACK.md` or shot purpose is returned in plaintext by `/api/pack` and displayed by the wizard in `packDetails`/`plan-check-json`. Fix: apply `redact_obj` to the result of `read_pack`/`api.pack` before sending it to the client.

Note: `app.js`, `index.html`, `tokens.css`, `style.css`, and the i18n JSON files were not included, so theme, language, and accessibility defects in those files could not be reviewed.
