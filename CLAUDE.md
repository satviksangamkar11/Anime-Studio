Read `blot.md` first. Rule 1: after EVERY step append one short line to PROJECT_LOG.md (format in blot.md). Then read the NOW block in PROJECT_LOG.md and CHECKLIST_ARCHITECTURE_2026-11-07.md.

# LOGGING RULE (owner, 2026-11-07, repeated several times: it must never stop)
- After EVERY step, with no exception, append ONE line to `PROJECT_LOG.md` in the format of `blot.md`: every edit, test run, check, decision, failure, commit, push, upload checked, process stopped, agent start and agent finish. Do it in the same turn as the step, before moving on. If a gap appears, backfill it at once with a line marked BACKFILL (append only; never edit old lines).
- The one log file is `D:\aai work\anime_studio\PROJECT_LOG.md`. Every agent you start appends to that same file (not to a copy in a worktree). Copy it into another worktree only when you commit there.
- Every agent prompt must carry this rule and the exact command: `echo "$(date +%m-%d\ %H:%M) | <agent id> | <TYPE> | <files> | <result>" >> "D:/aai work/anime_studio/PROJECT_LOG.md"` (TYPE: CMD EDIT TEST DECISION FAIL AGENT-DONE). When an agent reports back, check that its lines are in the log.
- After every agent finish or checklist tick, overwrite the NOW block at the top of `PROJECT_LOG.md` (max 8 lines).
- The log is an audit trail: a step that is not in the log did not happen.

# BIG MISTAKES WE MADE: READ BEFORE ANY RENDER, FLOW BATCH OR AGENT LAUNCH (owner, 2026-11-09)
Full list with costs and causes: `MISTAKES_AND_LESSONS.md` (same folder as `blot.md`). The short version, every line cost real compute units, hours or both:
- RENDER: prove within 3 minutes of `--go` that the script started (`colab ls /content` shows `out/`), else stop the session. Attempts 1 and 2 of reel 1 billed a G4 for nothing because a 19.7 MB and an 11.3 MB `run.py` never reached the VM (`colab exec -f` hangs above about 7 MB on this PC: upload in 3 MB parts, keep run.py small).
- SAVE CLIPS AT ONCE: every clip is copied to the PC the minute its shot ends. On 2026-11-05 six finished clips were lost because the final download failed.
- ONE SHOT FIRST: a dry run only prints commands. Run ONE shot for real and look at its clip before the full batch. A blank line in our H3 prompt made every shot fail in 10 seconds (Wan2GP reads a blank line as a second request).
- ALWAYS stop the Colab session and check `colab sessions` and `colab usage` after every run. The proven GPU is the G4, never an A100 or T4 (the T4 in the list is the owner's own browser notebook). Do not touch the session that is not ours. A failed fetch keeps the session on purpose: stop it by hand once the clips are home.
- REVIEW the render script with ALL reviewers (Nemotron Super VL, Xing) BEFORE `--go`, fix, then start (note N3, blot R28). Nemotron Super on NVIDIA needs slices of about 10 KB or it burns every token thinking.
- KEYFRAMES: open every kept picture at FULL size; the reviewer is advisory. A and B are the START and END frame of one shot, not two options: make B (or A) as an EDIT of the other so set, poses and props agree (note N4; shot 8 of reel 1 had Brahma standing in A and seated in B and the set morphed). Reworks: one reference chip, exact change list, Nano Banana Pro; never ask for one open and one closed eye.
- FLOW AGENTS: own tab, `tabId` on every action, retire before you rename, one tile per title, screenshot before a click (the "More options" button sits at x=668, not 615). The browser pane holds about 9 tabs; close the tabs of finished agents. One agent without `tabId` renamed the whole project.
- CODE: never edit code that contains backslashes with a python heredoc (it turned `\n` into real line breaks at least 8 times). Use the Edit tool and `ast.parse`. Read test output yourself.
- LOG: write the line after reading the result; a correction is a new FIX line; kill processes by PID, not by a command-line pattern that matches your own shell.
- LIMITS: the Claude weekly limit can block Opus and Sonnet for days (this time it was hit on 2026-11-08 and resets on 2026-11-12 at 15:30). Plan authoring and reviews on the free Super model.
- WHEN THE OWNER SAYS STOP: stop everything first, then answer.
