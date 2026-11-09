

# BATCH f1_backend (dots) 11-07 21:02



**Findings**

1. **High** — `server.py:1005-1009` (`Api._persist`)  
   **What:** The `_persist` method writes the job record file without holding the lock, so `_wait` (after releasing the lock) and `job_stop` (never takes the lock) can write to the same file concurrently.  
   **Failure:** Two threads writing `runs/jobs/<id>.json` at once can interleave bytes and corrupt the file; on restart the job table is unreadable or missing a job.  
   **Fix:** Wrap the whole body of `_persist` in `with self.lock:` (the lock is an `RLock`, so re‑entering from `_start` is safe).

2. **High** — `server.py:1095-1107` (`Api._verify_stop`)  
   **What:** `_verify_stop` changes `job.state`, `job.verified` and `job.warning` without acquiring `self.lock`. It is called from `_wait` (before the lock is taken) and from `job_stop` (no lock at all).  
   **Failure:** A race with `_wait`’s later locked update can leave the job in an inconsistent state (e.g., `state` overwritten or `verified` lost), which may cause the spend gate to think a session is still active or a stop is unverified.  
   **Fix:** Acquire `self.lock` at the start of `_verify_stop` (again safe because `RLock` is reentrant).

3. **Medium** — `server.py:443` (`scope_ids`, reel branch)  
   **What:** `picked = [s["id"] for s in shots if s.get("episode") == reel]` compares the shot’s `episode` field (which may be a string) with the integer `reel`.  
   **Failure:** If the shot file stores episodes as strings (e.g. `"1"`), the comparison fails and `scope_ids` raises `"no shots in reel N"` even though the reel exists, breaking the *run_kaggle_prepare* wizard step for a valid reel.  
   **Fix:** Compare string forms — `str(s.get("episode")) == str(reel)` (the `export` endpoint already does this correctly).

4. **Medium** — `server.py:1122, 1130` (`Api.status` and `Api.writers`)  
   **What:** `(c.studio.parent / "secrets" / "nvidia").glob("nvidia_api_key*.txt")` is called without checking whether the directory exists.  
   **Failure:** If the `secrets/nvidia` folder is missing, `Path.glob` raises `OSError` and the normal `/api/status` or `/api/writers` GET returns HTTP 500 instead of a clean error.  
   **Fix:** Guard with `if (dir).is_dir():` before the glob, or use `try/except OSError`.

5. **Low** — `server.py:1306-1313` (`Api.run` digest check)  
   **What:** When `command_spec` raises an `ApiError`, the except block sets `argv = None` but `spec` remains undefined; later `spec.id` is referenced (though short‑circuiting avoids a `NameError`). The error message “arguments changed since the preview” is also misleading when the real problem is an invalid command name.  
   **Failure:** A client that sends an unknown command gets a confusing 403 “arguments changed” instead of “unknown command”.  
   **Fix:** Initialise `spec = None` before the `try`, and if `spec is None` raise a clear `ApiError(400, “unknown command”)`.

6. **Low** — `server.py:581` (`b_h3` command build)  
   **What:** The `h3.render_controller` invocation passes shot‑ids / episode‑names as bare positional arguments (`*tail`) instead of using a named flag such as `--ids`.  
   **Failure:** *Possible* contract mismatch — the H3 engine may expect `--ids` (or `--episodes`) and will fail to parse the positional arguments, causing the *H3 prepare* step to error on a normal action.  
   **Fix:** Verify the CLI of `h3.render_controller`; if it requires flags, add them (e.g. `--ids` for shots, `--episodes` for reel).

7. **Low** — `server.py:210` (`safe_path` case sensitivity)  
   **What:** On Windows, `Path.is_relative_to` is case‑sensitive, but Windows paths are case‑insensitive. A path with different casing could pass the check yet actually point outside the root.  
   **Failure:** A crafted path like `STUDIO\..\..\SECRET\file` might be allowed if the casing tricks the string comparison.  
   **Fix:** Compare lower‑cased real paths on Windows, or use `os.path.commonpath`.

**FINAL count by severity:**
- High: 2
- Medium: 2
- Low: 3


# BATCH f2_wizard_js (dots) 11-07 21:31



## Analysis

I read `pipeline.js` (2579+ lines, tail truncated at the `showError` definition), `index.html`, and the constants. I could **not** read `app.js`, `i18n.js`, `theme.js`, `tokens.css`, `style.css`, or the server, so those areas are marked "possible".

### Concrete defects

**1. medium — pipeline.js:684 — `loadStory` race guard is inverted/ineffective**
The guard `if (State.storySlug !== State.lastStorySlug)` can never be false at that point: `lastStorySlug` is only ever updated *inside* this block, and the function already returned early when they were equal. So the guard never discards a stale response. If the story switches twice inside one request window, the first response overwrites `State.storyText`/`lastStorySlug` with the wrong story's text.
Fix: capture `var want = State.storySlug;` before the fetch and test `if (State.storySlug === want)`.

**2. medium (possible) — pipeline.js:792, 1250, 1265 — contract mismatch on `/api/story` shape**
`loadStoryList` does `State.storyList = data.slugs || []`, but every consumer treats items as objects (`s.slug`, `s.latest_pack`, row filter `s.slug === slug`). If the server returns an array of plain slug strings (the field name `slugs` suggests that), the picker options get `value=undefined`, labels read `undefined: ...`, and "Open this story" always sends `pack: ''`.
Fix: confirm the server shape; if it returns strings, map them to `{slug, latest_pack}` client-side (or change the field name).

