# UI simplification dispatch (lead, 2026-11-07) - two parallel coders W and E

Source of truth: `research/UI_COLD_TEST_2026-11-07.md` (independent tester, defects D1-D17, wording table C, ranked proposals D). The owner says the UI is complicated, mixed and jumbled. Goal: one clear path for a 60-year-old non-technical woman. RULE: MOVE or HIDE, never delete a control, id, class token or endpoint (parity rows stay true; `test_parity.py` anchors must still pass). Owner rules unchanged: no paid call, no Colab, no render, no push, English answers; typed words START and CLAUDE and the approvals stay (they only move into dialogs); stay English + Marathi (no Hindi UI).

Working folder for both: git worktree `D:\aai work\anime_studio_merge` (branch merge-v4-universal-2026-11-07). Never commit, push, stash, switch branches. Another coder works in the same folder: touch only your own files.

## Ownership
| Coder | May edit | Reads only |
|---|---|---|
| W (wizard) | `ui/static/pipeline.js` | everything else |
| E (shell and expert) | `ui/static/index.html`, `ui/static/app.js`, `ui/static/style.css`, `ui/static/tokens.css`, `ui/static/theme.js`, `ui/server.py`, `ui/pipeline.py` | pipeline.js |
| both | tests `ui/test_*.py` EXCEPT `test_parity.py` and `test_i18n.py` (update only assertions that pin text or structure you changed; never weaken a check: replace it with an equal check on the new text/structure) | |
| both | strings only via `python ui/i18n_merge.py BATCH.json --prefix <group> --replace` (replace allowed ONLY for existing keys of your own groups; Marathi in simple everyday Marathi, mark as draft; every key in en and mr) | |
Groups: W = `banner, dialog, ok, scope, step, story, next, warn, plan, writer, gate, pics, sum, video, files, runs, ops, icon`. E = `adv, theme, common, status, err, risk, app, lang`. `test_i18n.py` and `test_parity.py` are lead-only: list needed changes under REQUESTS.

## Task W (pipeline.js)
W1 One honest state (D1, D2, D4, D5): a step badge says "Finished" only when no failed stage is recorded and its data exists (languages saved etc.); the top line "Step N of 6" follows the OPEN step; one source object feeds the badge, the top line and "What to do next". Remove "step 9" wording from the user view.
W2 Duplicate card: the "Working on / Plan / Languages / Writer" card (`#wizard-scope`) repeats the header chips: keep the element but give it the `hidden` attribute (tests only need the id); the chips in the header stay.
W3 "Details for the helper" (about 20 times): render the fold only when it has content and call it "More"; file names, stage ids, commands, raw errors and ids go inside it only.
W4 Wording (cold test section C): Gate A-D -> "Your OK: the plan / the pictures / the video / the final video"; "Approve the plan"/"Send back" -> "Yes, the plan is good"/"No, change it" with one line what No does; no `--allow-spend`, `AUTHOR FIELDS`, `stage 3e1`, `Haiku effort LOW`, `fl2va`, `Mode: old style` in the user view (they may appear inside "More"); "Paid work is off. Ask your helper." once. Keep the typed words START and CLAUDE working, shown only inside their dialogs.
W5 Plan errors (D3): when the plan check finds errors show "The plan has N problems. Ask your helper to fix them." and DO NOT show the Approve button; show it only after a passing check.
W6 Writer chooser: one default choice visible, the other writers inside a "Other writers" fold; the Claude choice stays behind its tick plus typed word.
W7 Step 4 summary: drop the display of "Clips planned" and "Minutes to make" and "More numbers" (keep Parts, Scenes, Seconds, People, Places, Pictures done); show 0 instead of a dash (D17); readable names for people/places/things instead of raw ids like CHAR-KRISHNA (D9: use the display name field if the pack has one, else the id without its prefix, words separated, first letter capital).
W8 Locked steps and empty actions (D11): a locked step explains why ("Finish step 2 first") and is not a dead click; step 6 "Show" with an empty or unknown part says "Choose a part from the list".
W9 Story picker (D6): choosing in the picker no longer switches the project at once; a button "Open this story" does, with one line saying it changes the story for the whole page.
W10 Request bursts (D8): find why one story switch makes ~314 requests (repeated /api/status, pipeline/summary, registry, pipeline, story in bursts) and fix the cause (coalesce refreshes, no refresh from a refresh); report the before/after request count from a node/unit-level reasoning or a test; NO browser.
W11 Marathi (D14): anything W11-visible still English in Marathi mode that is not a product name (Flow, Colab, NVIDIA, Nano Banana, OpenRouter, Claude, Opus, Haiku may stay) gets a key.

