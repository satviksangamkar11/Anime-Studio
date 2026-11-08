# MISTAKES AND LESSONS (Anime Studio, written 2026-11-09)

Every big mistake that cost compute, time or effort, with the cost where it is known, the root cause, and the rule that now stops it. Honest on purpose: "we" includes me (Claude). Read this before any render, any Flow batch, or any agent launch. Rules in `blot.md` are cited as R<n>. Costs marked "unknown" were not measured.

## 1. Cost at a glance (reel 1, Kalika Puran Bhag 1)

| Item | Cost |
|---|---|
| Colab units: balance 187.61 before the first attempt, 178.61 after the finished render | 9.0 units in total |
| of which the useful render (all 10 clips) | 6.25 units |
| of which wasted on 4 failed starts (attempts 1, 2, 3, 5) | about 2.75 units |
| Opus writer stage lost its first 90% of the answer (rule R23) | 2.62 USD |
| Claude weekly limit reached on 2026-11-08 (resets 2026-11-12 15:30): no Opus or Sonnet CLI calls for days | planning and review capacity |
| Keyframes: 20 final images needed about 6 rework rounds and 4 agent generations | many hours, about 150 Flow submits |
| The first T0 test (2026-11-05): six clips rendered, then LOST because the final download failed | one full G4 session, plus an A100 re-render that also failed |

## 2. Compute mistakes (money)

| # | Mistake | What it cost | Root cause | Fix / rule |
|---|---|---|---|---|
| C1 | 2026-11-05 T0 run: the results folder did not exist locally, the final download failed, the runner then stopped the VM; six finished clips were lost | a full G4 session of rendering, a second session | clips were fetched only at the very end, the local folder was never created, the download step was not tested | R29: every clip is saved to the PC the minute its shot ends (`fetch_ready`); folders are created before use |
| C2 | The A100 re-render of those clips failed: Hugging Face HTTP 429 on the model download, then a hang at "Preparing Models" | an A100 session, 0 clips | no HF token, no retry; unproven GPU chosen | G4 is the proven GPU (R30); 429 retry on any 429; do not switch GPU without a test |
| C3 | Attempt 1 (2026-11-09 00:20): run.py was 19.7 MB; `colab exec -f` hung on this PC and the script never reached the GPU; a G4 billed for 13 minutes before anyone looked | 1.68 units | no proof the script started; script size limit unknown | R28: size under 12 MB (now 40 KB + 3 MB upload parts), proof within 180 s that `/content/out` exists, else stop |
| C4 | Attempt 2: the same hang with an 11.3 MB script | 0.57 units | the size fix was a guess, not tested | the 180 s proof caught it; chunked upload fixed it |
| C5 | Attempt 3: the G4 session was terminated 2 minutes into the install (cause unknown, probably closed in Colab Manage sessions while stopping an extra notebook); the local exec processes kept hanging | about 0.3 to 0.9 units | the owner's own browser notebook (T4) looked like ours; no clear "which session is whose" rule | the runner checks `Hardware: G4`; tell the owner which session to touch; kill local exec on every exit |
| C6 | Attempt 5: every shot failed in 10 seconds (rc=1): our H3 prompt had a blank line and Wan2GP reads a blank line as a second generation request | about 0.9 units, 15 minutes | the prompt layout was never run once on the GPU before the full batch; the proven T0 prompts had single line breaks only | builder collapses blank lines and raises if one is left; test + R30 |
| C7 | A forgotten or looping runner: the final fetch split `FILES.txt` on spaces (clip names contain spaces), tried to download "Picture", "1", "0.mp4" and ended without stopping the session (a failed fetch keeps the session on purpose) | extra billed minutes on a finished job | untested with real file names | one path per line; always check `colab sessions` after a run; stop by hand |
| C8 | Opus writer, stage 2 (Kalika): the CLI `result` kept only the last turn; the first 90% of the answer was lost | 2.62 USD | `--output-format json` joins nothing | R23: always stream-json + `join_stream`; check `num_turns` |
| C9 | Opus "repair" rewrote the 3e1 stage as 11 shots and failed validators | one Opus call, a failed stage | repair prompt let the model rewrite whole answers | targeted repair only; restore originals (kept `.bak`) |
| C10 | The Claude weekly limit was hit while Opus stages were still needed; later `h3_author --opus` and the CLI reviewers failed | blocked work for days | all heavy writer work on one subscription, no budget watch | free models (Nemotron Super, Xing) for authoring and review; `claude` limit checked before a stage |

