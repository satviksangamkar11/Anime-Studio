

## Findings

---

### HIGH

**1. Path traversal via absolute paths in picture paths**
- **File:line:** `schema_and_linter.py:323-324` (and `resolve_keyframes` at `:124-132`)
- **Why:** `os.path.join(root, rel)` returns `rel` unchanged when `rel` is an absolute path (e.g., `/etc/passwd`), completely bypassing `root`. The same flaw exists in `resolve_keyframes` (`:129`) which returns upstream paths unsanitized. An attacker controlling the story file can read arbitrary files on disk.
- **Fix:** Reject any `rel` that starts with `/` or contains `..` path components before calling `os.path.join`.

**2. Off-by-one in stage-span / cadence contiguity allows invalid spans to pass**
- **File:line:** `schema_and_linter.py:259` and `:276`
- **Why:** The code uses `expect = b + 1` (closed-interval contiguity) but the final check at `:260`/`:277` compares `b != pf` (half-open, where `pf` is the frame count). This mismatch means a span ending at `pf` (one past the last valid frame index) passes both checks. Example: spans `[0,10],[11,20],[21,30]` with `pf=30` passes, but frame 30 does not exist (valid indices are 0–29). The rest of the codebase uses half-open intervals (`master_reel_frame_window` is `[start, start+count]`, `trim` uses `0 <= ti < to <= pf`).
- **Fix:** Change `expect = b + 1` to `expect = b` on lines 259 and 276.

**3. Non-string `compiled_prompt` silently skips all prompt validation**
- **File:line:** `schema_and_linter.py:350-358` (via `:436-437` in `lint_shot`)
- **Why:** If `compiled_prompt` is a non-string, non-None, non-dict value (e.g., an integer from user-supplied `compiled` dict in `lint_story`), `PROMPT_RE.match(text)` raises `TypeError`. This is caught by the `_run` wrapper at `:156-158`, which reports a generic `SC-03` error and **skips the entire `_check_prompt` function** — all PR-* checks are bypassed.
- **Fix:** In `_check_prompt`, validate that `compiled` is `None`, `str`, or `dict` at the top; log `PR-00` and return for any other type.

---

### MEDIUM

**4. Float `editorial_frames` passes TM-02 but breaks the running frame counter**
- **File:line:** `schema_and_linter.py:205` and `:488-489`
- **Why:** `ed != to - ti` passes when `ed` is `10.0` and `to - ti` is `10` (Python: `10.0 != 10` is `False`). But `isinstance(ed, int)` at `:489` is `False` for floats, so `running += 0`. The running count for all subsequent shots is wrong, cascading into incorrect `master_reel_frame_window` checks.
- **Fix:** Change `isinstance(ed, int)` to `isinstance(ed, (int, float))` and verify `int(ed) == ed`, or coerce to int after TM-02 validation.

**5. Dialogue tags spanning newlines bypass PR-07 substring check**
- **File:line:** `schema_and_linter.py:386`
- **Why:** `re.findall(r"<d>.*?</d>", text)` — the `.` metacharacter does not match `\n` by default. A `<d>` tag containing a newline is invisible to this regex, so the PR-07 check that each dialogue tag is a substring of the description is skipped for multi-line tags.
- **Fix:** Add `re.DOTALL` flag: `re.findall(r"<d>.*?</d>", text, re.DOTALL)`.

**6. Path traversal in `load_default_profile` via unsanitized `name`**
- **File:line:** `schema_and_linter.py:119`
- **Why:** `os.path.join(..., "profiles", name + ".json")` — if `name` contains `../` (e.g., `../../etc/passwd`), the resolved path escapes the `profiles/` directory. The `name` value comes from user-controlled story registry data.
- **Fix:** Validate that `name` contains only alphanumeric/underscore characters before constructing the path.

---

### LOW

**7. Boundary condition in pose-jump check uses `>` instead of `>=`**
- **File:line:** `schema_and_linter.py:342-343`
- **Why:** `abs(a["torso_pitch_deg"] - b["torso_pitch_deg"]) > 5.0` allows a jump of exactly 5.0°, but the error message says "exceeds 5.0 deg" implying `>= 5.0` is the violation. Inconsistent with the `com_y_ratio` check which adds `1e-9` epsilon.
- **Fix:** Change `> 5.0` to `>= 5.0` (and `> 0.03 + 1e-9` to `>= 0.03`) for consistent boundary semantics.

**8. Direct dict access on workflow nodes without key-existence guards**
- **File:line:** `schema_and_linter.py:410` and `:425`
- **Why:** `nodes["2"]["inputs"]` and `nodes["5"]["inputs"]` raise `KeyError` if the node is missing. The `_run` wrapper catches this and reports a generic `SC-03` error instead of the specific `WF-01` node-class error, producing confusing output. Not a security hole but degrades diagnostic quality.
- **Fix:** Use `.get()` with explicit missing-key error codes, or check node existence before accessing inputs.

**9. Missing `LATTICE_CUT_BOUNDS` entries only warn, not error**
- **File:line:** `schema_and_linter.py:246-247`
- **Why:** For `lattice_n` values not in `LATTICE_CUT_BOUNDS`, a both-dynamic cut is validated with only a `CN-W1` warning. An invalid editorial/handle-sum for those `n` values passes silently.
- **Fix:** Either populate the missing bounds or escalate `CN-W1` to an error (`CN-06`) when bounds are unavailable.

---

FINAL:

1. HIGH, schema_and_linter.py:323-324 (and :129), Path traversal — absolute/`..` paths in `picture_1_path`/`picture_2_path` bypass `asset_root` via `os.path.join`. Reject absolute paths and `..` components before joining.
2. HIGH, schema_and_linter.py:259 and :276, Off-by-one contiguity — `expect = b + 1` (closed-interval) conflicts with final check `b != pf` (half-open), allowing spans that extend one frame past `pixel_frames` to pass. Change to `expect = b`.
3. HIGH, schema_and_linter.py:350-358 (via :436-437), Fail-open — non-string `compiled_prompt` causes `TypeError` caught by `_run`, silently skipping all PR-* prompt checks. Validate type (None/str/dict) at entry of `_check_prompt`.
4. MEDIUM, schema_and_linter.py:205 and :488-489, Float editorial_frames — `10.0 != 10` is False so TM-02 passes, but `isinstance(ed, int)` is False so `running` doesn't increment, corrupting subsequent window checks. Accept float-with-int-value or coerce.
5. MEDIUM, schema_and_linter.py:386, Regex gap — `re.findall(r"<d>.*?</d>", text)` misses tags containing newlines (`.` excludes `\n`), bypassing PR-07 substring check. Add `re.DOTALL`.
6. MEDIUM, schema_and_linter.py:119, Path traversal — `name + ".json"` in `load_default_profile` allows `../` escapes out of `profiles/`. Validate `name` is alphanumeric/underscore only.
7. LOW, schema_and_linter.py:342-343, Boundary — `> 5.0` allows exactly 5.0° jump though message says "exceeds". Change to `>= 5.0` (and `>= 0.03`).
8. LOW, schema_and_linter.py:410 and :425, Robustness — direct `nodes["2"]["inputs"]` / `nodes["5"]["inputs"]` access raises KeyError on missing nodes, producing generic SC-03 instead of specific WF errors. Guard with `.get()`.
9. LOW, schema_and_linter.py:246-247, Warning-as-pass — both-dynamic cuts for `lattice_n` not in `LATTICE_CUT_BOUNDS` only warn (CN-W1), letting invalid cuts pass. Escalate to error or populate bounds.