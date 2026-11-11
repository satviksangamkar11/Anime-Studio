Write ONLY the test file score/tests/test_loudness_targets.py (plain pytest, standard library, tmp_path, no network, no model call; start with sys.path.insert of its own folder and the project root so the modules import by bare name or package as the neighbouring tests do). It is the frozen test gate for this gap card; the module change is made later by someone else, so the tests must FAIL on the current code and pass on a correct implementation. Use the hand-computed values written in the card; do not copy code from the module under test. Cover every test name the card lists.

CARD:
**X-20 | stem_builder −14 → named audition constant**
- **Files:** `score/stem_builder.py`; `score/tests/test_loudness_targets.py` NEW.
- **Change:**
  - `AUDITION_NODUCK_LUFS = -14.0  # music-only audition file, not a deliverable (log 11-09 17:23)`.
  - stem_builder.py:503 `write_noduck(..., target_lufs=AUDITION_NODUCK_LUFS)`; output file name gets the suffix `_audition`.
  - If the owner chooses "one target": use `load_core()["delivery"]["audio"]["lufs"]` instead.
- **Tests:** `test_only_audition_constant_is_minus_14`: an AST scan of director/, h3/, score/ (non-test files) finds the literal −14.0 only in stem_builder's AUDITION_NODUCK_LUFS. `test_deliverables_use_core`: gate_d LOUDNESS target equals core.json lufs.
- **Closes:** 42.
- **Depends on:** none.
- **Collision:** none.
- **Acceptance:** `python -m pytest score/tests/test_loudness_targets.py -q`
- **OWNER DECISION:** confirm −14 audition-only (reverse-engineering F, downgraded).
- **Second-attempt risk:** low.

---



EXTRA HINT: Do NOT import score.stem_builder (it needs a core.json that does not exist here). Test by reading source text and AST scans only (ast.parse of the files; find Constant -14.0 nodes).