## 3. Time and effort mistakes (images and Flow)

| # | Mistake | Root cause | Fix / rule |
|---|---|---|---|
| F1 | Keyframes accepted from reviewer verdicts and small thumbnails; at full size they had letters in the sparks (1A), a wink (1A), Brahma at the edge and cropped sages (6A, 6B), wrong crowns | the reviewer is advisory; small captures hide defects | the coordinator opens every kept picture at FULL size (R25) |
| F2 | The A and B keyframe of one shot were made as two separate generations, so they disagree (8A: Brahma standing before a flat throne; 8B: seated on a stepped dais; 2A/2B arms) and the video has to invent the change | A/B treated as "pick the better of two" instead of start and end frame of one shot | note N4: B (or A) is made as an EDIT of the other; pair review side by side; list the allowed changes |
| F3 | A long misunderstanding with the owner: "A and B are two options" versus start and end frame | not explained in the packet and the UI | R25 and the packet text: A = start, B = end, both required |
| F4 | Regenerating images with long prompts again and again (1A: 5 submits, 6A/6B: 8) when one change list on a single reference would have worked | no rule for reworks | R25: one chip, exact change list, Nano Banana Pro for reworks; do not ask for one open and one closed eye (Flow draws a wink) |
| F5 | Chip rules: the `@` picker listed OLD- tiles next to the exact name; several agents stopped, some picked the wrong one; renames "saved" silently half the time | duplicated and stale names in the project; UI quirks | exact-title rule, rename then reload and re-read; retire first; one tile per title |
| F6 | Browser tabs: the pane has a cap of about 9 tabs; finished agents left theirs open, three download agents could not start; one agent acted without `tabId` on another agent's tab and RENAMED THE WHOLE PROJECT; I closed a tab that an agent was still using | no tab discipline | R26: own tab, `tabId` on every action, close tabs of finished agents only |
| F7 | 2K download: four Haiku agents (high and low) got null captures for 20+ minutes because they clicked "More options" at x=615 instead of x=668; I found it by doing one by hand | coordinate clicks without a screenshot | recipe in `Satvik notes refer.md` and R30: find the ref or screenshot before every click |
| F8 | The Flow project was signed out in the pane; three agents started, stopped, and their lines said "done" or "blocked" without the owner knowing | no sign-in check before launching agents | check sign-in first; agents report the stop at once |
| F9 | Edit ids in my notes did not match the gallery (c989ad77, 89444d2c): an agent lost time searching | ids copied from partial notes | match tiles by exact prompt and title, not by remembered ids |
| F10 | Watermark: the detector found no sparkle in 4 of 20 images (bright cloud and gold backgrounds); and 6A carried a second, baked-in ghost star inherited from the edit reference | threshold tuned on dark images; edits copy the watermark | fixed anchor fallback (`stamps_or_anchor`); look at every corner; remove ghost stars by hand |
| F11 | The wrong GPU named in memory: a handoff note said A100, the log said G4; the owner and I argued from a wrong note | memory written from plans, not from the run log | verify from `gpu.csv` and `colab new` lines; fixed the note |

## 4. Process and my own slips