## Task E (shell, expert area, server)
E1 Expert tools get their own place (cold test D1 proposal): the whole "For the helper: expert tools" block is hidden on the normal wizard page and shown on its own view opened from a footer link "Expert tools (for your helper)" (route `#expert`; back link "Back to the steps"); NOTHING is removed from it (all ids stay in index.html); the wizard page contains only the wizard, the header, the banners and the past-work slot. Existing hash routes `#story #images #bridge #video #export` must still open the right expert section (they now open the expert view).
E2 Phone header (D12): at <=480px the header chips fit one or two lines (smaller gaps, one line each, language and colour controls on one row), the step list becomes a horizontal strip, real content starts within the first screen (target: first step card visible without scrolling at 375x812); desktop unchanged.
E3 Tabs (D13): expert nav buttons get `role=tab`, `aria-selected`, the container `role=tablist`; the hash changes only when the expert view is open.
E4 Fix the 404 (D7): `GET /api/pack/validate?pack=...` returns 404; find who calls it (grep both js files and server.py routes) and fix the caller or add the route in server.py (read-only, same safe-path rules as its siblings, test in `ui/test_*.py`).
E5 Expert polish (D15): "Chapter" in the expert Pictures section is called "Part" like the wizard; badges R, W, N get a one-line legend; empty tables say what to do; expert fetch pollers must not fire while the expert view is hidden.
E6 Marathi: the Past work table headers and cells shown to the user go through keys; names that are product names may stay.
E7 Status/ops: nothing else; do not change the colour tokens' values (only add a class if needed).

## Done when (each coder, own tasks)
- `python -m pytest ui -q` shows no new failure (current baseline: 540 pass, 10 skip, 0 fail); `PARITY_BUILT=T2,T3,T4 python -m pytest ui/test_parity.py -q` passes; `python -m pytest ui/test_i18n.py -q` passes (no orphan or missing keys; `t()` only with literal keys); `node --check` on every js you touched.
- Do NOT open a browser or start a server (the lead tests in the browser).
- Final report in English, max 40 lines: per task id done/not done, files, tests, decisions, REQUESTS (test_i18n/test_parity changes), what you could not verify.

## Logging (owner rule, every step)
`echo "$(date +%m-%d\ %H:%M) | coderW(haiku,xhigh) | TYPE | files | result" >> "D:/aai work/anime_studio/PROJECT_LOG.md"` (use coderE(haiku,xhigh) for E; TYPE: CMD EDIT TEST DECISION FAIL AGENT-START AGENT-DONE; write any pipe inside the result as /). No Colab, no render, no paid or model API call.

## Overrides after the review (research/UI_SIMPLIFY_DISPATCH_REVIEW_2026-11-07.md; these WIN over the text above)
1. D7/E4: `/api/pack/validate` exists; `pack_validate_get` raises 404 on purpose and pipeline.js treats 404 as normal. E changes the server to answer 200 `{"status": "none"}` when there is nothing to validate; W changes pipeline.js (~678-686) to treat `status: "none"` as normal (keep tolerating 404). Server test updated by E.
2. D8/W10: W guards `refreshWizard` (~798) and the validate loop (~678) against repeated/overlapping refreshes (coalesce). E removes duplicate polling in app.js (`tick` ~1566, `/api/status` ~379, `StudioWizard.refresh` call ~1528) and gates every expert poller on the expert view being open. The lead measures requests in the browser (baseline 314 for one story switch); coders must not claim a number.
3. Keys: `common.details_helper` stays E's (index.html:56). W uses a NEW key `warn.more` for its fold. New key groups: W may add group `wiz` (new keys), E may add group `exp`. The footer link and every other new string in index.html is a `data-i18n` element WITHOUT child elements.
4. D6 story switchers: BOTH switchers (pipeline.js ~1138-1162, W; app.js ~1523-1527, E) stop posting `/api/pipeline/project` on `change`; each gets a button "Open this story" that posts it, plus one line saying it changes the story for the whole page. Keep the select ids.
5. "Paid work" is said once, in the header badge (`#spend-badge`, key `app.spend_off`, E: wording "Paid work is off. Ask your helper."); W removes its own repeat in step 6.
6. E6 (Past work table, keys `runs.*`, built in pipeline.js registryPanel/runsTable ~2495-2512) belongs to W, not E. W renames the heading "Past work (records)" to "Earlier work".
7. `#runs-slot` and `#expert-ops` placement: `#runs-slot` stays OUTSIDE the hidden expert view; `#expert-ops` moves with the expert view. Default hash (app.js ~1562): the page opens on the wizard, NOT on `#story`; only the old section hashes open the expert view. E5 pollers run only while the expert view is open.
8. Tests that pin text or structure stay true (keep the strings as VALUES of keys, do not edit those asserts): test_static ~255-261 ("Flow agents run on Haiku, effort LOW", "gap G1", "gap G12", "I looked at full size", "not available yet", "--allow-spend" in en.json, "EXECUTE " in app.js): these texts stay in the DOM/JSON (they may sit inside the "More" fold). test_static ~422-428 (button min-height 48px, `grid-template-columns: 1fr 1fr`, `#wiz-panels` 1fr on phone): E2 must not break them. test_static ~130-135 and ~383-389: keep ids `nav-%s` and `data-section`; W5 error text goes into an existing aria-live region (max 2 `role=alert`). ~412: every new dialog has class `dialog` and `tabindex="-1"`. ~392-403: ids built by pipeline.js stay built by pipeline.js (MOVE or HIDE is not enough: do not move creation to another file).
9. Added assignments: D5 (stale writer chip vs the plan in use) and the picker label showing plan ids in brackets -> W (show the plan the story really uses, plain words); cold-test row "Make the plan with ... on a story that already has a plan" -> W label "Make a NEW plan"; D15 12 chapters vs 6 parts -> E (find the key of the "Chapter" label in `adv.images.*`/index.html and rename it "Part"; a note when the lists differ); D16 is DROPPED on purpose (system theme equal to light is correct on a light-mode PC).
10. Browser-only checks (375x812 first card, keyboard tabs, locked-step click, request count) are the lead's; coders write the code and the tests that can run without a browser.
