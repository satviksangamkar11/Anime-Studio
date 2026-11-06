

# BATCH b1_validator_writer (dots) 11-07 02:03



## Findings

### FILE pack_validator.py

**1. medium — pack_validator.py:294 — dialogue `tone` is required by the schema and the error message but is never validated**
The AUD-03 message says "needs speaker, text, **tone** and time_range", but the guard only tests `speaker`, `text` and `time_range`. A line with no `tone` key passes.
- Failing input: `{"speaker":"S1","text":"hi","time_range":[1.0,2.0]}` (no `tone`) → no error, although `tone` is mandatory per the owner spec ("dialogue: Character line, speaker ID, tone, and time_range") and `writer_prompts` stage 3.
- Fix: add `and _nonempty_str(x.get("tone"))` to the condition at line 294.

**2. medium — pack_validator.py:224 + :257 — `_positions()` reads a `facing` key that the schema does not carry; the "eyeline" half of S55-6 cannot fail for conformant data**
`_positions` builds `(screen, facing)`, but ANCH-01 (line 257) requires `id, screen, **depth**`, and the spec/example use `screen`/`depth` (never `facing`). So for any row that passes ANCH-01, `_positions` returns `(side, None)` and the `eyeline` comparison at line 642 (`if a and b and a != b`) never fires — a check that cannot fail.
- Failing input: two consecutive conformant rows `character_positions:[{"id":"CHAR-X","screen":"left","depth":"mid"}]` → `[{"id":"CHAR-X","screen":"right","depth":"far"}]`; the screen flip is caught but the second-axis change is silently ignored.
- Fix: read the field the schema actually carries (`depth`) and compare depth values, or add `facing` to the required `character_positions` keys and compare it.

**3. medium — pack_validator.py:836 — VM-01 checks only the primary `narration`; `narration_by_lang` entries are never checked for a NARRATOR voice id**
The elevenlabs narration check inspects `track["narration"]` only. In multilingual rows the per-language narrations live in `narration_by_lang` and are never tested against `voice_map.NARRATOR.<lang>`, even though the same check runs for dialogue (including `dialogue_by_lang`) at lines 843-852.
- Failing input: multilingual row with `narration_by_lang: {"hi": {"text":"...","language":"hi","time_range":[1,2]}}` and no `voice_map.NARRATOR.hi` → no VM-01 error, while the identical omission on the primary `narration` would error.
- Fix: loop over `narration_by_lang` entries and apply the same `voice_map.NARRATOR.<lang>` presence check.

**4. medium — pack_validator.py:821 — when `voice_engine` is absent the validator skips all voice checks, but the owner default is elevenlabs**
`_check_voice` returns immediately when `engines is None`, and `_validate_story` only validates `voice_engine` when the key is present. The owner specifies elevenlabs as the default engine for all languages, so VM-01/VM-02 should still apply to a `voice_map` that the bible always carries; instead a pack with no `voice_engine` key gets no voice validation at all.
- Failing input: a pack with dialogue lines and a `voice_map` but no `voice_engine` key → a missing per-language voice id is never flagged.
- Fix: treat `engines=None` as the elevenlabs default (e.g. default to `{}` so `engine_for` returns "elevenlabs") instead of returning early.

**5. low — pack_validator.py:469 + :483 — multilingual rows are forced to have narration in every language, while single-language rows allow `narration: null`**
ML-03 requires every `*_by_lang` key present on a multilingual row, and the `narration_by_lang` loop (line 488) requires `text` + `time_range` for every language, so a multilingual shot with no narration cannot be represented. Single-language rows allow `narration: null`. Contradictory rules.
- Failing input: a 2-language story with an action shot that legitimately has no narration → `narration_by_lang: {}` or omitted triggers ML-03/ML-01.
- Fix: allow `narration_by_lang` to be absent (or accept null entries) when a shot has no narration, mirroring the single-language `narration: null`.

**6. low — pack_validator.py:843 — for the primary language, dialogue lines are checked twice (duplicate errors)**
`lines` collects both `track["dialogue"]` and `dialogue_by_lang[primary]`, which the spec says are duplicates, so an invalid primary-language line produces two identical errors.
- Fix: for the primary language, check only `dialogue_by_lang[primary]` (skip `track["dialogue"]`) when it is present.

**7. low — pack_validator.py:315 — `mouth_state` values are validated but coverage is not**
The loop checks each value is in `MOUTH_STATES` but never verifies there is one entry per second of the shot, which the spec requires ("one entry per second").
- Fix: check that `mouth_state` contains an entry for every integer second `0..floor(editorial_duration_sec)`.

**8. low — pack_validator.py:496 — the primary `narration.time_range` is not bounded by the shot duration**
ML-06 (line 493) bounds `narration_by_lang` time ranges against `editorial`, but the primary `narration` is only added to the timing-equality set (line 496) with no equivalent bounds check, so primary narration can extend past the shot.
- Fix: apply the same `rng[1] <= editorial + TIME_TOL` check to the primary `narration.time_range`.

### FILE writer_prompts.py
No findings — pure prompt text, no I/O, no model calls; the language/shape rules it emits are consistent with the validator.

=== FINAL:
1. pack_validator.py:294 — dialogue `tone` is mandatory in the spec and the error message but is never validated (missing validation at a trust boundary).
2. pack_validator.py:224/257 — `_positions()` reads `facing` while ANCH-01 requires `depth`, so the S55-6 "eyeline" flip check cannot fail for any spec-conformant row (dead check / contradictory rules).
3. pack_validator.py:836 — VM-01 never checks `narration_by_lang` entries for a `voice_map.NARRATOR` id, only the primary `narration` (missing validation).
4. pack_validator.py:821 — absent `voice_engine` skips all voice checks although the owner default is elevenlabs, so the default engine's VM-01/VM-02 never run (spec contradiction / missing validation).
5. pack_validator.py:469/483 — multilingual rows must have non-empty narration in every language while single-language rows allow `narration: null` (contradictory rules).
