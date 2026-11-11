# Nemotron Super review of S-10 (rule 55), supervisor test run: 33 passed in 0.27s

ROWS:
"Files: director/script_hook.py, director/test": PASS
"Change:": PASS (heading only, no requirement)
"Public validate_shots(shots) extends _validate": PASS — `validate_shots` calls `_validate_shots` first, then adds event/line checks; `inspect_hook` calls `validate_shots`.
"every event is a dict with": PASS — `event` dict check, `"t" not in event`, `_is_finite_number(event["t"])`, `event["t"] < 0` refused.
"every line is a dict with": PASS — line dict check, finite `start_s`/`end_s`, `start_s > end_s` refused, `text` must be `str`.
"otherwise ValueError naming the shot": PASS — event/line raises include `"shot " + shot_id + ...`.
"remove the defaults event.get": PASS — code uses `event["t"]` and `lines[0]["start_s"]`; no `.get("t"` / `.get("start_s"` defaults remain.
"A first shot with no spoken": PASS — `if not lines:` adds exact H2 string to `hard_fails`/`reasons`, score -= 40.
"_is_opener matches whole tokens with": PASS — `_phrase_matches(tokens[:opener_len], opener)` on `_tokens(line)`; no `startswith`.
"Tests:": PASS (heading only)
"test_no_first_line_hard_fail": PASS — in the 33-passed run.
"test_event_without_t_raises": PASS — in the 33-passed run.
"test_non_dict_event_raises": PASS — in the 33-passed run.
"test_it_was_a_timeline_not_opener": PASS — in the 33-passed run.
"test_once_upon_a_time_is_opener": PASS — in the 33-passed run.
"Update the tests that relied": PASS — no existing fixture relied on removed defaults; all set `t`/`start_s`/`end_s`.
"Problems: advances 15 (closes with": PASS (informational row)
"Depends on: none. Shared": PASS (informational row)
"Acceptance: python -m pytest director": PASS — supervisor run: `33 passed in 0.27s`, 0 failed.
"Waits on: none.": PASS (informational)
"Second-attempt risk: low.": PASS (informational)
"No reel 1 file is edited": PASS — only the two named files touched by S-10.
"No network, Colab, ElevenLabs, renderer": PASS — pure-Python, synthetic fixtures.
"Every changed .py file parses": PASS — ast check reported ok; no line > 120 chars; Edit tool only.
"The card's acceptance command was": PASS — full result pasted (33 passed).
"Every test named in the card": PASS — all named tests exist, ran, passed.
"Nothing was deleted from the": PASS — only 5 tests appended; old text verbatim.
"One log line was appended": PASS (informational)

UNTICKED:
"[ ] Only the files named in this card were changed …" — reason acceptable: S-10 itself touched only the two named files; the other worktree changes (`blot.md`, `director/test_clip_gates.py`, untracked `director/*.py`, `HANDOFF_2026-11-10.md`) are from other sessions, so leaving it unticked per the strict rule is correct.

MISSING: none — every required item in the card is implemented.

EXTRA: none.

BAD: `_has_stakes` returns `True` for any line containing "?" or "？" (`script_hook.py`, `_has_stakes`: `if "?" in line or "？" in line: return True`), conflating stakes with questions. It is behaviorally masked by H3's `stakes or question` OR, but the function itself is wrong and would misreport stakes in isolation. Fix: delete the `if "?" in line or "？" in line: return True` block from `_has_stakes` so it only matches real stakes words/phrases (questions are already handled by `_has_question`).

VERDICT: DONE (no ticked row fails; all 33 tests pass; the single BAD is a code-quality fix, not a failing row).
