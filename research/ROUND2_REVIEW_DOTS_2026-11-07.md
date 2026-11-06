

# BATCH r1_director (dots) 11-07 03:20



medium, write_pack.py:376, `episodes_from` crashes on invalid JSON in the episodes block, stage 1 answer contains ```json episodes\n{bad\n```, wrap `json.loads(block.group(1))` in try/except and raise `ValueError`.
medium, write_pack.py:321, `parse` crashes if `settings_for` raises a non-`ValueError`, legacy shot row causes `settings_for` to raise `KeyError`, catch any exception from `settings_for` and raise `ValueError`.
medium, write_pack.py:528-530 (run_stage) and 933 (run_single), exceptions from model calls (missing API keys, `ModelGaveUp`, network errors) are not caught, crashing the run instead of recording a stage failure, run writer with no NVIDIA keys, wrap `call` in try/except, record the error, and raise `StageFailed`.
low, pack_validator.py:599, `_s55_4` uses `isinstance(off, int)` without excluding `bool`, `off_stage_shots: true` when `EXIT_RELEASE_SHOTS=1`, add `and not isinstance(off, bool)`.
low, write_pack.py:152,189,170, configuration errors (missing keys, unreachable catalog) raise unhandled `RuntimeError`/`ValueError`, empty `NVIDIA_KEYS` directory, catch these in `run_stage` and record as stage failures (subsumed by the run_stage defect above).

FINAL:
1. medium, write_pack.py:528-530, `run_stage` does not catch exceptions from `call` (e.g., missing API keys, `ModelGaveUp`), crashing the run instead of recording a stage failure.
2. medium, write_pack.py:376, `episodes_from` crashes on invalid JSON in the episodes block.
3. medium, write_pack.py:321, `parse` crashes if `settings_for` raises a non-`ValueError`.
4. low, pack_validator.py:599, `_s55_4` does not exclude `bool` from `isinstance(off, int)`.
5. low, write_pack.py:152,189,170, configuration errors raise unhandled exceptions (covered by the run_stage defect).


# BATCH r2_registry_retry (dots) 11-07 03:40



**Findings**

**1. simple_language.py:41 – Invalid regex range causes `re.error` crash for Hindi/Marathi**  
`_DEV = "ऀ-ॣ०-ॿ"` contains the range `०-ॿ` (U+0966 to U+094F), which is descending. When `_phrase_re` compiles a lookbehind/lookahead using this string (line 162), Python’s `re` module raises `re.error: bad character range`. This happens for any hi/mr text that has at least one whitelisted phrase (which the sacred list always does).  
*Concrete failure:* Run `python director/simple_language.py shots.json --lang hi` on any valid Hindi shots file; the validator crashes instead of returning flags.  
*One-line fix:* Replace the string with a valid Devanagari range, e.g. `_DEV = "ऀ-ॿ०-९"` (or use `\u0900-\u097F` and add digits separately).

**2. retry_policy.py:203 – `is_free_model` crashes on non‑dict `pricing`**  
`entry.get("pricing") or {}` returns the original value when it is a list (or any truthy non‑dict), then `.values()` raises `AttributeError`.  
*Concrete failure:* A catalog entry `{"id": "x", "pricing": ["free", "0"]}` causes `is_free_model` to crash with `AttributeError: 'list' object has no attribute 'values'`.  
*One-line fix:* Guard with `isinstance(pricing, dict)` before calling `.values()`, or coerce non‑dicts to `{}`.

**3. run_registry.py:256 – `detect_language` uses incomplete Devanagari range**  
`re.findall("[ऀ-ॿ]", text)` matches only U+0900–U+094F, missing Devanagari digits (U+0966–U+096F) and other signs. A Hindi/Marathi text that contains many digits but few letters may fall below the 20‑character threshold and be misclassified as English.  
*Concrete failure:* A Hindi transcript consisting mostly of numbers written in Devanagari (e.g. "१२३४५") is labelled `en`, causing the wrong voice engine to be selected.  
*One-line fix:* Use the full Devanagari block, e.g. `re.findall("[\u0900-\u097F]", text)`.

**4. simple_language.py:77 – `_has_deva` uses the same incomplete range**  
`any("ऀ" <= ch <= "ॿ" for ch in t)` misses Devanagari digits, so a text that is entirely Devanagari digits is treated as non‑Devanagari and may be mis‑routed to English checks or flagged as SCRIPT‑02 incorrectly.  
*Concrete failure:* `check_text("१२३", "hi")` returns `language_detected: "en"` and may raise SCRIPT‑02 flags.  
*One-line fix:* Use the full Unicode range, e.g. `any("\u0900" <= ch <= "\u097F" for ch in t)`.

