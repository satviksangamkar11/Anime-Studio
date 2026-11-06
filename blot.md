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
