# UI cold test, Anime Studio, 2026-11-07 (UXtest sonnet medium)
Method: own tab, http://127.0.0.1:8765/, desktop 1280x800 and phone 375x812, EN + Marathi, 4 themes, both stories. Only read/open/switch actions. Clicked "Check the plan" (read-only) once. Changed the story picker to kaliya_mardan and back to upanishad (this does POST /api/pipeline/project on the server); restored.

## (A) VERDICT
Yes, it is jumbled, but the wizard core is clear; the mess is around it. Basics are fine: no horizontal scroll, no contrast fail (my script, all 4 themes), text min 18px, buttons 32px+, focus ring visible, Marathi almost fully translated.
1. Two UIs doing the same job: wizard steps 1-6 AND the "For the helper: expert tools" panel (story picker, plan name, make plan, continue plan, check plan, save story, Pictures, Final files tabs) repeat each other.
2. Status contradicts itself: Step 1 "Finished" + "A step failed"; Step 5 "Final check (step 9): Fail" + "Nothing blocks the video"; top line says "Step 2 of 6" while step 3/5 is open.
3. Programmer wording and raw errors in front of the user (Gate A-D, Flow agent packet, Haiku effort LOW, --allow-spend, AUTHOR FIELDS, "stage 3e1", file names, raw IDs CHAR-KRISHNA).
4. Same facts shown 2-3 times (Working on / Plan / Languages in header chips AND in a card; "Details for the helper" appears about 20 times).
5. Dead ends: "Fix them first" with no way for her to fix; locked steps give no explanation; buttons that start a model run sit next to harmless ones without a distinction.

## (B) DEFECTS
| id | sev | where | what I did | what happened | expected / evidence |
|---|---|---|---|---|---|
| D1 | high | Step 1, upanishad | opened step 1 | badge "Finished" but body says "Next: A step failed. Look at it, fix it, then run it again." and "The server reports a warning." (x2) | one honest state. Hidden detail: "Stage 3e1 of pack_super-vl_20261107_v2_look failed its checks: delete stage_3e1_raw.json ..." (concerns a v2 plan, picker shows v1) |
| D2 | high | Step 5 | opened step 5 | "Final check (step 9) Fail" next to "Nothing blocks the video."; wizard has only 6 steps | no "step 9"; one verdict |
| D3 | high | Step 2, kaliya_mardan | pressed "Check the plan" | "53 errors found ... Mode: old style ... Fix them first." plus Approve/Send back buttons still visible | tell her who fixes it ("ask your helper"), hide Approve |
| D4 | med | top line | opened steps 1, 3, 4, 5, 6 | "Step 2 of 6: Plan the story. Status: Needs your OK." never changes | line follows the open step |
| D5 | med | step 1, kaliya_mardan | picked kaliya in picker | "Languages: none ticked", "Saved: none saved yet" but step 1 says "Finished"; header "Writer: OpenRouter Super VL" for a story whose plan is pack_dots_v22 | Finished only if languages saved; writer matches plan (writer shown looks stale, guess) |
| D6 | med | story picker | changed select | switches the server-wide current story instantly (POST /api/pipeline/project), no confirm, no undo hint; one mistaken scroll over the select changes the story | confirm or a plain "Open this story" button |
| D7 | med | console/network | loaded and clicked | 7x "Failed to load resource: 404"; `GET /api/pack/validate?pack=...` returns 404 for both stories | no 404s |
| D8 | med | network | switched story once | 314 requests in the session; each refresh fires /api/status x3 + pipeline/summary + registry + pipeline + story in bursts | one fetch each (guess: render loop) |
| D9 | med | step 2 plan table, kaliya | read People/Places/Things | raw codes "CHAR-KRISHNA, ENV-KALIYA-DAH-POISONED, PROP-AMRIT-KALASH"; upanishad shows readable names | readable names |
| D10 | med | step 4 | read numbers | "171 Clips planned", "388.2 Minutes to make", but 57 scenes / 404 s | explain, or drop (6.5 hours is alarming) |
| D11 | med | steps 3-6 | tried locked step buttons in left list and "Show" in step 6 | clicking locked step gives no message; Step 6 "Show" with empty/99 part: no visible change, no request | say "Finish step 2 first" / "Part not found" |
| D12 | med | phone 375 | loaded page | header+banners 1195px high; first real content starts after 1.5 screens; no horizontal scroll | compact header, content first |
| D13 | low | expert tabs | inspected | tab buttons (Story text, Pictures, Key frames, Video clips, Final files) have no role=tab / aria-selected; hash silently changes to #images/#export | proper tabs |
| D14 | low | Marathi | switched | leftover English: "Flow", "Colab", "Google", "draft", "VL", "English" button, raw story/plan ids, Past work table cells (title, paste, opus, model id) | acceptable except Past work cells |
| D15 | low | expert Pictures | read | "Chapter" select has 12 options (1-12) while the story has 6 "Parts"; empty table "No rows yet." ; mini badges "R", "W", "N" with no legend | same word as wizard; explain badges |
| D16 | low | system theme | opened Colours | 4 choices: "Same as device" looks identical to Light (bg rgb 243,241,232) on this PC | fine (guess: depends on OS) |
| D17 | low | step 3 | read | "Finished: 0 of 114" yet 12 expert "Chapter" rows; "Pictures: - of 114" shows a dash | show 0 |