**3. medium (possible) — pipeline.js:824, 777, 799, 839, 855 — loaders with no caller inside pipeline.js**
`loadWriters`, `loadSummary`, `loadStatus`, `loadRegistry`, `loadRegistryDetail` are defined but never invoked anywhere in `pipeline.js` (only `loadStoryList` is called, from the Save button, and `loadOps`, from the banner button). `refreshWizard` only runs `loadPipeline` + `loadDetail`. If `app.js`/the poll doesn't call these on init+poll, step 2's writer chooser shows "Loading…" forever, the step-4 summary shows "None", the job bar and the runs panel stay empty.
Fix: verify `app.js` wires the poll/init; if not, call them from the poll.

**4. low — pipeline.js:1662, 1683 — analysis "Run" button is enabled when the stage isn't ready**
`readyToRun` (computed from `stage.status`) only affects the button *class*, not `disabled`. When the analysis stage is `done`/`approved`/`running`, the button stays clickable and clicking it raises `plan.err_not_ready` — an error on a normal action.
Fix: add `&& readyToRun` to `canRun` (or disable).

**5. low (possible) — index.html:70-116 / pipeline.js:1048 — stepper step buttons have no click handler**
`step-btn-story` … `step-btn-export` are `<button>` elements but `updateStepper` only mutates classes; no `click` listener is attached in `pipeline.js`. Tapping a step does nothing unless `app.js` binds them.
Fix: confirm `app.js`; if unbound, attach `openStep(stage.id)`.

**6. low (possible) — pipeline.js:1600 — writer chooser may never load**
Same as #3; if `loadWriters` is never called, step 2 shows a perpetual "Loading writers" box and the run button is permanently disabled.

**7. low (possible) — index.html:42, 49, 48 — `#spend-badge`, `#server-state`, `#job-badge` are never written by pipeline.js**
`spend-badge` ("Paid work: OFF") and the server/job badges have no updater in the wizard code. If `app.js` doesn't refresh them, the spend badge is stale even while a paid/Colab job runs.
Fix: verify `app.js` updates them from `/api/status` and the spend state.

**8. low (possible) — tokens.css vs style.css — undefined tokens**
`style.css` is loaded after `tokens.css` and the page uses `data-theme`. Without `tokens.css` I can't confirm every `var(--*)` used by `style.css` is defined; an undefined token silently falls back (hard-coded-looking colours, broken contrast).
Fix: grep `style.css` for `var(--*)` and confirm each exists in `tokens.css` for every theme.

**9. low (possible) — i18n coverage**
`LANGS = ['en','hi','mr']` (pipeline.js:12) means Hindi output is supported, but the UI language switch (index.html:30-31) only offers English/Marathi; `langName('hi')` and any `t('story.lang_hi')` depend on keys that may be absent. Also `t('scope.plan', { pack: ... })` nests a `t()` call as a substitution value, which some simple implementations don't support.
Fix: open the `i18n/*.json` files and confirm keys for `hi`, and that `t()` resolves nested calls.

**10. low (possible) — pipeline.js:855 — `loadRegistryDetail` loads but nothing renders it**
`State.registryDetail` is fetched and stored, but I find no render consumer in `pipeline.js`; the expert "Story text" panel (`#sec-story`) is presumably driven by `app.js`.
Fix: confirm `app.js` renders `State.registryDetail`; otherwise the detail call is dead.

**11. low (possible) — pipeline.js:1729 — Claude typed-word fallback**
`typed: data.confirm_text || 'CLAUDE'` falls back to the literal `'CLAUDE'`, and the dialog compares `value.trim().toUpperCase() !== o.typed`. If the server ever returns a lowercase or different `confirm_text`, the comparison can never match and the Yes button stays disabled forever.
Fix: normalise `o.typed` to uppercase at comparison time, or have the server always return `'CLAUDE'`.

**12. low (possible) — pipeline.js:1921 — `findJobsFile` prepends `'flow/'` to a server path**
The returned `jobsFile` is `'flow/' + names[i]` where `names[i]` is already a `j.file` that contains `generated/<slug>/`. Whether `/api/packet` expects the `flow/` prefix is unverifiable without the server.
Fix: confirm the expected path format on `/api/packet`.

**13. low — pipeline.js:1260-1262 — "Open this story" errors when the user picks the "new story" option**
The button reads only `slugSelect.value`; selecting the empty "New story" option and clicking shows `story.err_new_hint` even though the user may have typed a slug into `wiz-story-new-slug`, which the button ignores. New stories are created via Save, so this is by design, but the error is misleading.
Fix: if `slug` is empty, point the hint at the new-slug field or hide the button.

**14. low (possible) — pipeline.js:2576+ (truncated) — `showError`/`showSuccess`/`showApiError` bodies unseen**
The file is cut off inside `showError`. I cannot verify the error-bar auto-hide/keep logic (`SUCCESS_MS`, `State.errorTimer`), whether `showApiError` double-reports 404s, or whether raw error text is safely placed (it uses `textContent`, so XSS is unlikely).
Fix: read the tail of `pipeline.js` and confirm errors stay until closed and success auto-hides per B10.

### Things I deliberately did NOT report
- Style/wording preferences, missing features, or anything I could not verify.
- The `/api/story/<slug>/state` field names (used consistently in JS; server contract unverifiable).
- `app.js` behaviour in general — it is not provided.

FINAL:
- high: 0
- medium: 3
- low: 11
