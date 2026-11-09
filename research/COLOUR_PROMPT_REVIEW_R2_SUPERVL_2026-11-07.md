

# BATCH prompt (supervl) 11-07 18:47

Reviewing the prompt for real defects only.

Finding 1:
- Severity: medium
- File:line: `_prompt_colour_research.md:16` (conflicts with `:5` and `:14`)
- Why: The mandatory per-step logging rule appends to `D:/aai work/anime_studio/PROJECT_LOG.md`, but every deliverable lives under `D:\aai work\anime_studio_merge\docs/` and `...\research\`. The `anime_studio` folder (without `_merge`) is a different tree and may not exist, so the owner logging rule would fail on every step or write outside the intended tree; backslash and forward-slash path styles are also mixed.
- Fix: Retarget the log to the same tree, e.g. `D:\aai work\anime_studio_merge\PROJECT_LOG.md`, and use one consistent path style.

Finding 2:
- Severity: medium
- File:line: `_prompt_colour_research.md:16` (conflicts with `:5` and `:8`)
- Why: Line 16 says "do not touch `ui/`", but lines 5 and 8 require reading `ui/test_*.py` and read-only inspecting `ui/static/` files. "Touch" is ambiguous, so the agent may wrongly skip required inspection or treat permitted reads as forbidden.
- Fix: Clarify that "do not touch `ui/`" means do not modify or create files there, and that read-only inspection of `ui/test_*.py` and `ui/static/` is required and allowed.

No other real defects: git/secrets/paid-call/server safety rules are present, v1 is protected read-only, the two new deliverable filenames cannot overwrite v1, the redesign conflict rule (do not edit `style.css`/`index.html`) is explicit, and the anti-hallucination/source rules are strong.

FINAL: 2 findings — (medium) `_prompt_colour_research.md:16` log path `D:/aai work/anime_studio/PROJECT_LOG.md` mismatches the `anime_studio_merge` deliverable tree and mixes slash styles, so mandatory logging can fail; (medium) `_prompt_colour_research.md:16` "do not touch `ui/`" contradicts required read-only reads of `ui/test_*.py` and `ui/static/` at lines 5 and 8.