Passed: no overflow in all 4 themes at 1280, low-contrast items 0, focus ring visible (white on dark header, teal on light), skip link "Go to the steps" exists, all inputs have labels, Marathi page title changes.

## (C) CONFUSION (exact wording -> simple replacement)
- "Gate A: OK on the plan" / "Gate B/C/D" -> "Your OK: the plan" / "Your OK: the pictures" / "... the video" / "... the final video".
- "Approve the plan" / "Send back" -> "Yes, the plan is good" / "No, change it" (add what "send back" does).
- "Make the Flow agent packet" + "Flow agents run on Haiku, effort LOW; Claude starts them from the chat" -> "Make the picture instructions (your helper pastes them)".
- "Details for the helper" (about 20 times, even when nothing is in it) -> show only when there is content; one name: "More".
- "Final check (step 9)", "Detail writer", "Filled in: 0. Missing: 0.", "Saved copy: not needed" -> hide, or "Last check" / "Fill in the missing details".
- "To run it, type AUTHOR FIELDS exactly." and "Off: the server must be started with --allow-spend" -> "Paid work is off. Ask your helper." Never show the phrase to type.
- "Mode: old style", "Modes: fl2va:57", column "Method fl2va" -> remove.
- "A step file is too small to be real." / "stage 3e1 ... delete stage_3e1_raw.json" -> "One step did not finish. Ask your helper."
- "Where it stopped / Next: ..." vs top status -> one box named "What to do next".
- "Plan name (small letters, numbers and _ only)" next to "Make the plan with OpenRouter Super VL" on a story that already has a plan: a woman cannot tell if this overwrites; label "Make a NEW plan".
- "NVIDIA Ultra / NVIDIA Super VL / OpenRouter Super VL / Claude (Opus)" with Slow/Medium/High/Good and "not tested yet": 5 radio choices; she cannot choose. Give one default, put others under "More".
- "Nothing is paid here" (step 6) next to "Paid work: OFF (safe)" (header): say once.
- "Past work (records)": table of models, packs, ids - not for her.
- Story picker mixes ids in brackets: "kaliya_mardan (pack_dots_full_v22, pack_dots_v22, pack_nemotron_v1)": she cannot know which plan is used.

## (D) SIMPLIFICATION (ranked, for a coder)
1. Hide the whole "For the helper: expert tools" block behind a separate page (#/expert, link in footer) so the wizard page has one job. Remove from it everything the wizard already does: story picker, plan name + make plan, continue plan, check plan, save story, Final files tab. Keep Colab/disk check, Key frames, Video clips, Stop.
2. One status source: compute step badge, top line and "Where it stopped" from the same state object; a step is "Finished" only if no failure is recorded (fixes D1, D2, D4, D5).
3. Remove the duplicated card "Working on / Plan / Languages / Writer" (it repeats the header chips). Keep chips only; on phone collapse chips into one line.
4. Replace every "Details for the helper" with one "More" disclosure rendered only if it has content; move file names, stage ids, commands, errors inside.
5. Rename Gate A-D and Approve/Send back as in (C); show the Approve button only after the check passes (it already says "run the check first" but still shows buttons).
6. Step 2: one default writer, the 5 radios under "Other writers"; the plan list should show only the plan the story uses.
7. Step 4: drop "Clips planned / Minutes to make / More numbers" or explain in one line; show only Parts, Scenes, Seconds, People, Places, Pictures done.
8. Make locked steps unclickable with a visible reason ("Finish step 2 first") and stop auto-hash changes from expert tabs.
9. Phone: stack header into one row, put steps list as a horizontal strip, content first.
10. Fix 404 /api/pack/validate and collapse the repeated fetch bursts.

## (E) NOT TESTED
- Buttons that start work or a model run (Make the plan..., Build picture jobs, Make the Flow agent packet, Fill in the details, Prepare video files, Colab/paid session, Stop the work now, Get the transcript, Save story, Save language/voice/music): forbidden by owner rules; their error messages for empty input are therefore unknown.
- Approve/Send back (gates): forbidden; Preview not found as a button in the steps I opened (guess: appears only inside "More choices (voice, music, voice map)", which I did not expand).
- Steps 3-6 with real data (locked, since step 2 is not approved); step 6 results.
- Phone width only checked for the top of the page and overflow, not every step; Marathi only checked at desktop width.
- Screen reader behaviour; full Tab walk through every control (checked first 15 stops only).
- The other three stories (ashtavakra_gita_katha, kaliya_katha_dhenuk, mahadev_katha_indresh) were not opened.
