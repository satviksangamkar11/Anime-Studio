# Round 2 front-end review: Anime Studio wizard (2026-11-06, read-only)
Verdict: NOT READY. Fixed: H1, H3, H4, H5, H9 (overlay style), H10 (root cause), M2, M3, M9, L1, L3 labels. No stage can be completed end to end from the page.
## Remaining HIGH (fix in this order)
N1 Nothing writes runs/project.json (save_project is defined at pipeline.py:42 and called only by test_pipeline.py). story_slug, pack, images_dir stay null, so Story never shows saved, Analysis says "Save the story first" (pipeline.js:401-404), and Images, Read-out, Render and Gates B-D are unreachable (pipeline.py:123-140).
N2 Story picker is always empty: pipeline.js:169 reads data.stories, server returns {slugs} (server.py:859). No new-slug text input exists (pipeline.js:296-311), so Save story always fails the slug check (pipeline.js:359-362). M4 NOT FIXED.
N3 Story text is reset every 5 s: loadStory sets State.storyText from the server (pipeline.js:146) and restoreDrafts writes it into #wiz-story-text (pipeline.js:221-223) on every poll, ignoring focus. Typed or pasted text is gone within 5 s.
N4 post() and get() return undefined (pipeline.js:116-117), so `.finally`/`.catch` throw at pipeline.js:372, 424, 545, 550, 760, 907. Buttons stay disabled and State.busy stays true, so onGateDecision (pipeline.js:900) silently drops every decision after the first. M1 broken.
N5 Stale cards: render() stores lastJSON (pipeline.js:187) before the focus check (190-193). The clicked button keeps focus inside #wizard in Chromium and Firefox, so the new state is never drawn and later polls see no change.
N6 Gate A never draws: loadPack (pipeline.js:159) has no caller, so packInfo stays null (pipeline.js:433). read_pack also lacks purpose, modes and props (server.py:595-616), and names arrive as {id,name} objects shown as "[object Object]" (pipeline.js:492, 497).
N7 Pack and packet paths: pipeline.js:539 sends the bare pack name, but /api/pack needs stories/<slug>/<name> (server.py:278, 1119). The jobs path is wrong: read_pack has no `jobs` key (pipeline.js:540), and the real files are flow/A_KM_flow_jobs_*.json (server.py:660). H6 NOT FIXED.
N8 Confirm and packet dialogs cannot be seen: #modal sits inside closed <details id="advanced-tools"> (index.html:66, 316, 330) and nothing opens it. Its `.modal .dialog` rule (style.css:449) never matches class `overlay`, so the dialog has no panel. The owner cannot read the argv before Run.
N9 Rejects are permanent: the last decision wins (pipeline.py:210-229), the stage stays "rejected" after a re-run (pipeline.py:265-266, 330-331), and apply_gate needs state "open" (pipeline.py:465). Nothing can re-approve, against "a rejected gate re-opens its stage".
N10 Analysis stuck "Running": any stage_*_raw.json without shots.json means running (pipeline.py:256-259). "failed" is never produced, and the client refuses Run unless ready or rejected (pipeline.js:406). A run that stops partway (e.g. upstream 429) blocks the stage.
N11 Read-out per-episode table shows "undefined": summary uses key `episode` (pipeline.py:535), pipeline.js:645 reads `ep.n`.
N12 Render: pipeline.js:747 sends 'flow/<pack>/shots.json' (must be stories/<slug>/<pack>/shots.json, server.py:292), and pipeline.js:750 sends ids '' (refused, server.py:242-247). H7 NOT FIXED. h3/render_controller.py exists, so H3_MISSING will not block.
## New MEDIUM
Reject note must be printable ASCII (pipeline.py:475-476), which blocks Hindi and Marathi; the client has no check. Approve notes are not validated (pipeline.py:447-455). The textarea allows newlines (pipeline.js:824) that reject then refuses (pipeline.py:473-474).
START and pack-name inputs are rebuilt and not kept in State (pipeline.js:386-395, 836-845), so they clear on any data change while unfocused.
Error bar sits at page top and is not sticky (index.html:20, style.css:52): errors from gate cards at the bottom are off-screen. No success message is shown after approve or save.
summary() raises TypeError on null seconds or episode (pipeline.py:521-527, 534-537), so /api/pipeline/summary returns 500 and the error bar fires every 5 s.
Story limit mismatch: the client counts UTF-16 chars up to 200000 (pipeline.js:335-340); the server counts 204800 bytes (server.py:38, 876). Devanagari text passes the client and fails at save with 413.
H8 server half open: /api/preview and /api/run check no stage state (server.py:894-949). The wizard check is client-only, and 'failed' is not handled.
Phone: dialog pre has no wrap class (pipeline.js:584, 953); Gate A and read-out tables are not in .tablewrap (pipeline.js:441, 468, 634).
## LOW
"Gate A (Gate A)" title (pipeline.js:801). "Clips planned" tile shows the shot count, not shots x takes (pipeline.js:619; pipeline.py:588 vs 138).
Stepper ol/li lack display:flex (style.css:83-117): phone shows a six-row list, not a scroller; step numbers are plain text.
restoreDrafts uses undeclared `wizard`, resolved through window named access (pipeline.js:213). It works but is fragile. "The page needs JavaScript." stays if /api/pipeline fails (index.html:62). `.gate.locked` has no style (style.css:177 targets .gate-locked).
## Previous findings
H1 FIXED pipeline.js:853, 868-870. H2 NOT FIXED: notes survive; story text (N3) and START do not. H3 FIXED pipeline.js:977-987, style.css:25, app.js:1373. H4 FIXED: wiz-* ids unique. H5 FIXED: style.css:348-349 and 420-421 no longer hide. H6 NOT FIXED (N7). H7 NOT FIXED (N12). H8 PARTIAL (client-only, see MEDIUM). H9 PARTIAL: #modal reused (index.html:316) but hidden (N8). H10 FIXED: pipeline.py exists and server imports it (server.py:1074-1080).
M1 PARTIAL: flag never cleared (N4); server refuses a second decision with 409 (pipeline.py:465-466). M2 FIXED pipeline.js:238. M3 FIXED pipeline.js:798, style.css:143-177, 248-290. M4 PARTIAL (N2). M5 N/A: no spend path in the wizard. M6 PARTIAL: chips fixed (style.css:156-163); still open: .tile-value orange on white 2.7:1 (style.css:261-265), approved chip white on #1f8a4c 4.4:1 (style.css:159), progress text sits over the grey track (style.css:233-245).
M7 PARTIAL: role=dialog, aria-modal, Escape and labelled Close are present (index.html:317-320, pipeline.js:922-927); no focus trap; focus return lands on a non-focusable <main> (pipeline.js:939-940). M8 PARTIAL: tiles fixed (style.css:248-266); dialog pre and tables not (see MEDIUM). M9 FIXED: details closed (index.html:66), one <main>. L1 FIXED pipeline.js:255. L2 OPEN: checklist and server say Haiku LOW (server.py:1017); memory note project_flow_image_system_v2 says Haiku HIGH. Owner to confirm. L3 PARTIAL: labels fixed (pipeline.js:11-26, 239); desktop left column present (style.css:71-102).
## Owner requirements
Gate A: id, episode, mode, seconds exist in the code but are never drawn (N6); purpose, props and modes are not in the data; names are unreadable.
Read-out: all fields exist (pipeline.py:572-598) and are drawn, but the per-episode table is wrong (N11) and the stage is unreachable (N1, N9).
Flow note (Haiku LOW, Claude starts from chat) present at pipeline.js:558. No spend control in the wizard: met. Readable status labels: met. Left stepper on desktop: met.
## Layout (from CSS only)
390 px: dialog pre overflows its box; the Gate A 5-column table is unwrapped and about card width (~304 px), so it may widen the page; the stepper stacks six rows before the content.
1280 px: no page overflow found. Dialog unstyled (text #222 on the 55% black overlay, about 3:1). Stepper numbers render as inline text.
## Safe
No innerHTML, insertAdjacentHTML, eval or document.write in static/. No absolute URLs. Every POST sends X-UI (pipeline.js:93). No id clashes: wiz-*, analysis-pack, gate-note-*, gate-confirm-C are unique; app.js shares only #modal and #error-bar (app.js:410, 1370-1373).
Gate C exact START on client (pipeline.js:857-858) and server (pipeline.py:478-480). Reject 1-300 after trim (pipeline.js:878). Locked gates have no buttons (pipeline.js:806-809). write_pack args match (server.py:470). Pack has 45 shots, under the 60-shot packet cap (server.py:1012).
