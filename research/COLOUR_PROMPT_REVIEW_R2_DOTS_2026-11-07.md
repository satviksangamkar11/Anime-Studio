

# BATCH prompt (dots) 11-07 18:47



## Reasoning

I reviewed the instruction prompt line by line for concrete, actionable defects: contradictions the agent cannot resolve, file-overwrite risks, missing safety rules, path errors, and conflicts with the running UI redesign.

**High-severity findings:**

1. **Path inconsistency (line 16).** The log command writes to `D:/aai work/anime_studio/PROJECT_LOG.md`, but every other path in the prompt uses `anime_studio_merge` (lines 5, 8, 14). The log will land in the wrong directory tree or fail if the directory does not exist, breaking the mandatory logging rule.

2. **Git-safety contradiction in the deliverable (line 14 + line 16).** The agent must copy v1 section 1 (GIT SAFETY RULES) word for word into v2, yet the agent itself is bound by no-commit/no-push. The prompt says the agent's rule "overrides" v1's steps, but it never instructs the agent to add a clarifying note around the copied section. Without that note, v2 will contain contradictory instructions for any reader.

**Medium-severity findings:**

3. **File-overwrite risk (line 5).** The v1 and v2 filenames differ by only `_v2` (`UI_COLOUR_SYSTEM_GUIDE_2026-11-07.md` vs `..._v2.md`). A path typo or copy-paste error could overwrite the only copy of v1. No backup or restore instruction is given.

4. **Logging rule doesn't cover non-Bash steps (line 16).** The rule says "after every step run with the Bash tool," but WebSearch and WebFetch steps are not Bash commands. The agent has no guidance on how to log those steps.

5. **Fragile pipe-character rule (line 16).** The log format uses pipe separators and forbids pipes in the `result` field, but natural step descriptions (e.g., "searched \| found \| analysed") will break the format with no fallback.

**Low-severity findings:**

6. **No prioritisation of ~10 research areas (line 12).** The research scope is very broad with no length cap or priority order for the v2 document.

7. **Table placement unspecified (line 8).** The "what exists / what does not" table is requested for the agent's understanding but its placement in v2 is not stated.

---

FINAL:
- HIGH, line 16, PROJECT_LOG.md path uses `anime_studio` while all other paths use `anime_studio_merge` — the mandatory log will be written to the wrong directory tree or fail; fix the path to `D:/aai work/anime_studio_merge/PROJECT_LOG.md`.
- HIGH, line 14 + line 16, copying v1 section 1 (GIT SAFETY RULES) word for word embeds commit/push instructions in v2 that directly contradict the agent's no-commit/no-push rule, and the prompt does not instruct the agent to add a clarifying override note around the copied section — add an explicit instruction to wrap the copied section with a v2-only override notice.
- MEDIUM, line 5, v1 and v2 filenames differ by only `_v2` suffix with no backup or restore instruction — add a rule to write v2 to a temporary name first, verify, then rename, or to keep a backup copy of v1 before writing.
- MEDIUM, line 16, "after every step run with the Bash tool" does not account for WebSearch/WebFetch steps that are not Bash commands — add a logging alternative for non-Bash steps (e.g., a separate log entry using a Bash echo after the web tool call).
- MEDIUM, line 16, "no pipe character inside the result" is fragile with no fallback — instruct the agent to replace pipes in step descriptions with a safe separator (e.g., `;`) or use a different log format.
- LOW, line 12, ~10 research areas with no prioritisation or length cap for v2 — add a priority order or word-count guidance.
- LOW, line 8, the "what exists / what does not" table placement in v2 is unspecified — state whether it goes in an appendix, a dedicated section, or is for the agent's notes only.
