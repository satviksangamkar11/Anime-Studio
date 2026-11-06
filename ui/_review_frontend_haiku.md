# Front-end review: Anime Studio wizard (2026-11-06, read-only)
Verdict: not ready. 10 HIGH, 9 MEDIUM, 3 LOW. Route paths, methods and argument names match the contract; two commands are refused on values.

HIGH
H1 pipeline.js:539,553-557 Approve is disabled for every gate; only Gate C gets the enabling listener. Gates A, B, D can never be approved. Fix: `disabled: gate.id === 'C'`.
H2 pipeline.js:137,640-643 The 5 s poll calls render(), which empties #wizard even when nothing changed. Typed notes, START text and unsaved story are wiped. Fix: skip render when the fetched JSON is unchanged.
H3 pipeline.js:629-630 showError sets bar.textContent (deletes #error-text and Dismiss), adds class `show` (no CSS rule) and never clears `hidden` (style.css:22). Every error is invisible, and app.js:209 then throws on null. Fix: write to #error-text and set bar.hidden=false.
H4 pipeline.js:221,232 create id="story-slug" and id="story-text", already used at index.html:86 and :94. The wizard comes first, so app.js:591 and :619 hit the wizard controls. Fix: rename to wiz-story-slug and wiz-story-text.
H5 style.css:274,346 set .screen and .tabpanel to display:none; only `.active` overrides it, but app.js only toggles `hidden` (app.js:572, :725). Every old tool panel stays blank, which breaks C3. Fix: delete both display:none rules.
H6 pipeline.js:355-357 Packet: `flow/<pack>_jobs.json` does not match the real files `A_KM_flow_jobs_*.json` (server.py:660), and `shots: []` is refused (server.py:1010). Always fails. Fix: send the real jobs file and shot ids.
H7 pipeline.js:458-459 Prepare render: `story` is a slug but the server needs a .json path (server.py:292); `ids: ''` is refused (server.py:242-247, 304). Names are right (server.py:492). Fix: send the pack's shots.json and omit ids.
H8 pipeline.js:202-212 Action buttons ignore stage status. "Run story analysis" can re-run after Gate A is approved. Fix: enable only when the stage is ready or rejected; server must refuse out-of-order runs.
H9 pipeline.js:395,594-623 Confirm and packet dialogs use class `.modal` (no CSS) and are appended to the end of body: not an overlay, below the Advanced tools. The owner cannot see the argv before Run. Fix: reuse #modal (index.html:314) or style `.modal` as a fixed overlay.
H10 index.html:61 ui/pipeline.py does not exist (server.py:1072-1078 returns 503). The wizard shows "The page needs JavaScript." forever, and H3 hides the error. Blocks C1.

MEDIUM
M1 pipeline.js:536-568 No in-flight guard: a double click sends two gate POSTs. Fix: busy flag; server must refuse a decision on a non-open gate.
M2 pipeline.js:160 Stepper writes `.status-line`; index.html uses `.step-status` (lines 30-55), so every step reads "Locked". Fix: querySelector('.step-status').
M3 pipeline.js:489 Gate card gets `gate-<id>`, not the state, so style.css:145-147 never applies. No CSS for .chip, .current, .tile, .check, .counts, .note, .hint, .gate-info, .progress-text. C3 incomplete.
M4 pipeline.js:248 No overwrite option, so a saved story cannot change from the wizard (server.py:881-882). No picker for existing stories.
M5 pipeline.js:288,464 Sends confirm:'1' for spend commands; server needs the typed confirm_text (server.py:935-936). Unreachable now; fix before any spend stage.
M6 Contrast below 4.5:1: white on #e8870e 2.7 (style.css:116), white on #c27a00 3.4 (:118), #222 on #2563eb 3.1 (pipeline.js:181). Progress text sits inside the bar and clips at low %.
M7 a11y: dialogs lack role=dialog, focus move and Escape; the x button has no label; status is colour-only on the stepper.
M8 Phone 390 px: confirm and packet `pre` (pipeline.js:382,599) do not wrap and widen the page; readout tiles are unstyled blocks.
M9 index.html:64 Advanced tools open by default, so "Run on Colab... (spend gate)" (index.html:261) shows on load. index.html:80 is a second <main>.

LOW
L1 pipeline.js:178 total 0 gives NaN%.
L2 Flow effort: page and packet say Haiku LOW (pipeline.js:364, server.py:1015), matching the checklist. A memory note says Haiku HIGH; confirm with the owner.
L3 Checklist asks for a left stepper; built as a top horizontal stepper (index.html:25). Raw codes (waiting_approval, open) shown instead of labels.

OWNER LIST (section 5)
Present: story, analysis, Gate A, images, Gate B, read-out, Gate C START, render, Gate D; Haiku LOW and "Claude starts them" note (pipeline.js:364); no Claude call; no spend control in the wizard.
Missing: Gate A shows no shot list, per-shot durations, sermon-vs-story events or modes (analysis card shows episodes, characters, places, props; summary.modes unused). Read-out shows character and place counts only, no names, per-episode table, props, modes, takes, clips home, pending or reviewed. No per-generation check and no full-size check before Gate B. Render shows no clip or QA status. Export is text only, no reel files (server.py:1054-1055).

VERIFIED OK
Routes, methods and bodies match the contract (server.py:1106-1150); X-UI on every call (pipeline.js:66, server.py:1190); write_pack args match (server.py:470). Gate C Approve needs exact START (555) and sends confirm (543-545); Reject needs 1-300 after trim (564); locked gates render no buttons (496-499). No innerHTML, insertAdjacentHTML, eval or document.write; no absolute URLs; all ids pipeline.js reads exist; every app.js literal id exists in index.html; script order correct. Confirm shows argv before Run (286, 462). No secrets shown; packet has a secret check (server.py:1027).
