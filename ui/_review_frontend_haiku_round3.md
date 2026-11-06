# Round 3 front-end review: Anime Studio wizard (2026-11-06, read-only)

Scope: static/index.html, style.css, pipeline.js, app.js (ids), server.py routes, pipeline.py. Checked against CHECKLIST_REDESIGN.md (API contract + 2026-11-06 additions) and round 2 (N1-N12).
Evidence: `ui` pytest 150 passed. GET probes on 127.0.0.1:8765. Browser pane DOM checks only (no POST). Layout at 375 px measured in the pane.

## Round-2 status
- N1 FIXED: project.json written by story save and /api/pipeline/project (server.py:891, 922; pipeline.js:486).
- N2 PARTIAL: picker reads `slugs` now, but is empty on load (H2).
- N3 PARTIAL: typed text survives while a story is saved (storyDirty); new-story case regressed (M2).
- N4 FIXED: api()/get()/post() return promises (pipeline.js:104-127).
- N5 FIXED: render() no longer skips a changed state (pipeline.js:218-231).
- N6 PARTIAL: Gate A data loads and draws (pipeline.js:195-201, 564-651; server.py:595, 620-622); Approve still disabled (H1).
- N7 PARTIAL: pack path fixed (pipeline.js:674); jobs path still wrong (H3).
- N8 FIXED: #modal is outside <details> (index.html:318); .dialog styled (style.css:513).
- N9 PARTIAL: a rejected gate can be decided again (pipeline.py:466-468); stage stays "rejected" (M1).
- N10 NOT FIXED (H4).
- N11 FIXED: episode rows carry `n` (pipeline.py:540; pipeline.js:789).
- N12 PARTIAL: story path fixed (pipeline.js:888); `ids: ''` still sent (H5).
- Round-2 MED: reject note printable FIXED (pipeline.py:478); story byte limit FIXED (pipeline.js:96); sticky error bar FIXED (style.css:52-55); success message FIXED (pipeline.js:1164); null episode FIXED, null seconds NOT (M6); new-slug/overwrite kept NOT (M3); server-side preview gate NOT (L9).
- Round-2 LOW: "Gate A (Gate A)" NOT (L1); Clips planned FIXED; stepper flex FIXED (style.css:78-99); restoreDrafts FIXED; .gate.locked FIXED (style.css:231); blank wizard on failure NOT (L7); tile contrast FIXED (style.css:317-321); progress-text contrast NOT (M7).

## Contract checks
- Paths, bodies, X-UI on every POST (api() pipeline.js:104-113; server.py:1231): OK.
- Field names: `slugs` OK; episode `n` OK; /api/images `jobs` WRONG (H3); h3 `ids` WRONG (H5).
- textContent only: no innerHTML, insertAdjacentHTML, eval or document.write in static/ (grep): OK.
- Gate C typed START on both sides (pipeline.js:1003-1005; pipeline.py:481-483): OK.
- app.js: every `$('id')` it uses exists in index.html (scripted check): OK. Advanced tools reachable (details closed by default, index.html:66): OK.

## HIGH
H1 pipeline.js:1000 (root cause pipeline.js:76). `disabled: false` goes through el(), which calls setAttribute('disabled', false). That disables the button. Confirmed in the pane: `setAttribute('disabled', false)` gives `.disabled === true`. Approve is dead on Gates A, B and D. On Gate C it is dead whenever START is already typed at render time. Fix: remove `disabled` from the props and set `approveBtn.disabled = ...` after creating it.

H2 pipeline.js:203-207 with 218-221. loadStoryList() does not change the render key, so when /api/story resolves after the first /api/pipeline render, the picker keeps only "-- new story --". Pane: 4 of 5 loads showed only "(new)", and the last still showed only "(new)" after 7 s. Fix: set `State.lastJSON = ''` before the render() at pipeline.js:207.

H3 pipeline.js:673-679. /api/images `jobs` is a list of dicts (server.py:669-671; live: 22 rows with `file`), not file names. `jobsFiles[i].indexOf` throws, so the packet button always fails. The `indexOf(pack)` substring test (677) is also wrong. Fix: `files = unique((data.jobs || []).map(j => 'flow/' + j.file))`, then pick the file whose rows hold the pack's shot ids.

H4 pipeline.py:256-259 (shots_ready also needs bible.json, 133-135). A partial run (stage_*_raw.json, no shots.json) returns "running" forever. The contract says "ready" ("run again to resume"). The client refuses Run unless ready or rejected (pipeline.js:530), so the owner cannot resume. Fix: return "ready" with detail "N stages saved, run again to resume" unless a job is active.

