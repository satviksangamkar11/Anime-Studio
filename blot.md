# blot.md - standing rules for every session and agent in this folder

## RULE 1: LOG EVERY STEP (owner, 2026-11-07)
After EVERY step, append ONE line to `PROJECT_LOG.md` section "LIVE LOG" (bottom of file) before doing the next step.
A step = a command run, a file edit, a test run, a subagent started, a subagent finished, a review started or finished, a decision, a failure. No exceptions, no batching.
A line that is skipped is context lost when the session or account changes.

## LINE FORMAT (one line, max ~200 characters, English)
`MM-DD HH:MM | WHO | TYPE | WHERE | RESULT`

- WHO: `me` (the session) or an agent id (EV, S1 ...) with model and effort once at START, e.g. `EV(haiku,high)`
- TYPE: `CMD` `EDIT` `TEST` `AGENT-START` `AGENT-DONE` `REVIEW-START` `REVIEW-DONE` `DECISION` `FAIL` `OWNER`
- WHERE: file(s) or command, shortest path (`h3/gate_d_audio.py`), several -> `a.py,b.py`
- RESULT: the state change, not the story. Numbers beat sentences: `h3 385 pass`, `3 findings, 1 real`, `fixed 2`.
- provider only when a model is called: `NVIDIA` or `OpenRouter` (otherwise omit = local, no model call)
- FAIL lines say the cause in 5-10 words and what is next. OWNER lines quote the decision in 10 words.

## KEEP IT SHORT
1. Facts only: what, where, result. No reasoning, no apology, no repeated context.
2. Do not copy file content or test output; give the count and the path.
3. Refer by id (agent EV, checklist 1.3, finding R3-2) instead of re-describing.
4. Several tiny edits for one aim = one line only if they happened back to back with no test between.
5. Never edit old lines. A correction is a new line starting `FIX:`.

## NOW BLOCK (the resume header)
`PROJECT_LOG.md` starts with a `NOW` block of at most 8 lines. OVERWRITE it after every agent finishes or every checklist box is ticked:
current checklist item, agents running (id, model, effort, what), last green suite counts, blockers, next 2 actions.
A new session reads NOW first, then the last 20 LIVE LOG lines, then `CHECKLIST_ARCHITECTURE_2026-11-07.md`.

## RULE 2: CHECKLIST
Tick `[x]` in `CHECKLIST_ARCHITECTURE_2026-11-07.md` only when the step is done AND verified. Log the tick.

## RULE 3: AGENT BRIEFS
Every agent brief must include: "append lines in blot.md format to PROJECT_LOG.md after every step" and its file ownership. Agents never commit or push.

## OTHER STANDING RULES (details in HANDOFF section 13 and memory)
No push without the owner's go. No paid or ElevenLabs/Colab spend without go. Reviews = Nemotron 3.5 Super VL (OpenRouter free) + Dots. Easy English/Hindi/Marathi everywhere. Answer in English.

## RULE 4: NO COLAB CALLS (owner, 2026-11-07)
No Colab call of any kind (no colab CLI, no Colab runs, no sessions). Applies to me and every agent until the owner lifts it. Also: no renders, no ElevenLabs, no paid calls.

## RULE 5: REVIEW AGAIN AFTER FIXES (owner, 2026-11-07)
Every review round is followed by fixes and then a SECOND review of the fixed files (Super VL + Dots, free models). Repeat until a round finds no real defect. Log each round start and finish.

## RULE 6: REVIEWER CHECKS INSTRUCTIONS BEFORE THEY GO TO AGENTS (owner, 2026-11-07)
Before any agent prompt or instruction file is sent to an agent, Super VL + Dots (free models) review it; I triage, fix, review again (rule 5), and only then send. Log review start, finish and the send. Prompts are saved as files under research/ (for example `_prompt_*.md`, `UI_PARALLEL_DISPATCH_*.md`).

## RULE 7: UI COLOUR SYSTEM GUIDE (owner, 2026-11-07)
SCOPE: the control-panel UI only (ui/static/), nothing else in the pipeline (owner, 2026-11-07). Owner's guide (v1, unchanged): `anime_studio_merge/docs/UI_COLOUR_SYSTEM_GUIDE_2026-11-07.md`. Research-hardened v2 (research agent): `..._v2.md` next to it; notes in `research/COLOUR_RESEARCH_NOTES_2026-11-07.md`. The colour work starts only after the wizard and expert-tool tasks (T3, T4) are verified, never in parallel with a coder that owns style.css or index.html. Never push; palette is research-informed, never "clinically proven".

