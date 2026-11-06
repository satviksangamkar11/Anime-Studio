

# BATCH u1_server (dots) 11-07 03:05



## Findings

**1. Medium — server.py:1792‑1799 (Host/Origin guard gap)**  
The `_guard` method only checks the `Origin` header when it is present. A POST request that omits `Origin` (e.g., from a non‑browser client or a malicious local app) bypasses the origin check entirely. The only remaining protection is the `X‑UI: 1` header, which is a static, easily guessed value.  
**Failing input:** `curl -X POST -H "X-UI: 1" http://127.0.0.1:8765/api/run -d '{"token":"abc123"}'` (no `Origin` header) → 200 OK.  
**Fix:** Require a valid `Origin` header for all POST requests and reject the request if it is missing or not in the allowed set.

**2. Medium — server.py:1660‑1670 (Race condition in gate approval)**  
`pipeline_gate` calls `pl.apply_gate` without holding the server‑wide `api.lock`. Two concurrent POST requests to `/api/pipeline/gate` can read the same pipeline state, both write to `approvals.jsonl`, and return inconsistent results. The file append itself is atomic, but the read‑modify‑write cycle is not serialised.  
**Failing input:** Two browser tabs submit a gate decision at the same time; the second response may not reflect the first decision.  
**Fix:** Acquire `api.lock` (or a dedicated gate lock) for the whole `apply_gate` call.

**3. Low — server.py:1695‑1696 (Contract mismatch: `/api/author/status` ignores `story`)**  
The UI contract addendum specifies `GET /api/author/status?story=&pack=`, but the dispatch only passes `q.get("pack","")` to `api.author_status`. The `story` parameter is silently dropped.  
**Failing input:** `GET /api/author/status?story=my-story&pack=mypack` → server tries to find a pack named `mypack` (without the story folder) and returns 404.  
**Fix:** Accept and validate the `story` query parameter, or update the contract to remove it.

**4. Low — server.py:1438‑1450 (Author status does not cross‑check story/pack)**  
Even when the full pack path is supplied, `author_status` does not verify that the pack actually belongs to the given story. A UI that sends `story=foo` and `pack=stories/bar/baz` (where `bar ≠ foo`) will get a valid response for the wrong story.  
**Failing input:** `GET /api/author/status?story=foo&pack=stories/bar/baz` → returns the author status for `stories/bar/baz` even though the story is `foo`.  
**Fix:** In `author_status`, validate that the slug extracted from the pack path matches the `story` parameter (if supplied).

**5. Low — server.py:1521‑1531 (Hard‑coded paths in `results_roots` ignore root overrides)**  
For the legacy Kaliya story, `results_roots` appends `director/t0_pack/results` and `colab_batches` sub‑folders using `cfg.studio`. If the owner starts the server with `--root-override studio=...`, these paths are still resolved under the new studio root, which may not exist or may point to wrong data.  
**Failing input:** `--root-override studio=/tmp/fake` → `/api/export?reel=1&story=kaliya_mardan&pack=...` looks for clips in `/tmp/fake/director/t0_pack/results` instead of the real studio.  
**Fix:** Resolve these legacy paths relative to the original studio root (or the `--root-override` value if explicitly intended), and document the behaviour.

---

FINAL:
1. Medium – server.py:1792‑1799 – Origin header check is optional; POST without Origin bypasses CSRF protection.
2. Medium – server.py:1660‑1670 – `pipeline_gate` has no locking, allowing race conditions in gate approval.
3. Low – server.py:1695‑1696 – `GET /api/author/status` ignores the `story` query parameter, contradicting the contract.
4. Low – server.py:1438‑1450 – `author_status` does not verify that the pack belongs to the given story.
5. Low – server.py:1521‑1531 – `results_roots` hard‑codes legacy paths that ignore `--root-override studio`.


# BATCH u2_pipeline_js (dots) 11-07 03:15



## Reasoning summary

I audited `pipeline.js` against the two spec documents, checking: (a) route names and request/response field names vs the U1 contract addendum; (b) security (innerHTML/path traversal/CSRF/secrets); (c) button reachability and exitable states; (d) polling races; (e) accessibility/phone rules; (f) whether the JS adopts the U3-published element ids.

