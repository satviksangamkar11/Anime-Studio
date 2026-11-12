The card lists tests for L11–L17, but the test file omits coverage for L14 (beats), L15 (caption-safe), L16 (hook_type), and L17 (chain_from) — the test names exist only for L11–L13. That means the required per-code tests are missing.

**Exact faulty line (in `director/test_blocking_11.py`):** the test functions `test_l14_*`, `test_l15_*`, `test_l16_*`, and `test_l17_*` are absent; only `test_l11_*`, `test_l12_*`, `test_l13_*` are present.

**Exact fix:** add the missing tests:

```python
def test_l14_beats_two_to_four_with_gaps_and_one_primary():
    sheet = _with_hook(_ex())
    assert "L14" not in _codes(_lint_one(sheet))
    sheet = _with_hook(_ex()); sheet["beats"] = sheet["beats"][:1]
    assert "L14" in _codes(_lint_one(sheet))
    sheet = _with_hook(_ex()); sheet["beats"][1]["t"] = 1.0
    assert "L14" in _codes(_lint_one(sheet))
    sheet = _with_hook(_ex()); sheet["beats"][2]["primary"] = True
    assert "L14" in _codes(_lint_one(sheet))
    sheet = _with_hook(_ex()); sheet["beats"][2]["t"] = 6.0
    assert "L14" in _codes(_lint_one(sheet))

def test_l15_speaking_face_below_caption_line_flagged():
    sheet = _with_hook(_ex())
    sheet["cast"][0].update({"speaks": True})
    sheet["cast"][0]["start"]["mouth_moves"] = True
    sheet["cast"][0]["end"]["mouth_moves"] = True
    assert "L15" in _codes(_lint_one(sheet))
    sheet["cast"][0]["start"]["y"] = 0.60
    sheet["cast"][0]["end"]["y"] = 0.60
    assert "L15" not in _codes(_lint_one(sheet))

def test_l16_first_shot_needs_a_hook_but_later_shots_do_not():
    first = _shot("SHOT-001", 4.0, hook=None)
    assert "L16" in _codes(blocking_lint.lint([first]))
    first = _shot("SHOT-001", 4.0, hook="none")
    assert "L16" in _codes(blocking_lint.lint([first]))
    first = _shot("SHOT-001", 4.0, hook="scale_tableau")
    assert "L16" not in _codes(blocking_lint.lint([first]))
    second = _shot("SHOT-002", 9.0, hook=None)
    assert "L16" not in _codes(blocking_lint.lint([first, second]))

def test_l17_chain_needs_previous_match_and_depth_at_most_two():
    a = _shot("SHOT-001", 4.0, cut="match", hook="kinetic")
    b = _shot("SHOT-002", 9.0, cut="match", chain_from="SHOT-001")
    assert "L17" not in _codes(blocking_lint.lint([a, b]))
    a_cut = _shot("SHOT-001", 4.0, cut="cut", hook="kinetic")
    assert "L17" in _codes(blocking_lint.lint([a_cut, b]))
    wrong = _shot("SHOT-002", 9.0, chain_from="SHOT-007")
    assert "L17" in _codes(blocking_lint.lint([a, wrong]))
    c = _shot("SHOT-003", 9.0, cut="match", chain_from="SHOT-002")
    d = _shot("SHOT-004", 6.0, chain_from="SHOT-003")
    assert "L17" in _codes(blocking_lint.lint([a, b, c, d]))
    assert "L17" not in _codes(blocking_lint.lint([a, b, c]))
```

VERDICT: FIX-FIRST