H5 pipeline.js:891. `ids: ''` reaches _ids(), which rejects an empty string (server.py:245-246; normalize 304-305): "ids must be a list of 1 to 200 shot ids". Prepare render always fails. Fix: drop `ids` from the args (scope "all" needs none).

## MEDIUM
M1 pipeline.py:265-267, 304-306, 363-365. A rejected stage stays "rejected" after a re-run (N9 partial). The gate can still be decided, but the chip and detail are stale. Fix: report "rejected" only while the reject record is newer than the stage output (compare with shots.json, finals or clips mtime).

M2 pipeline.js:143-146 and 160. With no saved story, each 5 s poll sets State.storyText = '' while storyDirty stays true, so the next re-render empties the typed text. Fix: stop assigning storyText in loadPipeline's else branch and on the 404 path; set it only when the slug changes.

M3 pipeline.js:433-442, 458-462; save/restore at 251-323. wiz-story-new-slug and wiz-story-overwrite are in neither saveFocusedInputs nor restoreDrafts, so any re-render clears them. Fix: keep both in State on input/change and restore them in restoreDrafts.

M4 pipeline.js:232 and 273-297. Each re-render removes the focused control. restoreFocusedInputs restores values but never calls focus(), so focus and caret leave a note or START box mid-typing. Fix: save document.activeElement.id and selectionStart, then focus() after restore.

M5 pipeline.js:185-201; server.py:926-927. Once project.pack is set and before the pack exists, /api/pack returns 404 "no such pack", and the error bar fires every 5 s. Fix: ignore the "no such pack" error in loadPack, or skip the call while analysis is ready or running.

M6 pipeline.py:524-532, 537. A shot with `seconds: null` makes `sec <= 0` raise TypeError. /api/pipeline/summary returns 500 and the error bar repeats (round-2 MED, still open). Fix: `sec = shot.get("seconds"); sec = sec if isinstance(sec, (int, float)) else 0`.

M7 style.css:115, 125, 127, 290-301. White on orange step circles (ready) is 2.7:1, white on amber (waiting_approval) 3.5:1, and the #111 progress text over the blue bar 3.6:1. All below AA. Fix: #222 text on orange and amber; darken --blue to #1d4ed8 (6.7:1 with white); print the progress count outside the bar.

## LOW
L1 pipeline.js:567: title "Gate A (Gate A): ..." repeats the gate header. Fix: "What you must approve".
L2 pipeline.js:1052: "Gate A rejectd". Fix: `decision === 'approve' ? 'approved' : 'rejected'`.
L3 pipeline.js:1046: onGateDecision returns silently while State.busy (any other action runs). Fix: showError("Busy, try again").
L4 app.js:209-210: app's showError does not remove the `success` class (style.css:65), so an error can show green. style.css has no `.bar-ok` rule, so #msg-bar (app.js:214-218) is unstyled. Fix: classList.remove('success') in app.js; add a `.bar-ok` rule.
L5 pipeline.js:973-975 with 303-304: a gate note survives the decision, so the next Approve sends the old text. Fix: clear State.gateNotes[gate.id] on success (pipeline.js:1051).
L6 pipeline.js:658-700 (and 386 onward): action buttons in locked stages stay enabled and answer with an error. Fix: disable them when the stage status is locked.
L7 pipeline.js:1226 with index.html:62: when /api/pipeline fails, the wizard is blank and only an 8 s error bar shows. Fix: keep a persistent "server not reachable, retrying" line while State.pipeline is null.
L8 pipeline.py:573-574: text says "outside 55..80" but only > 80 is checked. Fix: check both bounds or reword.
L9 server.py:931-937: /api/preview and /api/run have no stage check, so the wizard gate is client-only (round-2 H8). Fix: add the same stage check server-side (409).

## Layout and focus (checked)
- Viewport meta present (index.html:5). At 375 px the page has no horizontal overflow (scrollWidth 375), the stepper scrolls (style.css:154-161), the error bar is sticky. Gate A and read-out tables sit in .tablewrap; the dialog pre wraps (style.css:366-370).
- Focus: buttons get a 3 px outline (style.css:251-255); the dialog has a focus trap and Escape (pipeline.js:1069-1094). Inputs keep the browser ring.

## Notes
- The server on 8765 is stale: GET /api/pack returns the pre-round-3 shape (no props, modes, purpose or *_names; server.py:620-622 is not live). Restart it before the C7 screenshot. The client guards the missing fields, so nothing crashes.
- The pytest suite does not cover pipeline.js; H1-H5 were found by reading the code and by the pane.

VERDICT: FAIL (5 HIGH: H1-H5). Fix H1-H5 and M2-M5 before the C7 check.