Two concrete route/field mismatches stand out as functional breakers: the `write_pack` preview omits `out_lang` (contract deviation 9 says it is required with no default), and `/api/images` is called with `?story=&pack=` while the contract specifies `?adhyay=&story=`. A polling race exists because `loadDetail` from a previous tick can resolve after `loadPipeline` clears state on a scope change, restoring the wrong story's validator/render/voice data. The JS also never adopts the U3-published element ids (`yt-*`, `bgm-enabled`, `job-bar*`, `render-*`, `runs-docs`, `stale-banner*`, `next-step-*`, `author-output`, …), so any static containers U3 placed in `index.html` inside `#wiz-panels` will be left empty while the wizard duplicates them. Several routes used by the JS (`/link`, `/languages`, `/render/choice`, `/pipeline/project`) are not in the contract's endpoint list — flagged as unverified rather than asserted defects. No `innerHTML`, no secrets in output, no Colab/ElevenLabs/model calls, no path-traversal construction in the JS; the author-run and spend paths are correctly gated.

---

### Findings

**1. HIGH — pipeline.js:1019** — `write_pack` args are `{ slug, pack, writer }`; the contract (U1 deviation 9) says `write_pack` needs `out_lang` (en/hi/mr, comma list or "all") with **no default**.
- Failing path: Save a story → tick languages → enter a pack name → click **Run story analysis** → POST `/api/preview` `{command:'write_pack', args:{slug, pack, writer}}` → server 400s because `out_lang` is missing → error bar shows, analysis never runs, Gate A never opens.
- Fix: add `out_lang: (State.storyState && State.storyState.output_languages || State.langPick).length ? (...).join(',') : 'all'` to the args, and require at least one language before the button proceeds.

**2. MEDIUM/HIGH — pipeline.js:1161** — `get('/api/images?story=' + enc(slug) + '&pack=' + enc(pack))`; contract deviation 14 specifies `GET /api/images?adhyay=&story=` (no `pack`).
- Failing path: story saved, Gate A approved, image jobs built → click **Make Flow agent packet** → the request omits `adhyay` and sends an undocumented `pack` → server rejects or returns the wrong job list → "Image jobs are not built yet" / packet fails.
- Fix: `get('/api/images?adhyay=' + enc(BUILD_ADHYAY) + '&story=' + enc(slug))` (align param names with the contract).

**3. MEDIUM — pipeline.js:289–342 vs 220–264** — race between in-flight `loadDetail` responses and scope changes.
- Failing path: a slow poll's `loadDetail` is still pending when the owner switches story (POST `/api/pipeline/project` → `loadPipeline` clears `State.storyState/validator/render/packInfo/voices` at lines 230–247). The stale response then resolves and overwrites those fields with the **previous** story/pack's data; `adoptPrefs` can also pin `State.prefsFor` to the old slug, so the UI briefly (or, in the worst ordering, until the next tick) shows the wrong validator, Gate D rows, voice map and author panel.
- Fix: attach a scope generation counter to each `loadDetail` call and ignore any response whose counter is older than the current scope.

**4. MEDIUM — pervasive (many lines)** — the JS does not adopt the U3-published element ids.
- Mismatch examples: `wizard-jobbar`/`jobBar()` text vs `job-bar`/`job-bar-text`/`job-bar-toggle`/`job-bar-log`/`job-bar-stop`; `link-url/link-lang/link-asr/link-overwrite/link-run/link-result` vs `yt-*`; `bgm-on` vs `bgm-enabled`; `asset-panel`, `choice-*`, `choice-note-*` vs `render-assets`/`render-choices`/`render-choice-note`; `runs-panel` vs `runs-docs`; `author-preview-out` vs `author-output`; `pipe-banner` vs `stale-banner`/`stale-banner-text`; `btn-continue`/`next-step-*`; missing `validator-chip/-stats/-errors/-repair`, `voice-status`, `lang-status`, `bgm-status`, `render-panel/-status`, `step9-status/-list`, `render-prepare-reason`, `gate-d-panel/-safezone/-bgm`, `author-missing/-cache-status`, `ops-disk/-server/-colab/-refresh`, `spend-badge`, `chip-story`.
- Impact: the contract says static containers live in `#wiz-panels` (a sibling of `#wizard`) and the wizard rebuild must not clear them; since the JS never fills those ids, U3's containers stay empty and the wizard duplicates their content. Verify `index.html` and adopt the U3 ids (or confirm none exist).
- Fix: rename/rebuild the panels to the published ids.

