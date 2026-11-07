

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


# BATCH r4_h3_gate_ctrl (dots) 11-07 04:07



**gate_d_audio.py**

- **severity: medium**, `gate_d_audio.py:97` — `_speech_items` assumes `narr["time_range"]` exists when narration text is non‑empty; a shot whose `narration` object has `text` but no `time_range` raises `KeyError`.  
  *Failing input:* `{"narration": {"text": "hello"}}` in any shot track.  
  *Fix:* use `narr.get("time_range")` and skip the item (or raise a `ValueError`) when the range is missing.

- **severity: medium**, `gate_d_audio.py:180` — `check_closing_shot` reads `narr["time_range"]` directly after only checking that `text` is non‑empty; the same `KeyError` occurs if `time_range` is absent.  
  *Failing input:* closing shot with `narration: {"text": "goodbye"}` (no `time_range`).  
  *Fix:* use `narr.get("time_range")` and report a `CLOSING_VO_NO_TIME_RANGE` error when it is missing.

- **severity: medium**, `gate_d_audio.py:115‑116` — `check_opening_hook` iterates `sfx_cues` and calls `c["time_range"]` without verifying the key exists or that `c` is a dict; a cue missing `time_range` raises `KeyError`/`TypeError`.  
  *Failing input:* `sfx_cues: [{"sound": "whoosh"}]` (no `time_range`).  
  *Fix:* use `c.get("time_range")` and skip cues that do not provide a valid range.

**render_controller.py** — no findings (the default‑language fallback and other fixes are correct and do not introduce regressions).

**voice_engine.py** — no findings.

FINAL:
1. medium, gate_d_audio.py:97 – `_speech_items` does not guard `narr["time_range"]`.
2. medium, gate_d_audio.py:180 – `check_closing_shot` does not guard `narr["time_range"]`.
3. medium, gate_d_audio.py:115‑116 – `check_opening_hook` does not guard `c["time_range"]` in `sfx_cues`.


# BATCH r5_h3_convert_author (dots) 11-07 04:18



=== FILE v4_to_h3.py ===
- Line 187: In `_soundscape`, the chunking logic `cues[j * len(cues) // n:(j + 1) * len(cues) // n]` drops cues when `len(cues)` is not a multiple of `n`.  
  **Severity**: medium  
  **Concrete input**: a track with 5 `sfx_cues` (`n=4`); the fifth cue is omitted from the overall soundscape.  
  **One-line fix**: distribute cues with a round-robin or `math.ceil`-based split so every cue lands in exactly one sentence.

- Lines 151–153: In `_stages`, when a stage has `audio_cue` entries but no `action_pose_expression`, the built sentence becomes `", with cue1 and cue2."` (leading comma).  
  **Severity**: low  
  **Concrete input**: a `per_second_directives` entry that has `audio_cue` but missing/empty `action_pose_expression`.  
  **One-line fix**: construct the sentence conditionally — if `actions` is empty, use the cues as the sentence; otherwise append `, with …` after the actions.

=== FILE voice_manifest.py ===
- Lines 64–66: `build_entry` reads the wav file to compute `sha256` without handling `OSError`.  
  **Severity**: medium  
  **Concrete input**: a wav file that exists but is unreadable (permissions `000`). The program crashes with `OSError`.  
  **One-line fix**: wrap the `open(...)` in `try/except OSError`, set `sha256=None` and record an error.

- Line 89: `build_manifest` calls `vo_fit_check` without a `try/except`; any exception from that function crashes the CLI.  
  **Severity**: low  
  **Concrete input**: `vo_fit_check` raises on malformed input (e.g., a wav with an invalid header).  
  **One-line fix**: wrap the call in `try/except Exception` and append an error to the `errors` list.

=== FILE h3_author.py ===
No real defects found (the `languages=["en"]` in `_lint_candidate` is a safe choice for language-independent H3 fields; unverified whether the linter depends on it).

=== FILE pipeline_contract.py ===
No findings.

FINAL:
1. v4_to_h3.py:187 – _soundscape chunking drops cues when len(cues) > n (medium)
2. voice_manifest.py:64-66 – unhandled OSError when reading wav for sha256 (medium)
3. v4_to_h3.py:151-153 – _stages produces a malformed sentence starting with ", with " (low)
4. voice_manifest.py:89 – unhandled exception from vo_fit_check (low)


# BATCH r6_ui_server (dots) 11-07 04:21



After reviewing server.py and pipeline.py for regressions, spec violations, and logic errors introduced by the Round‑1 fixes, I found the following real defects:

---

