# Nemotron Super merged report

# Anime-Reel Pipeline — Consolidated Review Report

## 1. PROBLEMS (deduplicated, by stage, most expensive first)

### Story/Writer
- **P6** — Pipeline hard-wired to first story (Kaliya): folders, patterns, style chip, no GPU path for V4 rows. Root cause: no per-story customization. Cost: two audits found 44 HIGH gaps, closed late.
- **C10** — Claude weekly limit hit during Opus stages; all heavy writer work on one subscription. Root cause: no budget watch. Cost: blocked work for days.
- **Q3** — Compiled H3 prompt had grammar defects, duplicate sentences, broken sentences, pronoun clashes, boilerplate repetition, curly apostrophes, jargon. Root cause: compiler glues text pieces without a language check. Cost: unknown, probably lower clip quality in every shot.
- **Q11** — Story-fidelity not checked against SOURCE.md; writer grades itself. Root cause: no independent check. Cost: risk of wrong story beats in production.
- **Gap 5** — Story gate self-graded by writer with no SOURCE.md comparison. Root cause: no automated source fidelity validation. Cost: not stated.
- **R22** — Non-Kaliya stories not working end to end. Root cause: not stated. Cost: not stated.
- **R16** — Web context missing for story accuracy. Root cause: not stated. Cost: not stated.
- **R13** — Stories without explicit style pack. Root cause: not stated. Cost: not stated.
- **R19** — Off-style bible passes without repair. Root cause: style only named, not enforced. Cost: fails and gets repair call.
- **Q4** — Visual prompt had no negative/"only these characters" line despite Flow job prompt having one. Root cause: H3 layout lacks negative or "only these characters" line. Cost: cobras, possible extra figures.
- **C8** — Opus writer stage 2 lost first 90% of answer. Root cause: CLI `result` kept only last turn. Cost: 2.62 USD.
- **C9** — Opus "repair" rewrote stage as 11 shots and failed. Root cause: repair prompt let model rewrite whole answers. Cost: one Opus call, failed stage.
- **[11-09 03:01]** — Render started without reading script. Root cause: didn't read script. Cost: stopped render, runner killed, defects found.
- **[11-09 02:50]** — Visual defect: snakes appearing. Root cause: sound cues in prompt (Q1). Cost: re-render needed (~1.2 units, ~30 min).
- **[11-08 22:30]** — h3_author failed (Claude weekly usage limit 429). Root cause: usage limit. Cost: nothing written, fell back to free model.
- **[11-09 13:40]** — Music bible SHIVA theme D2-D3 all <200 Hz = silent on phones at peak. Root cause: low notes below phone playback range. Cost: octave-up doubling fix applied.
- **[11-09 15:35]** — note_writer rejects plan_check transitions theme_handover, key_colour_on_downbeat: vocabulary clash. Root cause: cut vocabulary differs between plan_check and note_writer. Cost: forced swells on 5 soft cuts (style fault).
- **[OWNER 18:40]** — Devanagari spelling not checked properly. Root cause: not specified. Cost: not stated.
- **[11-09 13:33]** — test_note_writer.py C29 red before impl: partners test fails. Root cause: incomplete implementation. Cost: test failed.
- **[11-07 03:48 W1 FAIL]** — test_stage_1_data_carries_the_selected_languages fails after gate merge. Root cause: LANG-03 from writer fallback. Cost: not stated.
- **[11-07 04:57 B1/B4a/B5 FAIL]** — Core suite collection blocked by other workers' test files / missing modules. Root cause: missing modules from other workers. Cost: not stated.
- **[11-07 08:25 A25 FAIL]** — Linter 15 ERRORs in test_convert_deva_h3.py. Root cause: template/registry content issues (KF-02, SD-01, CM-01, PR-05). Cost: not stated.
- **[11-07 08:39]** — dots attempt 1 empty (token budget). Root cause: token budget exceeded. Cost: retry at 48000.
- **[11-07 08:49]** — unmocked call_path hit NVIDIA endpoint with fake model (HTTP 404). Root cause: probes not mocking calls. Cost: no paid, but fixed by mocking.
- **[11-07 10:33]** — r3 test pins PLAN-01 for captions_by_lang string; reverted that guard. Root cause: guard reverted. Cost: already an error entry.
- **[11-07 12:57]** — one transient failure in first final run (581 pass, 1 fail). Root cause: transient, not reproduced. Cost: total now 590 pass.
- **[11-07 13:20]** — collection error blocks full core run after wait. Root cause: not mine, reported under REQUESTS. Cost: blocks full core run.
- **[11-07 13:20]** — correction: last AGENT-DONE said 325; actual core run excluding caption_text = 331 pass, 1 skip. Root cause: misreporting. Cost: incorrect pass count reported.
- **[11-07 16:12]** — previous push ce74e37 went out with 2 failing Gate D tests; wrapper hid the failure. Root cause: cue-layer hardening coerced malformed blocks silently. Cost: fixed by raising clear ValueErrors; h3+core 1033 pass.
- **[11-07 17:03]** — 8 selectors target removed #wiz-panels (dead CSS). Root cause: dead CSS. Cost: not a visible fault.
- **[11-07 17:04]** — Gate A Approve enabled while stale-server banner says restart first. Root cause: safety gap. Cost: not stated.
- **[11-07 17:05]** — Images Shots tab shows [object Object] in Q1-Q6 cells. Root cause: fillReview String of object. Cost: not stated.
- **[11-07 17:07]** — phone Advanced toggle click did not expand. Root cause: mis-target on a Runs row. Cost: not stated.
- **[11-07 17:59]** — Write blocked by worktree path guard. Root cause: worktree path guard. Cost: both reviewer runs failed.
- **[11-07 18:47]** — Edit script failed due to backslash escapes. Root cause: backslash escapes in script. Cost: no change made.
- **[11-07 19:12]** — File not written due to worktree path guard. Root cause: worktree path guard. Cost: report delivered in handback text instead.
- **[11-07 19:27]** — Key-check command started Python REPL by mistake. Root cause: command error. Cost: hung, stopped, redoing as script.
- **[11-07 19:27]** — First background pytest left no output and no process. Root cause: not stated. Cost: rerunning with output to scratchpad.
- **[11-07 19:48]** — tokens.css ignored by .gitignore. Root cause: .gitignore pattern '*token*'. Cost: not changed, lead must add negation or force-add.
- **[11-07 20:20]** — write_pack.py story argument must be SOURCE.md path. Root cause: wrong argument type. Cost: retrying with correct path.
- **[11-07 21:00]** — UI bug: error 'Save the languages first' always shows at step 2. Root cause: not stated. Cost: not stated.
- **[11-07 21:52]** — Stray 'cat >> /dev/null' command hung on stdin. Root cause: stray command. Cost: stopped, nothing else lost.
- **[11-07 21:56]** — coderW and coderE stopped by user, cannot be resumed. Root cause: user interruption during Assay. Cost: work cancelled, partial uncommitted edits remain.
- **[11-08 20:16]** — Flow pane signed out / redirect to /about. Root cause: owner not signed in to Google Flow in the pane. Cost: stopped all jobs (0/4 done), wasted turns.
- **[11-08 20:37]** — review_shot.py cp1252 UnicodeEncodeError. Root cause: printing Devanagari characters without UTF-8 encoding. Cost: required rerun with PYTHONIOENCODING=utf-8.
- **[11-08 21:13]** — Gallery title alias (SHOT-001A__v01 on edit 1f1d26c1 vs 8aa727e3). Root cause: stale/alias title mapping in gallery. Cost: required manual