## RULE 8: REVIEW CAP (owner, 2026-11-07)
Reviews of instructions and code: ONE pass plus ONE check of the fixes (free reviewers Nemotron Super VL + Dots, or Haiku medium when the owner asks). Not endless rounds; a round with no HIGH finding ends the review and the work starts. Log each review start and finish.

## RULE 9: UI LANGUAGES AND SCOPE (owner, 2026-11-07)
The UI is English + Marathi only (no Hindi UI). The research-based colour guide `docs/UI_COLOUR_SYSTEM_GUIDE_2026-11-07_v2.md` wins over v1 where they differ. Controls are MOVED or HIDDEN, never deleted (parity rows stay true). A UI task is not done until it has been tried in the browser at 375 and 1280 px in both languages, and an independent cold test (`research/UI_COLD_TEST_*.md` style) found no high defect.

## RULE 10: LOG AND NOW UPKEEP (owner, 2026-11-07, repeated)
The one log is `D:\aai work\anime_studio\PROJECT_LOG.md`; copies in worktrees are stale and never written. Every step gets its line in the same turn (a line for a step that did not happen is a FIX line). Overwrite the NOW block after every agent finish. `blot.md` in every worktree is kept equal to this one (sync on every rule change). Backfill gaps at once with BACKFILL lines.

## RULE 11: NO RENDER CALLS AND NO OPUS CALLS (owner, 2026-11-07)
No render of any kind and no Opus call (neither by me nor by any agent or script) until the owner lifts it. Applies with rule 4 (no Colab, no ElevenLabs, no paid calls). Agents use only the models the owner already named for their job (Haiku/Sonnet agents, free OpenRouter models); the UI's Claude/Opus choice stays behind its tick and typed word and is never clicked in tests.

## RULE 12: REVIEWERS = NEMOTRON SUPER VL + XING (owner, 2026-11-07)
Free reviewers are now Nemotron 3.5 Super VL (`nvidia/nemotron-3.5-super-vl:free`) and Xing (`xingchen-agi/xing4.0-29b-a4b:free`), both OpenRouter free. Dots is no longer used (slow). Runner: `research/_run_uifinal_reviews.py xing|supervl`.

## RULE 13: DEVA NEON IS THE FIXED DEFAULT STYLE (owner, 2026-11-07)
From now every story uses the `deva_neon` style pack unless its story.json names another one (`kaliya_mardan` stays on `braj_earth`). The default lives in `core/core.json` key `default_style_pack`; the writer, new story.json files and the UI read it from there. The UI and server let the owner choose the style per story (style chooser in step 1; `GET /api/styles`, `POST /api/story/<slug>/style`). Supersedes OPEN_QUESTIONS Q1 for new work. The Assay UI review (owner: "ASCII") runs AFTER the style chooser is built and the simplification is verified.

## RULE 14: HEAVY FILES GO TO GOOGLE DRIVE (owner, 2026-11-07)
All rendered files, images, videos and other heavy outputs are stored on Google Drive; local disk (C: is nearly full, D: has a few GB) is used only when there is no other option. Code, small text (SOURCE.md, plans, logs, reports) and tools that must run locally stay local. Never upload `secrets/`, keys or tokens. STATUS 2026-11-07: Drive is NOT yet reachable from this machine (no Drive connector in the session, no Google Drive for desktop drive letter); until it is, heavy outputs wait or use D: only with the owner's OK. When Drive is reachable: set the Drive folder, point `flow_outputs`/render outputs there, and move finished heavy files off D:.

## RULE 15: PACE, PHONE CHECKS, AGENT STALLS (owner, 2026-11-07)
Owner: skip the phone-size UI checks (desktop width only is enough; mark phone as not tested). Finish steps as fast as possible. An agent that writes no log line for 20 minutes is treated as stalled: replace it at once (Haiku xhigh coders stalled twice on the 2700-line pipeline.js; use Sonnet high for big UI files) and log a FAIL line. Every agent brief demands a log line at least every 5 minutes.