**1. HIGH — server.py:1241‑1246**
`_ops_checks().record_spend(...)` is called **before** the `_active()` re‑check. If another job is already running, the 409 is raised but the spend has already been debited from the ledger — units are consumed with no job executed.
**Failing input:** Two concurrent clients; client A starts a `$` job, client B previews and runs a second `$` job while A is still active. B's run gets 409 but its units are already recorded.
**One‑line fix:** Move `record_spend` inside the `with self.lock:` block after the `_active()` re‑check and `rec["used"] = True`.

---

**2. MEDIUM — pipeline.py:690**
Episodes are sorted with `key=lambda x: str(x[0])`. If `episode` values are integers (e.g. `1, 2, 10`), string sort produces `1, 10, 2` — the episode list in the summary is numerically wrong.
**Failing input:** A pack whose shots have `episode: 10`; the summary will place it between 1 and 2.
**One‑line fix:** Sort numerically when the episode value is an int: `key=lambda x: (isinstance(x[0], str), x[0] if isinstance(x[0], int) else 0, str(x[0]))` or coerce to int inside a try.

---

**3. MEDIUM — server.py:850**
`read_images` calls `queue_state(cfg, adhyay)` for legacy stories without a try/except. If `_dq_module()` fails to import `download_queue` or `dq.status()` raises, the entire `/api/images` endpoint crashes (500) instead of gracefully degrading.
**Failing input:** A legacy story folder where `flow/scripts/download_queue.py` is missing or has a syntax error.
**One‑line fix:** Wrap the `queue_state` call in try/except and fall back to `{"pending": [], "filed": [], "accepted": []}` on failure.

---

**4. LOW — pipeline.py:832**
`_per_language` filters gate‑D reasons with `f" {lang}: " in r`, expecting a **leading space** before the language code. If reasons are formatted as `"en: missing VO"` (no leading space), the filter silently matches nothing, hiding real per‑language problems.
**Failing input:** A gate‑D reason list containing `"en: audio plan not ready"`; the row for `en` would show `"ready"` when it is not.
**One‑line fix:** Match with `f"{lang}: "` (no leading space) or normalise the reason format at the source.

---

**5. LOW — server.py:1205**
For `colab_run`, `args` contains only `batch`, `gpu`, `session` (from `BATCH_ARGS`). `rec["story"]` is therefore `None`, and the spend ledger entry gets `story=""`. The spend is not traceable to any story.
**Failing input:** Any `colab_run` execution; the ledger row has an empty story field.
**One‑line fix:** Derive the story from the batch's `render_manifest.json` or from the project pointer, falling back to `""` only when truly unknown.

---

**6. LOW — pipeline.py:713‑714**
`_reel_range()` returns `(lo, hi)` but only `hi` is checked (`ep_data["seconds"] > hi`). Episodes shorter than `lo` are never flagged, despite the variable name implying both bounds.
**Failing input:** An episode with 10 seconds when the studio range is 60‑75 s; no warning is raised.
**One‑line fix:** Add `or ep_data["seconds"] < lo` to the condition.

---

**7. LOW — server.py:1291**
When `job_stop` calls `_verify_stop` for a spend job that already finished but was never verified, `_verify_stop` may set `job.state = "stop_failed"`. The return message still says `"the job had already finished"`, misrepresenting the actual state.
**Failing input:** A `colab_run` job that ended but whose Colab session is still listed; the API returns `"the job had already finished"` while `state` is `"stop_failed"`.
**One‑line fix:** Return `job.state`‑aware text: `"stop_failed"` when `job.state == "stop_failed"`, else the existing message.

---

FINAL:
1. HIGH — server.py:1241‑1246 — `record_spend` debits the ledger before the `_active()` re‑check, allowing units to be consumed with no job executed.
2. MEDIUM — pipeline.py:690 — Episode sorting by `str()` misorders numeric episodes (1, 10, 2).
3. MEDIUM — server.py:850 — `queue_state` in `read_images` has no error handling; a broken `download_queue` module crashes the images endpoint.
4. LOW — pipeline.py:832 — Per‑language reason filter expects a leading space, silently missing real reasons.
5. LOW — server.py:1205 — `colab_run` spend entries have an empty `story` field, breaking traceability.


# BATCH r7_ui_js (dots) 11-07 04:29



## Findings

**1. Medium — pipeline.js:733–734**
Story save resets `State.newSlug` and `State.overwrite` but does **not** clear the corresponding drafts (`wiz-story-new-slug`, `wiz-story-overwrite`). On the next render, `applyDrafts()` restores the stale values: the "New slug" input shows the old slug instead of being empty, and the "overwrite" checkbox stays checked.
- **Failing input:** Save a story with a new slug `foo_bar`, then watch the new-slug field re-populate with `foo_bar` and the overwrite checkbox remain ticked.
- **One-line fix:** add `delete State.drafts['wiz-story-new-slug']; delete State.drafts['wiz-story-overwrite'];` after line 733.

