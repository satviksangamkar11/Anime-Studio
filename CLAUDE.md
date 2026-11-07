Read `blot.md` first. Rule 1: after EVERY step append one short line to PROJECT_LOG.md (format in blot.md). Then read the NOW block in PROJECT_LOG.md and CHECKLIST_ARCHITECTURE_2026-11-07.md.

# LOGGING RULE (owner, 2026-11-07, repeated several times: it must never stop)
- After EVERY step, with no exception, append ONE line to `PROJECT_LOG.md` in the format of `blot.md`: every edit, test run, check, decision, failure, commit, push, upload checked, process stopped, agent start and agent finish. Do it in the same turn as the step, before moving on. If a gap appears, backfill it at once with a line marked BACKFILL (append only; never edit old lines).
- The one log file is `D:\aai work\anime_studio\PROJECT_LOG.md`. Every agent you start appends to that same file (not to a copy in a worktree). Copy it into another worktree only when you commit there.
- Every agent prompt must carry this rule and the exact command: `echo "$(date +%m-%d\ %H:%M) | <agent id> | <TYPE> | <files> | <result>" >> "D:/aai work/anime_studio/PROJECT_LOG.md"` (TYPE: CMD EDIT TEST DECISION FAIL AGENT-DONE). When an agent reports back, check that its lines are in the log.
- After every agent finish or checklist tick, overwrite the NOW block at the top of `PROJECT_LOG.md` (max 8 lines).
- The log is an audit trail: a step that is not in the log did not happen.