**5. LOW — pipeline.js:1206** — `findJobsFile` returns `'flow/' + names[i]` where `names[i]` is the raw `j.file` value; `genDir` at line 1232 is already `'flow/generated/' + slug + '/'`, so if `j.file` already begins with `flow/` the path sent to `/api/packet` is double-prefixed (`flow/flow/…`).
- Impact: packet request references a non-existent jobs file. (Which form `j.file` uses is unverified from the JS alone.)
- Fix: strip a leading `flow/` from `j.file` before prefixing, or return the path exactly as the server expects.

**6. LOW — pipeline.js:947, 774, 1463, 671 (unverified routes)** — the JS calls `/api/story/<slug>/link`, `/api/story/<slug>/languages`, `/api/render/choice`, and POST `/api/pipeline/project`, none of which appear in the contract's endpoint list (line 23 / deviations). They may exist, but if not these calls 404. `/api/pipeline/project` is the core navigation mechanism, so confirm it on the server before final wiring.

**7. LOW — pipeline.js:1417** — `h3_prepare` args send `story: packPath(slug,pack) + '/shots.json'` and no reel/episode; contract deviation 11 says the story must be an H3 story file (episodes + registry) and reel N is sent as `EP_0N`. (The button is disabled until `prepare_ready`, so it may be unreachable until `convert_pack` is ready — verify the arg shape when it becomes reachable.)

**8. LOW — pipeline.js:1006, 1154, 863, 796, 820, 1560** — several action handlers (`analysis-run`, `images-packet`, `voice-map-save`, `voice-save`, `bgm-save`, `export-show`) do not check `State.busy` at entry, so a rapid double-click can fire the command twice. (Gate/continue/link/build handlers do check it.) Fix: add `if (State.busy) { showError('Busy, try again'); return; }` at the top of each.

---

FINAL:

1. **HIGH — pipeline.js:1019** — `write_pack` preview omits the required `out_lang` param; **Run story analysis** always fails and Gate A never opens. Fix: send `out_lang` from the saved/selected languages.
2. **MEDIUM/HIGH — pipeline.js:1161** — `/api/images` is called `?story=&pack=` but the contract is `?adhyay=&story=`; the Flow packet feature breaks. Fix: pass `adhyay`, drop `pack`.
3. **MEDIUM — pipeline.js:289–342 vs 220–264** — stale in-flight `loadDetail` responses overwrite state after a scope change, showing the wrong validator/render/voice-map and pinning `prefsFor` to the old slug. Fix: scope-tag `loadDetail` and discard stale responses.
4. **MEDIUM — pervasive** — U3-published element ids (`yt-*`, `bgm-enabled`, `job-bar*`, `render-*`, `runs-docs`, `stale-banner*`, `next-step-*`, `author-output`, …) are not adopted; U3's static containers in `#wiz-panels` are left empty and the wizard duplicates them. Fix: adopt the published ids.
5. **LOW — pipeline.js:1206** — `findJobsFile` prepends `'flow/'` to a path that may already contain it, double-prefixing the jobs path sent to `/api/packet`. (Unverified which form `j.file` uses.)


# BATCH u3_app_html_css (dots) 11-07 03:26



## Analysis

I reviewed `app.js`, `index.html`, and `style.css` against the spec and contract. Security posture is solid (no `innerHTML`, all server data goes through `textContent`/`createElement`, `encodeURIComponent` on all URL params, `rel=noopener` on external links). The main defects are dead/unupdated UI elements and one contract mismatch.

---

### Findings

**1. medium — `app.js:291-305` (renderHeader)**
`renderHeader()` updates `spend-badge`, `job-badge`, and `story-status` but never touches `project-name`, `chip-pack`, or `chip-languages`. Those header chips are static in `index.html` and permanently show "(no story chosen)", "Pack: none", and "Languages: none ticked" regardless of actual project state.
**Fix:** Add `$('project-name').textContent = …`, `$('chip-pack').textContent = …`, and `$('chip-pack').textContent = …` updates in `renderHeader()` (or wherever the active story/pack/languages are known).

