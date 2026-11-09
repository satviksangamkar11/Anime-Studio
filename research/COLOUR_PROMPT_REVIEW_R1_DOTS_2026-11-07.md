

# BATCH prompt (dots) 11-07 18:09



## Findings

**1. HIGH — line 1 vs line 12: "no code" contradicts "run a throw-away python snippet"**
Line 1 says "You write documents only: no code, no test runs that change anything, no commits." Line 12 then demands "compute with a small throw-away python snippet you run only to print numbers." The agent cannot simultaneously obey "no code" and "run a python snippet." The agent may refuse to compute ratios (defeating the requirement) or may violate the "no code" rule.
**Fix:** Change line 1 to "You write documents only: no project code, no test runs that change anything, no commits. Throw-away computation scripts for research are permitted if they write no file and modify nothing."

**2. MEDIUM — line 3: Path inconsistency between v1/v2 and research notes**
v1 and v2 live in `D:\aai work\anime_studio_merge\docs\` but the research notes are directed to `D:\aai work\anime_studio\research\`. These are different base directories (`anime_studio_merge` vs `anime_studio`). If they are meant to be the same project tree, the notes will land in the wrong place and the lead will not find them.
**Fix:** Confirm the correct base path and unify it — either write notes to `D:\aai work\anime_studio_merge\research\...` or change the v1/v2 paths to `anime_studio\docs\...`.

**3. MEDIUM — line 12: Missing instruction to read test files for "Test plan" style**
Line 12 requires a "Test plan using the existing test suite style (the ui tests are pytest files in `ui/`)." But the agent is never told to inspect those test files. It only knows to inspect `index.html`, `style.css`, `app.js`, `pipeline.js`, `i18n.js`. Without reading the actual pytest files, the agent cannot match the existing style.
**Fix:** Add to the inspect list (line 6) or the research to-do (line 10): "read-only inspect `ui/test_*.py` to learn the existing test suite style."

**4. MEDIUM — line 16: Missing explicit instruction to read the redesign plan**
Line 16 requires reporting "any conflict between the guide and the redesign plan (`docs/UI_REDESIGN_PLAN_2026-11-07.md`)." But the agent is never told to read that file. It is only told to read v1 and the UI source files. The agent may not think to open the redesign plan and will miss conflicts.
**Fix:** Add to the "Read first" list: "also read `docs/UI_REDESIGN_PLAN_2026-11-07.md` for conflict detection."

**5. LOW — line 14: Logging format pipe delimiter vs "no pipe character inside the result"**
The log format uses `|` as a field delimiter: `... | colourRes(haiku,xhigh) | TYPE | files | result`. It then says "no pipe character inside the result." If the agent's result text naturally contains a `|` (e.g., "WCAG 1.4.3 | 1.4.6"), the log line will break. The constraint is confusing because it restricts content to satisfy a format, rather than the format being robust.
**Fix:** Change the delimiter to a character unlikely in file paths and results (e.g., `@@`) or remove the "no pipe" restriction and use a quoted format.

**6. LOW — line 3: No explicit "do not modify v1" rule**
Line 3 says to write v2 to a different file and "keep [v1] unchanged," but the only enforcement is the different output path. If the agent misreads the path or overwrites by accident, v1 is lost. No explicit prohibition exists.
**Fix:** Add "Do not open v1 for writing; open it read-only" to the RULES section (line 14).

**7. LOW — line 12: "Keep section 6 and Git safety rules word for word" without locating them**
The instruction assumes the agent can find "section 6 (protect animation output)" and "the Git safety rules" inside v1. If v1's section numbering differs or the Git rules are in an appendix, the agent may struggle to extract them verbatim without explicit guidance.
**Fix:** After reading v1, state the exact section heading or line range for each, or paste the Git safety rules inline so the agent can copy them unchanged.

FINAL: 7 findings (1 high, 3 medium, 3 low)