**5. run_registry.py:612 (and 119, 130) – `summary` / `pack_folders` crash on unreadable story directory**  
`story_dir.iterdir()` raises `PermissionError` when the directory exists but cannot be read. `summary()` and `pack_folders()` are not wrapped in error handling, so a single unreadable story folder crashes the whole story‑list UI.  
*Concrete failure:* After `chmod 000 stories/test_slug`, the UI request to list stories raises `PermissionError` and returns a 500 error.  
*One-line fix:* Catch `OSError` during iteration (e.g. `try: ... except OSError: return []`) or pre‑check readability with `os.access(story_dir, os.R_OK)`.

---

**Files with no real defects:**  
`retry_policy.py` (aside from the `is_free_model` bug above) and `run_registry.py` (aside from the range and permission issues) contain no further regressions or spec violations. The remaining fixes listed in the prompt (h3‑voice enforcement, Marathi detection by U+0933, shared retry policy, etc.) are correctly implemented and do not introduce new problems.

---

FINAL:
1. simple_language.py:41 – Invalid regex range `०-ॿ` crashes Hindi/Marathi validator.
2. retry_policy.py:203 – `is_free_model` crashes on non‑dict `pricing`.
3. run_registry.py:256 – `detect_language` misses Devanagari digits, misclassifies texts with numbers.
4. simple_language.py:77 – `_has_deva` misses Devanagari digits, causes wrong language routing.
5. run_registry.py:612 (and 119, 130) – `summary`/`pack_folders` crash on unreadable story directory.


# BATCH r3_h3_core (dots) 11-07 03:49



```json
{
  "findings": [
    {
      "severity": "high",
      "file": "schema_and_linter.py",
      "line": "950-952",
      "what": "lint_story crashes if the `compiled` parameter is not a dict or if a dict entry lacks the `compiled_prompt` key. The server POST body (pack) may contain a malformed `compiled` dict, leading to an unhandled AttributeError/KeyError.",
      "failing_input": "POST body with `compiled` set to a list, or `compiled` dict where a shot's value is a dict without `compiled_prompt`.",
      "fix": "Validate `compiled` is a dict; for each entry, if it is a dict require `compiled_prompt` else treat as a string or skip, and catch missing keys gracefully."
    },
    {
      "severity": "medium",
      "file": "compile_h3_sing8.py",
      "line": "200-203",
      "what": "compile_episode only catches KeyError from compile_comfyui_workflow, but compile_comfyui_workflow can raise ValueError when second_pass=True and the profile lacks `upscale_resolution`. This causes an unhandled crash.",
      "failing_input": "Request with `second_pass=True` and an execution_profile without `upscale_resolution`.",
      "fix": "Catch ValueError as well, or validate the profile for second-pass requirements before calling compile_comfyui_workflow."
    },
    {
      "severity": "medium",
      "file": "schema_and_linter.py",
      "line": "959",
      "what": "Assumes `shot["timing_and_lattice"]` is a dict; if it is a non-dict truthy value (e.g., a string), `(shot.get(...) or {}).get(...)` raises AttributeError because the truthy value is used directly.",
      "failing_input": "A shot where `timing_and_lattice` is a string instead of an object.",
      "fix": "Check `isinstance(shot.get("timing_and_lattice"), dict)` before calling `.get`."
    },
    {
      "severity": "medium",
      "file": "schema_and_linter.py",
      "line": "973",
      "what": "Assumes `ep.get("episode_plan")` is a dict; a non-dict truthy value causes AttributeError when `.get` is called on it.",
      "failing_input": "An episode where `episode_plan` is a string instead of an object.",
      "fix": "Check `isinstance(ep.get("episode_plan"), dict)` before calling `.get`."
    },
    {
      "severity": "low",
      "file": "router.py",
      "line": "16-20",
      "what": "ref_inventory does not validate that `reference_audio` and `reference_videos` are lists; a string will be split into characters, causing incorrect routing (always Ref2VA) and wrong reference counts.",
      "failing_input": "A shot with `reference_audio` set to a string like \"charA\".",
      "fix": "Add type checks in ref_inventory or in the linter to ensure these fields are lists of strings."
    }
  ]
}
```

FINAL:
1. (High) schema_and_linter.py:950-952 – `lint_story` crashes on malformed `compiled` parameter (trust boundary with server POST body).
2. (Medium) compile_h3_sing8.py:200-203 – `ValueError` from `compile_comfyui_workflow` (second pass, missing `upscale_resolution`) not caught, crashing `compile_episode`.
3. (Medium) schema_and_linter.py:959 – `timing_and_lattice` assumed to be dict; non-dict truthy value causes AttributeError crash.
4. (Medium) schema_and_linter.py:973 – `episode_plan` assumed to be dict; non-dict truthy value causes AttributeError crash.
5. (Low) router.py:16-20 – `reference_audio`/`reference_videos` not validated as lists, leading to incorrect routing and reference counts.