## RULE 16: INTERNET FOR EVERY WRITER MODEL (owner, 2026-11-07)
Web context matters most for getting the story context right. `write_pack.py --web` turns it on for every model. Claude writers (Opus etc.) use WebSearch/WebFetch live. Free models (NVIDIA, OpenRouter free) get `WEB_NOTES.md` next to SOURCE.md, written once per story by a Haiku agent at low effort with web search (reused; delete the file to redo). The paid OpenRouter web plugin is not used. The story SOURCE stays the authority: the web only corrects clear fact or look mistakes and fills gaps, never adds scenes. Looks follow the traditional scripture description first, then the style pack. Final answers carry no links.

## RULE 17: LOG AND BLOT IN THE SAME STEP (owner, 2026-11-07, repeated)
Every change, even a one-line one, gets its PROJECT_LOG line in the same step, and blot.md is updated in the same step whenever a rule changes (both copies: anime_studio and anime_studio_merge).

## RULE 18: NOTHING HIDDEN, BUILT FOR A 60-YEAR-OLD (owner, 2026-11-07)
The UI user is 60. No step, action or needed fact sits behind a "More" fold, a hidden section, a hash-only link or a hover. Everything needed to move a story forward is visible on the page, in order, with large clear text. Story choice is always visible at the top. Locked future steps stay visible with the reason they are locked. Only raw technical details (file paths, logs, JSON) may sit in a fold. Supersedes rule 9's "moved or hidden": controls are MOVED, never hidden.

## RULE 19: THE CHOSEN STYLE IS ENFORCED, NOT JUST NAMED (owner, 2026-11-08)
The writer receives the WHOLE style pack (per-act look, frame law, every palette with hex and role) through `style_rules()`, and `MASTER_PROMPT_v2.3.md` rule 8 defers to it (no story's look is hard-coded). Stage 2 is gated by STYLE-01/STYLE-02 (`style_pack_errors`): an off-style bible fails and gets its repair call. Before any image work, check the bible's swatches against the pack. A new style pack field that changes the look must be added to `_look_rules` with a test.

## RULE 20: SCRIPTED EDITS ARE CHECKED FOR CONTROL CHARACTERS (2026-11-08)
After any edit made by a script (python heredoc), check the file parses and has no control characters (`grep -c $'\x08\x0c'`, `ast.parse`, `node --check`). Two such slips happened on 11-07/11-08 (a real newline inside a string, a backspace inside a regex). Prefer the Edit tool for code with escapes.

## RULE 21: EVERY STORY HAS ITS OWN FLOW FOLDER; THE PACKET IS COMPLETE (owner, 2026-11-08)
Pictures of a story live only in `flow_outputs/anime_<slug>` (`server.flow_root`; Kaliya keeps `anime_kaliya`). The server reaches only `anime_*` folders, never Granth ones. The Flow agent packet carries everything for making AND downloading (project link, aspect, edit base, neighbours, safety stops, fix loop, reviewer commands, queue, progress, phase-2 2K download); `ui/test_packet_and_roots.py` fails if any item goes missing.

## RULE 22: A STORY OTHER THAN KALIYA MUST WORK END TO END (owner, 2026-11-08)
Folders come from the story, never from the Kaliya defaults: `_project_update` sets `images_dir` to `flow_root(story)` and resets pack/results on a story switch; `facts()` reads `<flow folder>/adhyay_01`; every queue/review/neighbour/bridge/watermark command takes `story`; packet ids may be `SHOT-001` (expands to 001A/B); the Prepare button converts the pack to `<pack>/h3_story.json`. A new gap found by an audit is fixed with a test, not noted. Open gaps live in the NOW block of PROJECT_LOG.md.

## RULE 23: ONE CLAUDE CALL = THE WHOLE ANSWER (2026-11-08)
write_pack.call_claude always uses --output-format stream-json and join_stream. A long answer (thinking + bible beyond the output cap) is continued by the CLI in a second turn, and the plain json result keeps only the last turn (Kalika stage 2 lost its first part, 2.62 USD). After any Claude stage, check num_turns and that the answer parses before the next stage.

## RULE 24: LOG AFTER EVERY STEP, NO EXCEPTION (owner, 2026-11-08, repeated)
After EVERY step, including a check, a failed run, a tool call that only reads, the PROJECT_LOG.md line and (when a rule changed) the blot.md update are written in the same step. A missed line is backfilled at once with a BACKFILL line. Shell tip: no backticks inside echo text (the shell breaks and nothing runs).
