

# BATCH prompt (dots) 11-07 18:55



**Findings:**

1. **HIGH** — `prompt:17` — The LOGGING path `D:/aai work/anime_studio/PROJECT_LOG.md` uses a different root (`anime_studio` vs `anime_studio_merge`) and forward slashes, while every other path in the prompt references `D:\aai work\anime_studio_merge\`. The log would be written to a non-existent or wrong directory, making the mandatory step-tracking invisible to the owner.  
   **Fix:** Change the LOGGING path to `D:/aai work/anime_studio_merge/PROJECT_LOG.md` (or `D:\aai work\anime_studio_merge\PROJECT_LOG.md`).

2. **MEDIUM** — `prompt:5` — The research-notes deliverable targets `D:\aai work\anime_studio_merge\research\COLOUR_RESEARCH_NOTES_2026-11-07.md`, but the `research/` directory may not exist and the prompt never authorizes creating it. The agent is told "write only the two deliverable files" and "do not edit any other file," creating a deadlock: the file cannot be written without creating a directory, which is not explicitly permitted.  
   **Fix:** Add an explicit authorization to create the `research/` directory if it does not exist, or pre-create it before sending the prompt.

3. **MEDIUM** — `prompt:15` — The instruction says "copy v1 section 1 (IMPORTANT GIT SAFETY RULES) word for word, but this prompt's no-commit/no-push rule overrides any step in it that would need a commit." If v1 section 1 contains steps like "commit this document" or "push the branch," copying it verbatim while also overriding those steps creates a contradictory document unless the agent carefully annotates every conflicting line. The prompt does not specify *how* to mark the override (e.g., a `[v2: override]` tag per line vs a single blanket note), leaving room for an inconsistent v2 document.  
   **Fix:** Specify the annotation format (e.g., "prefix each overridden line with `[v2: no-commit override]`").

4. **LOW** — `prompt:9` — The prompt provides pre-computed contrast ratios "computed by the lead" but simultaneously instructs the agent to "compute with a small throw-away python snippet." If the agent's computation differs from the lead's numbers (e.g., due to rounding or a different WCAG formula), there is no guidance on which set to publish in v2 or how to resolve the discrepancy.  
   **Fix:** Add a line: "If your computation differs from the lead's, publish both with a note explaining the difference."

5. **LOW** — `prompt:13,15` — The rule "Every claim in v2 gets a source URL and a confidence tag" does not account for claims that are owner requirements rather than research findings (e.g., "the main user is a 60-year-old non-technical woman" or the lead's assumed 4.77 ratio). These cannot have a source URL. The prompt says to write "not found" for missing studies, but does not provide a tag for "owner assumption" or "lead input."  
   **Fix:** Add an allowed confidence tag: `owner-assumption` or `lead-input`, with no URL required.

6. **LOW** — `prompt:8,15` — Line 8 asks for a "what exists / what does not" table of real screens, and line 15 asks for an "Applies to this app" section covering "real screens, files, order." These overlap substantially and could result in duplicated content in v2, wasting effort and creating inconsistency.  
   **Fix:** Merge them into a single "Applies to this app" section that includes the existence table.

**FINAL: 6 findings (1 HIGH, 1 MEDIUM, 4 LOW)**
