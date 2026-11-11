# Nemotron Super review of S-05 (rule 55), supervisor test run: 46 passed in 0.06s

ROWS:
Files: h3/prompt_hygiene.py h3/tests/test_prompt_hygiene.py: PASS
Replace return f"While {join_names(on_screen)} keep their: PASS (code now returns `f"{join_names(on_screen)} keep their lips completely closed."` — "While" removed)
Mouth and cast go into the body line: PASS (clean_prompt appends `mouth` + `cast` to the first line starting with BODY_PREFIXES and raises PromptError("no body line") otherwise; music line stays last)
Exactly one mouth sentence (Opus 10d): PASS (imports MOUTH_LOCK_SENTENCE, removes it via .replace, and _drop_mouth_sentences removes `\bmouth stays (?:closed|shut)\b` IGNORECASE sentences)
check_sound_cue: a visible entry also counts: PASS (visible_normalised lowercased; raises only if neither noun nor noun±s other_form is visible; "serpents hiss" with visible ["serpent"] → other_form "serpent" present → no raise)
Blank lines stay collapsed (problem 30: PASS (collapse_blank_lines normalises CRLF, rstrip(" "), drops empty lines; clean_prompt ends with collapse_blank_lines)
test_mouth_no_while: (["Kama","Rati"], []) →: PASS (mouth_sentence(["Kama","Rati"],[]) == "Kama and Rati keep their lips completely closed."; test in the 46 passed)
test_clean_prompt_keeps_section_order: 5-line FL2VA: PASS (in 46 passed; code preserves section order and appends mouth+cast to body line)
test_single_mouth_sentence: input containing MOUTH: PASS (in 46 passed; MOUTH_LOCK_SENTENCE removed, one "lips" sentence remains)
test_no_blank_line_in_output: PASS (in 46 passed)
test_visible_plural_ok: cue "serpents hiss": PASS (in 46 passed; verified logic above)
Depends on: none. Shared files: none: PASS (status row, no contradiction)
Acceptance: python -m pytest h3/tests/test: PASS (supervisor result: 46 passed in 0.06s)
No reel 1 file is edited or opened: PASS (status row)
Only the files named in this card: PASS (status row)
No network, Colab, ElevenLabs, renderer: PASS (code has no such calls)
Every changed .py file parses (ast.parse): PASS (tests ran/imported cleanly)
The card's acceptance command was run: PASS (46 passed result present)
Nothing was deleted from the existing tests: PASS (status row)
One log line was appended to D:/aai: PASS (status row)

UNTICKED:
- Change: (category header) — sub-rows individually ticked and verified; acceptable.
- Tests: (category header) — sub-rows individually ticked and verified; acceptable.
- Problems: advances 26, 27, 28, 30 ... Bugs O10a/b/d/e — status/tracking only, no code contradiction; acceptable.
- Waits on: D3 — dependency note only; acceptable.
- Second-attempt risk: medium — status note only; acceptable.
- Every test named in the card exists, was run, and passed ... — unticked, but supervisor result (46 passed) includes all five named card tests, so substance is satisfied; acceptable/non-blocking.

MISSING: none — every card requirement reflected in the code.
EXTRA: none — no unrequested functionality added.
BAD: NONE — no wrong, fragile, or silently-passing-bad-input code found; all ticked behaviours verified against the code and the 46-passed result.
VERDICT: DONE