**2. medium — `index.html:71-79` (job-bar)**
The entire `#job-bar` block (`job-bar-text`, `job-bar-toggle`, `job-bar-stop`, `job-bar-log`) is never referenced by `app.js`. It is dead UI — no JS reads or writes those IDs. The actual job tracking happens in the header `#job-badge` and the footer `#log-tail`.
**Fix:** Either wire the job bar into `renderHeader()`/`onStarted()`/`pollJobs()` or remove the dead markup from `index.html`.

**3. medium — `index.html:34-67` (stepper)**
The wizard stepper (`#stepper`, `#step-story` … `#step-export`) is static HTML. Every `<li>` permanently has `class="status-locked"` and shows "Locked". No JS (app.js or otherwise) updates the step statuses. The stepper is decorative only.
**Fix:** Have `pipeline.js` (or app.js) update `step-*` classes/text based on actual pipeline state, or remove the static stepper if the sidebar nav is the real control.

**4. medium — `app.js:1323` (loadExport)**
`loadExport()` builds the URL as `/api/export?reel=…&story=…&pack=…`. The documented contract (line 32) specifies only `GET /api/export?reel=N`. The extra `story` and `pack` params are not in the contract — the server may reject or ignore them, breaking export.
**Fix:** Confirm the server accepts `story`/`pack` params; if not, remove them or update the contract comment.

**5. low — `app.js:501` (showStage)**
`var want = needsTyped ? (pv.confirm_text || ('EXECUTE ' + pv.estimate)) : '';` — if the server omits both `confirm_text` and `estimate`, `want` becomes the string `"EXECUTE undefined"`. The user must type that literally to proceed.
**Fix:** Guard: `var want = needsTyped ? (pv.confirm_text || ('EXECUTE ' + (pv.estimate == null ? '?' : pv.estimate))) : '';`

**6. low — `app.js:68` (PAT.edit)**
`/^[0-9a-f-]{36}$/` accepts any 36-character string of hex digits and dashes (e.g. `------------------------------------`), not just valid UUIDs.
**Fix:** Tighten to `/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/`.

**7. low — `app.js:72` (PAT.json)**
`/^[^\r\n\u0000-\u001f"]{1,260}\.json$/i` allows `/` and `.`, so values like `../../etc/passwd.json` pass client-side validation. The server must still sanitize; the client regex gives a false sense of safety.
**Fix:** Add `[^/\\]` to the character class or reject paths containing `..`.

**8. low — `app.js:1321` (loadExport)**
`loadExport()` calls `window.StudioWizard.project()`. `StudioWizard` is not defined anywhere in `app.js` or `index.html`. If `pipeline.js` doesn't define it, `loadExport()` fails with the misleading error "Pick a story and run its analysis first; export works per pack."
**Fix:** Define a fallback or move the project-pointer logic into app.js; don't rely on an unverified global.

**9. low — `app.js:1295-1301` (stopSession)**
`stopSession()` sends `colab_stop` without checking `S.jobBusy`. If a job is running, stopping the Colab session mid-run may leave the local process in an inconsistent state.
**Fix:** Add a `data-gate="busy job"` check or confirm before stopping a session during an active job.

---

FINAL:
1. medium — Header chips (project-name, chip-pack, chip-languages) never updated by renderHeader(); permanently show stale defaults.
2. medium — #job-bar block (job-bar-text/toggle/stop/log) is dead UI, never referenced by app.js.
3. medium — Stepper (#stepper) is static HTML, all steps permanently "Locked", never reflects pipeline state.
4. medium — loadExport() sends &story=&pack= to /api/export, but the documented contract only specifies ?reel=N.
5. low — showStage() can produce "EXECUTE undefined" as typed-confirm text if server omits both confirm_text and estimate.
6. low — PAT.edit accepts any 36-char hex/dash string, not just valid UUIDs.
7. low — PAT.json allows / and . characters, enabling path traversal if the server doesn't sanitize.
8. low — loadExport() depends on window.StudioWizard.project(), an unverified global not defined in app.js.
9. low — stopSession() doesn't check S.jobBusy before stopping a Colab session during an active job.