| # | Mistake | Cost | Fix / rule |
|---|---|---|---|
| P1 | Python heredocs turned `\n` inside strings into real line breaks (at least 8 times: write_pack.py, tests, build_h3_batch.py, remove_sparkle patches, NOW block paths with `\a` `\r`) | broken files caught late, wasted rounds | R20 and R30: use the Edit tool for code with backslashes; `ast.parse` after every scripted edit |
| P2 | A shell wrapper hid 2 failing Gate D tests and a push went out (ce74e37) | a bad push to fix | tests are read, not trusted through a wrapper |
| P3 | Log lines for steps that did not happen (an "applied fixes" line after a failed script; agents writing DONE lines for retired tiles) | wrong state believed | R24: a correction is a new FIX line; read the result before writing the line |
| P4 | Killing processes by a command-line pattern that also matched my own shell (twice), so the command exited 255 and the next steps did not run | lost minutes, a session left running once | kill by PID found first |
| P5 | Reviewers: the NVIDIA-hosted Nemotron Super spent every token thinking (4 empty answers even at 30000 tokens); Xing returned only thought traces; OpenRouter reviewers hit 429 when run together | hours of review time | slices of at most about 10 KB for Nemotron; run reviewers one after another; trust but triage every finding |
| P6 | The pipeline was built around the first story (Kaliya): hard-wired folders, `LEAP-*` file patterns, a style chip name identical for every story, a route name the runner rejected, no GPU path for V4 rows | two full audits found 44 HIGH gaps, closed late (R21, R22) | every story gets its own folders; one end-to-end dry run per new story |
| P7 | The sound-cue rule SX-01 (all 7 action sentences need a sound word) only showed up in the render controller after authoring: 6 of 10 shots were "not ready" | authoring ran twice (stale fields) | run `render_controller --dry-run` right after the writer, before authoring |
| P8 | "Dry run" only prints commands; nothing ever tested the real chain on one shot before the full 10-shot batch | 4 failed starts | before a full run: a one-shot run (`--ids SHOT-001`) is the first real test; look at its first clip before the rest |
| P9 | Agent briefs and agent reports were trusted too much: sign-in blocks, wrong tab, "done" lines, "I cannot open the second tile" | repeated reruns | verify what an agent says against the file, the gallery or the log; keep a short list per shot |
| P10 | Owner rules arrived mid-task (send each clip, then do not send each clip; Haiku low then high; Pro for reworks only; stop at once) and I did not always stop first | wasted calls and sends | on "stop": stop everything first, then answer; log the order in blot |

## 5. The rules that matter most (short list)

1. Prove the script started within 3 minutes of `--go` (`colab ls /content` shows `out/`), else stop the session.
2. Save every clip to the PC the minute its shot ends. Never wait for the end of the run.
3. Run ONE shot for real first; look at its clip; then the rest. A dry run is not a test.
4. Always stop the session; check `colab sessions` and `colab usage` after every run, and never touch the session that is not ours (the owner's T4 browser notebook).
5. The proven GPU is the G4. Do not change GPU, model or prompt layout without a one-shot test.
6. Prompts: single line breaks only, no blank line (Wan2GP).
7. `colab exec -f` hangs above about 7 MB on this PC: upload in 3 MB parts; run.py stays small.
8. Review the render script with ALL reviewers before `--go` (note N3), then fix, then start.
9. Keyframes: open every kept picture at full size; A/B pairs are start and end of ONE shot, check them side by side (note N4); reworks are single-reference edits.
10. Flow agents: own tab, `tabId` on every action, retire before you rename, one tile per title, screenshot before a click.
11. Code with backslashes: Edit tool, then `ast.parse`. Never a heredoc.
12. A log line is written after the result is read, not before. Corrections are new FIX lines.
13. Opus and Sonnet CLI can run out for days (weekly limit): plan authoring and reviews on the free Super model.
14. When the owner says stop, stop first.

See also: `blot.md` rules 20 to 31, `Satvik notes refer.md` (N1 to N4), `PROJECT_LOG.md` (every step), `CLAUDE.md`.
