

# BATCH prompt (supervl) 11-07 18:09

high, _prompt_colour_research.md:14 — RULES says "write only the two files named above," but LOGGING in the same line requires appending to `D:/aai work/anime_studio/PROJECT_LOG.md` after every step, i.e. a third file; the agent cannot obey both. Fix: exempt the log, e.g. "write only the two deliverable files; the PROJECT_LOG.md append required by LOGGING is exempt."

high, _prompt_colour_research.md:6 vs :12 — line 6 says v2 lists only real screens and marks non-applicable sections "not present," but line 12 orders section 6 "protect animation output" be kept word for word; the context has no animation/timeline/scene screen, so a non-applicable section cannot be both "not present" and verbatim. Fix: declare section 6 and the Git safety rules as owner-protected exceptions to the "not present"/real-screens rule.

medium, _prompt_colour_research.md:3 and :14 — the v1 guide and app live under `D:\aai work\anime_studio_merge\...`, but the research notes target `D:\aai work\anime_studio\research\...` and the log targets `D:/aai work/anime_studio/PROJECT_LOG.md`, a different root that may not exist and would split deliverables. Fix: unify notes and log under `D:\aai work\anime_studio_merge\...` (or confirm the `anime_studio` root exists).

medium, _prompt_colour_research.md:10 — the task presupposes "the 2025 light-green background reading study named in the guide" exists; if v1 does not name it, the agent is pushed toward inventing a citation/study despite the honesty rule. Fix: rephrase to "if the guide names a 2025 light-green background reading study, find it …; otherwise write 'not found'."

medium, _prompt_colour_research.md:12 vs :14 — line 12 requires keeping v1's "Git safety rules" word for word (unseen here), while line 14 forbids commit/push/stash/branch; if v1's Git rules require committing, the agent cannot satisfy both. Fix: state that line 14's no-commit rule overrides, or quote the Git safety rules in this prompt for consistency.

FINAL: 5 findings — high: :14 two-file limit vs mandatory PROJECT_LOG.md append; :6 vs :12 "not present" rule vs keep section 6 word for word; medium: :3/:14 anime_studio vs anime_studio_merge root split; :10 presupposed 2025 light-green study risks invented citation; :12 vs :14 Git safety rules word for word vs no-commit rule.