**2. Medium — pipeline.js:278–285 (and pipeline.js:966–989)**
`loadStory()` only updates `State.storyText` when `State.storySlug !== State.lastStorySlug`. After a server-side story-text change (e.g. a completed YouTube link import), the slug is unchanged so the text is **never** refreshed — the textarea keeps showing the pre-import text indefinitely. Additionally the `wiz-story-text` draft is never cleared, so a stale draft can override the server's new text on the next render.
- **Failing click path:** Paste a YouTube link → click "Get transcript from link" → confirm → job completes → the story textarea still shows the old text, and if the user had typed something earlier the draft overrides the new transcript.
- **One-line fix:** in the `.then` at line 278, always update when the server text differs and clear the draft:
```js
var newText = data && data.text ? data.text : '';
if (newText !== State.storyText || State.storySlug !== State.lastStorySlug) {
  State.lastStorySlug = State.storySlug;
  State.storyText = newText;
  State.storyDirty = false;
  delete State.drafts['wiz-story-text'];
}
```
Also change `runLink`'s final `.finally` to call `refreshWizard(true)` instead of `render(true)` so the refresh actually happens.

**3. Low — pipeline.js:276–285**
Race condition: `get('/api/story/' + enc(State.storySlug))` captures the slug at call time, but the `.then` checks `State.storySlug !== State.lastStorySlug` using the *current* slug. If the slug changes while the request is in flight, the old story's text is written under the new slug's name.
- **Failing input:** rapidly switch story A → story B while A's `/api/story` request is still pending; B's UI shows A's text.
- **One-line fix:** capture `var requestedSlug = State.storySlug;` before the `get()` and guard the `.then` with `if (requestedSlug !== State.storySlug) return;`.

**4. Medium (unverified) — pipeline.js:340**
`/api/render/status` is called with `pack=enc(pack)` (bare pack name) while every other pack-scoped endpoint (`/api/pack`, `/api/pack/validate`, `/api/author/status`, `/api/pack/voices`) uses `pack=enc(pp)` where `pp = 'stories/' + slug + '/' + pack`. If the render-controller fix changed the server contract to expect the full path, the render-status panel will fail to load and Gate D can never be approved.
- **One-line fix:** change line 340 to use `enc(pp)` for consistency, or confirm the server still expects the bare pack name.

**5. Low (unverified) — pipeline.js:1237**
`findJobsFile()` returns `'flow/' + names[i]` where `names[i]` comes from the server's `/api/images` file paths. If those paths already include the `flow/` prefix the result is doubled (`flow/flow/…`), producing an invalid jobs-file path for the packet.
- **One-line fix:** guard the prefix, e.g. `var p = names[i]; return p.indexOf('flow/') === 0 ? p : 'flow/' + p;`, or confirm the server returns bare filenames.

---

FINAL:
1. Medium — pipeline.js:733–734 — story save leaves stale `wiz-story-new-slug` and `wiz-story-overwrite` drafts; `applyDrafts` restores them after save.
2. Medium — pipeline.js:278–285 — `loadStory` never refreshes story text when the slug is unchanged, so link-import / server-side updates are invisible; `wiz-story-text` draft is also never cleared.
3. Medium (unverified) — pipeline.js:340 — `/api/render/status` uses bare `pack` while sibling endpoints use the full `stories/slug/pack` path; possible contract mismatch after the render-controller fix.
4. Low — pipeline.js:276–285 — `loadStory` race condition: a stale response for an old slug can overwrite text under the new slug.
5. Low (unverified) — pipeline.js:1237 — `findJobsFile` may double the `flow/` prefix if server file paths already contain it.


# BATCH r8_ui_app_html_css (dots) 11-07 04:47



Looking at the codebase, I've identified several real defects. Here are my findings:

---

**HIGH**

1. **app.js:1321-1323** — `loadExport()` references `window.StudioWizard.project()`, a global that is never defined in `app.js` or `index.html`. The guard `window.StudioWizard && …` short-circuits to `{}`, so `pj.story_slug` is always `undefined` and the export feature permanently fails with "Pick a story and run its analysis first". No other script in the provided files defines `StudioWizard`.  
   *Failing input*: Click "Load" on the Export section with any valid reel number.  
   *One-line fix*: Replace the `window.StudioWizard` fallback with `S.story.slug` and `$('story-pack').value` (or define the global in `pipeline.js` if it is supposed to exist).

2. **app.js:1323** — The `/api/export` URL appends `&story=` and `&pack=` query parameters that are not documented in the server contract (line 32: only `reel=N` is specified). If the server does not accept these params, the request may fail or behave
