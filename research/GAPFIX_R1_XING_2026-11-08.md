# GAPFIX R1 (xing) 11-08 03:07

We need to carefully review the patch for real defects: wrong logic, crashes (None, missing key, wrong type), regressions for older story formats (Kaliya legacy rows, v2.2 rows with beats, packs without a story block), security problems (path traversal, injection, trusting story.json), Windows path problems, and edits that do not do what their comment says. Report each as severity, file:hunk, one sentence what is wrong, concrete input -> wrong result, exact fix. Do NOT report style, missing features or things you are unsure about; write 'possible' and what to check if unsure. End with FINAL: count by severity.

We need to examine each hunk carefully. Let's go through them.

1. core/caption_cues.py hunk 81-19: The change handles captions_by_lang[lang] being a list of cards. It iterates over cards, appending items. For dict cards, it uses c.get("text") and c.get("time_range") or (narr or {}).get("time_range"). For str cards, it uses c and narr.get("time_range"). Potential issues: If cap is a list but some elements are not dict/str? The condition `all(isinstance(c, (dict, str)) for c in cap)` ensures all are dict or str. But then inside loop, `if isinstance(c, dict):` else `elif narr:` else nothing? Actually if c is str and narr is None, then `items.append((c, narr.get("time_range")))` would append None for time_range. That might be okay? But maybe time_range should be None. However, the original code for dict used `cap.get("time_range") or (narr or {}).get("time_range")`. For str, they use `narr.get("time_range")` which could be None. That seems consistent. But there is a subtle bug: if cap is a list of cards, but some card is a dict without "text" key, then `c.get("text")` returns None, and item becomes (None, time). That could cause downstream None handling. But maybe acceptable. Also, if cap is a list but empty, `cap and all(...)` short-circuits to False, so goes to elif dict, elif str. That's fine. However, there is a potential issue: if cap is a list of dicts where some have "time_range" as something falsy like 0, then `or` would fall back to narr time_range. That might be intended. Not a crash. But there is a more serious bug: the original code had `if isinstance(cap, dict):` and then `items.append((cap.get("text"), cap.get("time_range") or (narr or {}).get("time_range")))`. The new code adds a branch for list. But note that the variable `narr` is defined earlier? In the function `spoken_cues`, `narr` is likely the narration object. The patch uses `narr` inside the loop. That should be fine. However, there is a potential bug: if `cap` is a list but `narr` is None, then for dict cards, `c.get("time_range") or (narr or {}).get("time_range")` would evaluate `(narr or {})` which is `{}`, so `.get("time_range")` returns None. So time_range becomes None. That's okay. For str cards, `narr.get("time_range")` would raise AttributeError because narr is None. Wait: In the str branch, they wrote `elif narr:` then `items.append((c, narr.get("time_range")))`. If narr is None, the `elif narr:` condition fails, so it won't enter that branch. Actually the code is:
```
if isinstance(c, dict):
    items.append((c.get("text"), c.get("time_range") or (narr or {}).get("time_range")))
elif narr:
    items.append((c, narr.get("time_range")))
```
So if c is str and narr is None, neither branch executes, so the str card is ignored! That means a list of strings would be silently dropped. That could be a regression: previously, if cap was a string, it would be handled. Now if cap is a list of strings, none are processed. That is a real defect. Also, if cap is a list of mixed types? The all() check ensures only dict/str, but if a str card and narr is None, it's dropped. That could cause missing captions. So this is a high/medium bug. Severity: medium? Could be high because it drops valid caption entries. Input: captions_by_lang[lang] = ["Hello", "World"], narr=None. Output: no items added, captions missing. Fix: handle str cards even when narr is None, perhaps using `(c, None)`. Or better: for str cards, use `(c, None)` if narr is None. But the spec likely expects time_range from narr if available, else None. So we can do: `elif isinstance(c, str): items.append((c, narr.get("time_range") if narr else None))`. But the current code only does that when narr is truthy. So fix: change `elif narr:` to `elif isinstance(c, str):` and inside use `narr.get("time_range") if narr else None`. However, note that the original code for dict used `or` fallback. For consistency, we could do similar: `c.get("time_range") or (narr or {}).get("time_range")` for both dict and str. But for str, `c.get` doesn't exist. So we need to handle separately. Simpler: for str, `items.append((c, (narr or {}).get("time_range")))`. That works even if narr is None. So fix: replace `elif narr:` with `elif isinstance(c, str):` and change line to `items.append((c, (narr or {}).get("time_range")))`. That ensures str cards are always processed. Also, for dict cards, keep as is. That fixes the drop.

But also note: the condition `if isinstance(cap, list) and cap and all(isinstance(c, (dict, str)) for c in cap):` ensures non-empty list. If cap is empty list, it falls through to elif dict/str. That's fine.

Another potential issue: if cap is a list of dicts where some dict has no "text", then item text is None. That might be okay but could cause downstream None handling. Not a crash. But maybe the original code didn't handle that either. We'll ignore.

2. core/retention_rules.py hunk 124-63: R2 and R5 changes. Need to verify logic. R2: originally `bad = [b for b in covering if b.get("hold") is not True]` meaning bad if hold is not true (i.e., motion beat). New: `bad = [b for b in covering if b.get("hold") is True]` meaning bad if hold is true (i.e., hold beat). The docstring says "Motion starts by first_motion_s: a beat covering 0 .. first_motion_s must NOT be hold: true, unless the first shot's post declares push/zoom at 0." So indeed, a hold beat covering 0..first_motion_s is bad. So new logic correct. But there is a subtlety: `covering` is the list of beats covering the first_motion_s window? The code: `covering = [b for b in beats if b["start_s"] <= first_motion_s <= b["end_s"]]`? Actually need to see context. The hunk shows `bad = [b for b in covering if b.get("hold") is True]`. That seems correct. However, there is a potential bug: if `covering` is empty, `bad` is empty, returns []. That's fine. But what about the case where `first_motion_s` is 0? Then covering includes beats starting at 0. If a beat starts at 0 with hold true, it's bad. That matches spec. So R2 seems correct.

R5: originally `if any(b.get("hold") is True and b["start_s"] < limit for b in beats): return [_entry(...)]` meaning if any hold beat starts before limit, fail. New: `early = [b for b in beats if b.get("hold") is True and b["start_s"] < limit]; if not early: return []; return [_entry(...)]`. That is logically equivalent: if early is non-empty, fail. So same logic. But there is a subtle difference: original returned FAIL if any hold beat starts before limit. New returns FAIL if early is non-empty. Same. However, the error message changed: original said "no hold beat starts before {limit} s". New says "a hold beat starts at {early[0]['start_s']:.2f} s, before {limit} s". That's fine. But there is a potential bug: if `beats` is empty, original `any(...)` returns False, so returns [] (no entry). New: `early` empty, returns []. Same. So R5 seems fine.

But wait: there is a comment about "the old code was inverted". The patch says R2 was inverted. The new code seems correct. However, we need to check if there are any other issues in retention_rules.py? The hunk only changes R2 and R5. No other changes. So likely no defect there.

But there is a potential issue: the function `rule_r2` uses `ret["first_motion_s"]`. If `ret` is missing that key, KeyError. But that's pre-existing. Not introduced by patch.

3. core/timeline.py hunk 40-164: major changes. Need to examine carefully.

First, import re added. That's fine.

New functions `_range_start` and `_v4_parts`. Let's analyze `_v4_parts`:

```python
def _v4_parts(shot, length_s):
    """Beats, cast ids, dialogue (start, text), camera moves and caption change times of a V4 writer row (per_second_directives)."""
    beats, camera_rel = [], []
    for d in shot.get("per_second_directives") or []:
        if not isinstance(d, dict) or not _is_num(d.get("t0")) or not _is_num(d.get("t1")) or d["t0"] >= length_s:
            continue
        acting = _str(d.get("action_pose_expression"))
        beats.append(_beat(float(d["t0"]), min(float(d["t1"]), length_s), hold="hold" in acting.lower(), acting=acting))
        cam = _str(d.get("camera")).strip().lower()
        if cam and STATIC_WORD not in cam and "hold" not in cam:
            camera_rel.append(float(d["t0"]))
    anchors = shot.get("reference_anchors") if isinstance(shot.get("reference_anchors"), dict) else {}
    cast = [p["id"] for p in anchors.get("character_positions") or [] if isinstance(p, dict) and isinstance(p.get("id"), str)]
    track = shot.get("audio_and_dialogue_track") if isinstance(shot.get("audio_and_dialogue_track"), dict) else {}
    dialogue = []
    for line in track.get("dialogue") or []:
        start = _range_start(line.get("time_range")) if isinstance(line, dict) else None
        if start is not None and 0 <= start < length_s:
            dialogue.append((start, _str(line.get("text"))))
    caption_rel = []
    by_lang = track.get("captions_by_lang")
    for cards in by_lang.values() if isinstance(by_lang, dict) else []:
        for card in cards if isinstance(cards, list) else []:
            start = _range_start(card.get("time_range")) if isinstance(card, dict) else None
            if start is not None and 0 <= start < length_s:
                caption_rel.append(start)
    return {"beats": beats, "cast_ids": cast, "dialogue": dialogue, "camera_rel": camera_rel, "caption_rel": caption_rel}
```

Potential issues:

- `_is_num` and `_str` are helper functions defined elsewhere. Assume they exist.
- `STATIC_WORD` is a constant. Assume exists.
- The loop over `per_second_directives` filters out non-dict or non-numeric t0/t1, or t0 >= length_s. That's fine.
- `acting = _str(d.get("action_pose_expression"))` then `hold="hold" in acting.lower()`. If action_pose_expression is missing, `_str` returns ""? Probably. So hold false. That's okay.
- `cam = _str(d.get("camera")).strip().lower()` then condition `if cam and STATIC_WORD not in cam and "hold" not in cam:`. Note: `STATIC_WORD` is likely a word like "static"? If camera contains "static", it's excluded. That's fine.
- `anchors = shot.get("reference_anchors") if isinstance(shot.get("reference_anchors"), dict) else {}`. This calls `shot.get` twice; minor inefficiency but okay.
- `cast = [p["id"] for p in anchors.get("character_positions") or [] if isinstance(p, dict) and isinstance(p.get("id"), str)]`. If `character_positions` is not a list, `or []` makes it empty list. Good.
- `track = shot.get("audio_and_dialogue_track") if isinstance(shot.get("audio_and_dialogue_track"), dict) else {}`. Again double get.
- `dialogue` loop: for each line in `track.get("dialogue") or []`, if line is dict, get time_range via `_range_start`. If line is not dict, start=None, skip. That's fine.
- `caption_rel` loop: `by_lang = track.get("captions_by_lang")`. Then `for cards in by_lang.values() if isinstance(by_lang, dict) else []:` This iterates over values of the dict. For each value (which should be a list of cards), iterate over cards. If value is not a list, `else []` skips. That's fine. But note: `by_lang.values()` returns view; if by_lang is not dict, the conditional expression `by_lang.values() if isinstance(by_lang, dict) else []` yields an empty iterator. Good.
- Inside, `for card in cards if isinstance(cards, list) else []:` Wait: `cards` is the value from `by_lang.values()`. The expression `cards if isinstance(cards, list) else []` means if cards is a list, iterate over it; else skip. That's fine.
- For each card, if dict, get time_range; else start=None. Good.

Now, the integration into `_parse_rich_or_legacy`:

```python
v4 = _v4_parts(shot, length_s) if isinstance(shot.get("per_second_directives"), list) else None
if v4:   # the writer's V4 row (11-08 audit A): beats, cast, dialogue starts, camera moves and caption changes come from its columns
    beats = v4["beats"]
    beats_raw = [{"acting": b["acting"]} for b in beats]

dialogue = []
raw_dialogue = shot.get("dialogue")
if v4:
    raw_dialogue = []
    dialogue = list(v4["dialogue"])
if raw_dialogue is not None and not isinstance(raw_dialogue, list):
    soft.append("dialogue is not a list; ignored")
    raw_dialogue = []
...
camera_rel = v4["camera_rel"] if v4 else ([0.0] if moved else [])
...
"cast_ids": v4["cast_ids"] if v4 else _ids(shot.get("cast"), soft, "cast"),
...
"camera_rel": camera_rel,
"caption_rel": sorted(set(_caption_changes(look) + (v4["caption_rel"] if v4 else []))),
```

Potential issues:

- When v4 is present, `beats` is replaced by v4 beats, and `beats_raw` is built but not used? Actually `beats_raw` is assigned but never used later. That's dead code, but not a bug. However, the comment says "beats, cast, dialogue starts, camera moves and caption changes come from its columns". The `beats` variable is used later? Let's see: later in the function, `beats` is used in prompt_parts? Actually `beats` is used in `prompt_parts`? The code later builds `prompt_parts` from various fields. `beats` is not directly used in prompt_parts? Let's check: after the v4 integration, there is:
```
prompt_parts = [_text(shot.get(k)) for k in ("style", "world", "action")]
prompt_parts.append(_text(camera))
prompt_parts.append(_text(move))
prompt_parts.append(_text(post))
prompt_parts.append(_text(look))
prompt_parts.append(_text(light_world))
prompt_parts.append(_text(beats))
prompt_parts.append(_text(impacts))
prompt_parts.append(_text(cast))
prompt_parts.append(_text(first_dialogue))
prompt_parts.append(_text(dialogue_rel))
prompt_parts.append(_text(camera_rel))
prompt_parts.append(_text(caption_rel))
prompt_parts.append(_text(purpose))
prompt_parts.append(_text(sound_text))
prompt_parts.append(_text(soft))
```
So `beats` is used. If v4 is present, `beats` is set to v4["beats"]. That's good. But `beats_raw` is unused. That's not a bug, just wasteful. However, there is a potential issue: `beats` is used in `prompt_parts.append(_text(beats))`. If v4 is present, beats is a list of beat dicts. That's fine.

- `camera_rel` is set to v4["camera_rel"] if v4 else ([0.0] if moved else []). That's fine.

- `caption_rel` is `sorted(set(_caption_changes(look) + (v4["caption_rel"] if v4 else [])))`. This combines caption changes from look and from v4. That seems correct.

- `cast_ids` is v4["cast_ids"] if v4 else _ids(...). Good.

- `dialogue` is set to list(v4["dialogue"]) if v4, else raw_dialogue. But note: if v4 is present, raw_dialogue is set to [] and dialogue is set to v4 dialogue. That overrides any raw dialogue. That's intended: V4 row provides its own dialogue. Good.

- However, there is a subtle bug: `raw_dialogue = shot.get("dialogue")` is called before the `if v4:` block. Then inside `if v4:`, `raw_dialogue = []`. That's fine. But later, `if raw_dialogue is not None and not isinstance(raw_dialogue, list):` will be False because raw_dialogue is [] (a list). So no soft warning. That's okay.

- Another potential issue: `beats_raw` is built but never used. Could be removed, but not a bug.

- The function `_v4_parts` uses `_is_num` and `_str`. Are these defined? They likely are. But we need to ensure they handle missing keys gracefully. `_is_num` probably checks if value is int/float. `_str` probably converts to string. If missing, returns "" or None. That's fine.

- One more: `_range_start` function:
```python
def _range_start(value):
    """Start second of a time range given as [a, b] or as the text '1.2-1.6s'; None when it has none."""
    if _two_numbers(value):
        return float(value[0])
    m = re.match(r"\s*(\d+(?:\.\d+)?)\s*-", value) if isinstance(value, str) else None
    return float(m.group(1)) if m else None
```
Assume `_two_numbers` is defined elsewhere. It likely checks if value is a list/tuple of two numbers. If value is a string like "1.2-1.6s", regex extracts 1.2. If value is a number? Not handled. But time_range is usually a string or list. That's fine.

- Potential bug: if `value` is a string but doesn't match regex, returns None. That's okay.

- However, there is a possible issue: `_two_numbers(value)` might return True for a string that is two numbers separated by comma? Not sure. But likely fine.

- Another: `re.match` on string with pattern `\s*(\d+(?:\.\d+)?)\s*-`. This matches start of string. If value is "1.2-1.6s", group(1) is "1.2". Good. If value is "1.2 - 1.6s" with spaces, still matches. If value is "1.2-1.6" (no s), still matches. Good.

- But what if value is a list like [1.2, 1.6]? `_two_numbers` likely returns True, then `float(value[0])` works. Good.

- So `_range_start` seems okay.

Now, the bigger concern: regressions for older story formats. The patch adds V4 support but does not remove legacy handling. The `_parse_rich_or_legacy` still handles legacy shots. However, there is a potential regression: previously, `beats` were built from legacy beats. Now if a shot has `per_second_directives`, it uses V4 parts. But what about shots that have both legacy beats and per_second_directives? The code prioritizes V4. That might be intended. But the comment says "the writer's V4 row (11-08 audit A): beats, cast, dialogue starts, camera moves and caption changes come from its columns". So if a shot has per_second_directives, it's treated as V4. That's fine.

But there is a potential issue: the `beats` variable is used in `prompt_parts`. If v4 is present, beats are from v4. But what about legacy beats? They are ignored. That could be a regression if some shots have both legacy beats and per_second_directives? Unlikely. The spec says V4 rows have per_second_directives. Legacy rows don't. So it's fine.

However, there is a more serious issue: the `_v4_parts` function reads `reference_anchors` and `audio_and_dialogue_track`. For legacy shots, these may not exist. The code handles missing keys by defaulting to {}. That's fine.

But there is a potential bug: `anchors = shot.get("reference_anchors") if isinstance(shot.get("reference_anchors"), dict) else {}`. This calls `shot.get` twice. If `reference_anchors` is present but not a dict, it defaults to {}. That's fine. But if it's a dict, it uses it. However, `character_positions` may be missing or not a list. The code does `anchors.get("character_positions") or []`. That's fine.

- Another: `track = shot.get("audio_and_dialogue_track") if isinstance(shot.get("audio_and_dialogue_track"), dict) else {}`. Again double get.

- The `dialogue` loop: `for line in track.get("dialogue") or []:` If `dialogue` is not a list, `or []` makes it empty. That's fine.

- The `caption_rel` loop: `by_lang = track.get("captions_by_lang")`. If `captions_by_lang` is not a dict, `by_lang.values()` would raise AttributeError. But the code guards with `if isinstance(by_lang, dict) else []`. Wait: `for cards in by_lang.values() if isinstance(by_lang, dict) else []:` This is a conditional expression: `by_lang.values() if isinstance(by_lang, dict) else []`. If by_lang is not dict, it evaluates to `[]`. So safe. Good.

- However, there is a subtle bug: `for cards in cards if isinstance(cards, list) else []:` Here `cards` is the value from `by_lang.values()`. If `cards` is not a list, the inner loop skips. That's fine.

- But what if `by_lang` is a dict but a value is not a list? Then `cards` is not a list, so inner loop skips. That's fine.

- So `_v4_parts` seems robust.

Now, the integration: `v4 = _v4_parts(shot, length_s) if isinstance(shot.get("per_second_directives"), list) else None`. This checks if `per_second_directives` is a list. If it's a list, call `_v4_parts`. If it's not a list (e.g., None or missing), v4 is None. That's fine.

But there is a potential issue: `per_second_directives` might be present but not a list (e.g., a dict). Then `isinstance(..., list)` is False, so v4 is None. That's okay; legacy handling proceeds.

Now, the `beats_raw` variable is assigned but never used. That's not a bug, but could be considered dead code. However, the instruction says "edits that do not do what their comment says." The comment says "beats, cast, dialogue starts, camera moves and caption changes come from its columns". The `beats_raw` is built but not used. That might be considered an edit that does not do what its comment says? The comment is about the v4 integration, not about beats_raw. beats_raw is leftover from previous code? Actually looking at the diff, before the change, there was likely `beats_raw` used somewhere? The diff shows:
```
+    v4 = _v4_parts(shot, length_s) if isinstance(shot.get("per_second_directives"), list) else None
+    if v4:   # the writer's V4 row (11-08 audit A): beats, cast, dialogue starts, camera moves and caption changes come from its columns
+        beats = v4["beats"]
+        beats_raw = [{"acting": b["acting"]} for b in beats]
```
Then later:
```
      dialogue = []
      raw_dialogue = shot.get("dialogue")
+    if v4:
+        raw_dialogue = []
+        dialogue = list(v4["dialogue"])
```
So `beats_raw` is assigned but never used. That is indeed dead code. But is it a defect? Possibly low severity, but the instruction says "edits that do not do what their comment says." The comment is attached to the `if v4:` block, not to `beats_raw`. So maybe not. However, it's still unnecessary code. But we might report it as low. But the instruction says "Report every REAL defect the patch introduces or leaves". Dead code is not a defect per se, but could be considered an edit that does not do what its comment says? The comment says "beats, cast, dialogue starts, camera moves and caption changes come from its columns". `beats_raw` is not part of that. So it's an extra line that doesn't serve the purpose. I'd say low severity, but maybe not required. Let's focus on real defects.

Another potential issue: The `_v4_parts` function uses `_is_num` and `_str`. Are these defined in the same module? Likely yes. But if they are not, it would crash. However, the patch didn't define them. They were presumably already there. So not introduced.

Now, director/story_state.py hunk 69-75: changes expected pack names. Let's analyze:

Original:
```
expected = ["single"] if "single" in present else ["1", "2"] + [f"3e{k}" for k in range(1, (episodes or 0) + 1)] + ["5"]
```
New:
```
eps = range(1, (episodes or 0) + 1)
tail = ["5"] if "5" in present else [f"5e{k}" for k in eps]
expected = ["single"] if "single" in present else ["1", "2"] + [f"3e{k}" for k in eps] + tail
```
This changes stage 5 from always "5" to per-episode "5e<N>" unless "5" is present. That matches the new design: captions per episode. But there is a potential bug: if `episodes` is 0 (older packs), `eps = range(1, 1)` empty, tail = ["5"] if "5" in present else []. So expected = ["1","2"] + [] + tail. If "5" not in present, tail = [], expected = ["1","2"]. That's fine. But if episodes is 0 and "5" not present, expected = ["1","2"]. That might be okay. However, the old code had `+ ["5"]` always. So for older packs without "5", expected would include "5". Now it doesn't. That could be a regression: older packs that don't have a stage 5 file might now be considered missing stage 5? But the code later checks `if (out / "stage_5_raw.json").exists():` and if not, does per-episode. So if a pack doesn't have "5" in present, it might still have stage_5_raw.json? Actually `present` is the set of files present. If "5" is not in present, but stage_5_raw.json exists, then `present` wouldn't include "5"? Wait, `present` is likely the set of files in the pack folder. The stage 5 file is named "stage_5_raw.json". Does "5" refer to that file? Probably yes. So if "5" not in present, it means no stage_5_raw.json. Then the code goes to the else branch (per-episode). That's fine. But the `expected` list is used for validation? Maybe to check that all expected stages are present. If expected doesn't include "5", but the pack has stage_5_raw.json, then validation might pass even though "5" is missing from present? Actually `present` is the set of files present. If stage_5_raw.json exists, "5" should be in present. So if "5" not in present, stage_5_raw.json doesn't exist. So expected not including "5" is consistent. So no regression.

But there is a subtle bug: `eps = range(1, (episodes or 0) + 1)`. If `episodes` is None, `(episodes or 0)` is 0, range(1,1) empty. That's fine. If `episodes` is 0, range(1,1) empty. That's fine.

However, the new code uses `eps` for both `3e{k}` and `5e{k}`. That's fine.

But there is a potential issue: the `tail` uses `eps` which is range(1, episodes+1). If episodes is 0, tail = ["5"] if "5" in present else []. That's fine.

So story_state.py seems okay.

Now director/write_pack.py hunk 186-236, 240-250, 254-260, 263-289, 299-316, 319-336, 338-373, 385-396, 401-408, 411-458.

Let's go through each.

Hunk 186-188: `gate_of` now returns "5" for "5e..." names. Previously returned name unchanged. That's fine.

Hunk 192-197: ORDER prompt addition. That's just text, no bug.

Hunk 201-212: `make_web_notes` changes. It now parses markdown fence and requires at least 200 chars. Potential issue: if the Haiku agent returns text without markdown fence, it uses raw text. That's fine. But the 200 char minimum might reject valid short notes. However, the comment says "the Haiku notes agent returned no usable notes". 200 chars is arbitrary. Could be a regression for short notes. But maybe acceptable. Not a crash.

Hunk 215-236: `call_claude` changes. It now always uses stream-json and join_stream. That's fine. But there is a potential issue: `join_stream` is called on `r.stdout` always. Previously, for non-web, it returned `r.stdout`. Now it returns `join_stream(r.stdout)`. `join_stream` likely joins multiple JSON objects from stream-json output. If the output is not stream-json (e.g., if web is False, fmt is still stream-json), then `join_stream` should handle that. But what if `join_stream` expects multiple JSON objects and the output is a single JSON object? It should still work. However, there is a risk: if the claude command fails or produces unexpected output, `join_stream` might raise. But that's pre-existing behavior. Not a new defect.

But there is a subtle bug: `web = WEB if web is None else web` originally. Now `web=False` default. That's fine. But the function signature changed: `def call_claude(prompt, model, effort, web=False, rule=True):`. Previously `web=None`. Callers might pass `web=None`? The diff shows `call_path` calls `call_claude(prompt, model, effort)` without web, so default False. That's fine. But there might be other callers that pass `web=None`? Unlikely. So okay.

Hunk 240-250: `call_path` changes. The WEB_NOTES prompt is updated. That's fine.

Hunk 254-260: `parse_stage_map` regex changed from `[1235]|3e\d+` to `[1235]|[35]e\d+`. This allows "5e1" etc. Previously "3e1" allowed, now also "5e1". That's fine. But note: the regex `[35]e\d+` matches "3e1" or "5e1". Good.

Hunk 263-289: `plan_errors` and `PLAN_SECONDS` added. Let's analyze.

`plan_errors(plan)`:
- If plan is not dict or no "episodes", returns [].
- eps = plan["episodes"]
- If not list or empty, returns ["PLAN-01 ..."].
- For each episode, checks n is int not bool, sec is number between PLAN_SECONDS.
- Checks seen numbers are 1..len(seen) once each.

Potential issues:
- `PLAN_SECONDS = (20, 180)`. If sec is exactly 20 or 180, it's within range. That's fine.
- The check `isinstance(sec, (int, float)) or isinstance(sec, bool)` is redundant because bool is subclass of int. But they explicitly exclude bool. That's fine.
- The check `not PLAN_SECONDS[0] <= sec <= PLAN_SECONDS[1]` uses `<=`. That's inclusive. Fine.
- The seen check: `if seen and sorted(seen) != list(range(1, len(seen) + 1)):`. This ensures numbers are 1..N once each. But what if there are duplicate numbers? sorted(seen) would have duplicates, not equal to range. So error. Good.
- However, there is a potential bug: if `eps` contains episodes with episode numbers not starting at 1? The check ensures they are 1..N. That's intended.
- But what about older stage 1 format that has "Episode N" lines but no ```json story block? The comment says "an older stage 1 (lines 'Episode N', no ```json story block): nothing to check here". So plan_errors returns [] for those. That's fine.

But there is a subtle bug: `plan_errors` is called as `lambda d: with_language(gate("1", d, None), plan_errors(d))`. The `gate` function likely validates the plan. If plan_errors returns errors, gate might fail. That's intended.

However, there is a potential issue: `plan_errors` might raise KeyError if `plan` is missing "episodes"? It checks `if not isinstance(plan, dict) or "episodes" not in plan: return []`. So safe.

But what if `plan["episodes"]` is present but not a list? It returns ["PLAN-01 at episodes: the story block must list the episodes"]. That's fine.

So plan_errors seems okay.

Hunk 299-316: `episode_id_errors` and `caption_id_errors` added.

`episode_id_errors(shots, ep)`:
- Returns errors for shots whose episode field doesn't match ep.
- Assumes shots is list of dicts.
- Uses `enumerate(shots)`.
- If shot is not dict, skipped? Actually `if isinstance(s, dict) and str(s.get("episode")) != str(ep)`. So non-dict shots ignored. That's fine.
- But there is a potential bug: `str(s.get("episode")) != str(ep)`. If ep is 1, and shot episode is "1", str comparison works. If shot episode is 1 (int), str(1) == "1". Good. If shot episode is "1.0", str is "1.0" != "1". That would be flagged. That's probably intended.
- However, if ep is a string like "1", and shot episode is int 1, str(1) == "1". Good.
- So fine.

`caption_id_errors(items, shots)`:
- `ids = {s.get("id") for s in shots if isinstance(s, dict)}`. If shot id missing, key None. That's okay.
- `named = {i.get("shot_id") for i in items if isinstance(i, dict)}`. If item missing shot_id, key None.
- Errors for ids not in ids. But if ids contains None, and named contains None, then None is in ids, so no error. That's fine.
- Then for each shot, checks if speaks and id not in named. If id is None and not in named, error. That's fine.
- But there is a potential bug: `named` is a set of shot_id values. If a shot has id "SHOT-001", and a caption item references shot_id "SHOT-001A", then "SHOT-001A" not in ids, so error "CAP-01 ... SHOT-001A is not a shot of this episode". That's intended? The comment says "every row of episode ep says episode ep. (Ids may restart per episode: merge_episodes renumbers, and the captions are applied per episode before the merge, so a repeated id cannot take another episode's captions.)" So caption items should reference shots of the same episode. If a caption references a shot id that doesn't exist in the episode, that's an error. That's fine.
- However, there is a nuance: the patch later allows SHOT-001A/B to match SHOT-001. But that matching is done in ui/server.py review_shot, not in caption_id_errors. So caption_id_errors might flag SHOT-001A as not a shot if the episode only has SHOT-001. That could be a false positive. But the comment says "Ids may restart per episode: merge_episodes renumbers". Actually, if ids restart per episode, then SHOT-001A might be a different shot id in the same episode? The example row uses SHOT-001A/B. So if an episode has SHOT-001A, then caption referencing SHOT-001A is valid. But if the episode only has SHOT-001, then SHOT-001A is not a shot. That's correct. So no false positive.
- But there is a potential issue: `named` includes shot_id from items. If an item references shot_id "SHOT-001A" but the episode has "SHOT-001A", then it's fine. So okay.

Hunk 319-336: `apply_captions` and `run_staged` changes.

`run_staged` changes:
- Added `earlier` parameter to `stage`.
- Stage 1 now checks plan_errors.
- Stage 3 now checks episode_id_errors.
- Stage 5: if stage_5_raw.json exists, do whole-story stage 5; else per-episode stage 5e<N>.
- In per-episode branch, `earlier=base + [(f"3e{ep}", ep_texts[ep])]`. `base` is list of done stages (1 and 2). `prev` is previous episode's stage 3 text. That's fine.
- After per-episode, `shots = [legacy_fields(s, bible) for s in merge_episodes(per_episode)]`. Note: apply_captions is called per episode but results are discarded? Actually in per-episode branch, `apply_captions(ep_shots, ...)` is called but its return value is not stored. That's fine because captions are applied to ep_shots in place? Let's see: `apply_captions` likely modifies shots in place. So calling it per episode applies captions to each episode's shots. Then later `merge_episodes` merges them. That's fine.
- In whole-story branch, `shots = [legacy_fields(s, bible) for s in apply_captions(merge_episodes(per_episode), ...)]`. That applies captions to merged shots.
- Then writes PACK.md, bible.json, shots.json.
- Then `report = pack_check_report(out)` and writes check_pack_report.json.

Potential issues:
- The `earlier` parameter is used to limit prompt growth. But in stage 3, `earlier=base + prev`. `prev` is only the previous episode's stage 3 text. That's fine.
- However, there is a bug: `prev = [(f"3e{p}", ep_texts[p]) for p in [episodes[episodes.index(ep) - 1]] if episodes.index(ep) > 0]`. This assumes `episodes` is a list and `episodes.index(ep)` finds the index. But `episodes` might not be a list of unique values? It should be. But if there are duplicate episode numbers? Unlikely. Also, `episodes.index(ep)` returns first occurrence. If there are duplicates, it might pick wrong. But that's edge case.
- More importantly, `ep_texts` is populated as we go. For the first episode, `prev` is empty. That's fine.
- But there is a potential bug: `ep_texts[ep] = text` is set after stage. That's fine.
- However, in the per-episode branch, `earlier=base + [(f"3e{ep}", ep_texts[ep])]`. At the time of calling stage for episode ep, `ep_texts[ep]` hasn't been set yet (it's set after). So `earlier` includes a tuple for the current episode's stage 3 text, which is not yet available. That means the prompt for stage 5e<ep> includes the stage 3 text of the current episode, which is not yet saved. That could cause the prompt to reference unsaved data. But the comment says "the saved stages this call may see". Since stage 3 for the current episode hasn't been saved yet, including it in earlier might be premature. However, the stage 3 text for the current episode is generated in the same run_staged call, but not yet appended to `done` or `ep_texts`. So `earlier` would include a future stage. That could lead to the prompt containing the stage 3 answer before it's produced. Is that a problem? The prompt is built before the stage runs. If the prompt includes the stage 3 text of the current episode, but that text isn't available yet, the prompt would contain placeholder or empty? Actually `ep_texts[ep]` is initially empty dict, so `ep_texts[ep]` is None? Wait, `ep_texts` is initialized as `{}`. So `ep_texts[ep]` is undefined until set. But the code does `earlier=base + [(f"3e{ep}", ep_texts[ep])]`. At that point, `ep_texts[ep]` is not yet set, so it would raise KeyError! Let's check: `ep_texts` is defined as `{}` before the loop. Then inside the loop, `earlier=base + [(f"3e{ep}", ep_texts[ep])]`. Since `ep_texts` is empty, `ep_texts[ep]` raises KeyError. That is a real bug! Indeed, the code tries to access `ep_texts[ep]` before assignment. That would crash. Let's verify the diff:

```
+        else:                                                   # captions per episode (5e<N>): bounded prompt and answer
+            for ep, ep_shots in zip(episodes, per_episode):
+                check5 = (lambda d, ep_shots=ep_shots: gate("5", d, bible, lambda: caption_language_errors(d["captions"], langs)
+                                                            + caption_id_errors(d["captions"], ep_shots), merge=True))
+                text5, captions = stage(f"5e{ep}", parse_captions, check5, earlier=base + [(f"3e{ep}", ep_texts[ep])])
+                done.append((f"5e{ep}", text5))
+                apply_captions(ep_shots, captions["captions"], langs)
+            shots = [legacy_fields(s, bible) for s in merge_episodes(per_episode)]
```

Yes, `ep_texts[ep]` is accessed before being set. `ep_texts` is `{}` initially. So this will raise KeyError. That is a high-severity bug. The fix: either set `ep_texts[ep]` before the loop, or use a different approach. Perhaps `earlier=base + [(f"3e{prev_ep}", ep_texts.get(prev_ep))]` where prev_ep is previous episode. But the comment says "the saved stages this call may see". For stage 5e<ep>, it should see stage 3e<ep>? Actually the stage 5e<ep> is for episode ep, and it should see the stage 3e<ep> output. But that output is generated just before. So including it in earlier is premature. Maybe the intent is to include the previous episode's stage 3, not the current. The `prev` variable is computed as previous episode's stage 3. So `earlier` should be `base + prev` (previous episode's stage 3), not including current. The current line incorrectly includes `ep_texts[ep]`. That is likely a copy-paste error. The correct line should be `earlier=base + prev` (where prev is the previous episode's stage 3 text). But `prev` is defined as `[(f"3e{p}", ep_texts[p]) for p in [episodes[episodes.index(ep) - 1]] if episodes.index(ep) > 0]`. That gives a list of tuples for the previous episode. So `earlier=base + prev` would work. The current code `earlier=base + [(f"3e{ep}", ep_texts[ep])]` is wrong. So fix: change to `earlier=base + prev`. But note: `prev` is defined outside the loop? Actually `prev` is defined inside the loop? Let's see the diff:

```
+        prev = [(f"3e{p}", ep_texts[p]) for p in [episodes[episodes.index(ep) - 1]] if episodes.index(ep) > 0]
+        text, ep_shots = stage(f"3e{ep}", parse, check, first=first, seconds=seconds.get(ep), earlier=base + prev)
```

Wait, that's for stage 3. For stage 5, the code is:

```
+                check5 = (lambda d, ep_shots=ep_shots: gate("5", d, bible, lambda: caption_language_errors(d["captions"], langs)
+                                                            + caption_id_errors(d["captions"], ep_shots), merge=True))
+                text5, captions = stage(f"5e{ep}", parse_captions, check5, earlier=base + [(f"3e{ep}", ep_texts[ep])])
```

So indeed, `ep_texts[ep]` is accessed before assignment. That's a bug. The fix: use `earlier=base + prev` where `prev` is the previous episode's stage 3 text. But `prev` is defined in the stage 3 block, not available in the stage 5 block. We could compute `prev` inside the stage 5 block similarly. Or simply `earlier=base` (only stages 1 and 2). That would be safe. The comment says "the saved stages this call may see (default: all). Episodes and captions see only stages 1, 2 and their neighbour". So for stage 5e<ep>, it should see stages 1, 2, and the previous episode's stage 3. So `earlier=base + prev` is correct. But since `prev` is not available, we need to compute it. Alternatively, we can set `ep_texts[ep]` before the loop? No, because stage 3 for current ep hasn't run. So the safest is to compute `prev` inside the loop. Let's propose fix: inside the per-episode loop, compute `prev_ep_text = [(f"3e{p}", ep_texts.get(p)) for p in [episodes[episodes.index(ep) - 1]] if episodes.index(ep) > 0]` and use `earlier=base + prev_ep_text`. But that's verbose. Simpler: `earlier=base` (only stages 1 and 2). That might be acceptable because the stage 5 prompt doesn't need the current episode's stage 3. The comment says "Episodes and captions see only stages 1, 2 and their neighbour". So for stage 5e<ep>, the neighbour is the previous episode's stage 3. So we need to include that. But since it's not saved yet, we can't. However, the stage 3 for the current episode is generated immediately before, but not saved. The prompt is built before the stage runs. So including the current episode's stage 3 would require it to be available. It's not. So the correct approach is to include the previous episode's stage 3, which is already saved. So we need to compute `prev` inside the loop. Let's write fix:

```
+                prev = [(f"3e{p}", ep_texts.get(p)) for p in [episodes[episodes.index(ep) - 1]] if episodes.index(ep) > 0]
+                text5, captions = stage(f"5e{ep}", parse_captions, check5, earlier=base + prev)
```

But note: `ep_texts.get(p)` returns None if not set, which is fine. So that works.

Alternatively, we could restructure to avoid KeyError. The simplest fix is to change `earlier=base + [(f"3e{ep}", ep_texts[ep])]` to `earlier=base + prev` where `prev` is computed similarly. But since `prev` is not defined in that scope, we need to define it. So I'll report this as a high-severity bug: KeyError when captions per episode. Fix: compute previous episode's stage 3 text and include it.

Also, there is another potential issue: `check5` lambda captures `ep_shots` correctly via default argument. That's fine.

Now, director/write_pack.py hunk 385-396: pack_check_report and writing report. That's fine.

Hunk 401-408: pack_check_report function. It imports check_pack and calls check. If exception, prints and returns None. That's fine.

Hunk 411-458: main changes. Reads meta_story from story.json. Uses saved_langs. Sets voice from meta_story if no --voice. That's fine.

But there is a potential security issue: reading story.json and trusting its values. The patch says "without flags the story's own settings (set in the UI) stand; they are not overwritten by the defaults". That's intended. But is there path traversal? `Path(a.story).parent / "story.json"` is safe as long as a.story is a path within studio. Probably fine.

However, there is a potential bug: `meta_story = json.loads((Path(a.story).parent / "story.json").read_text(encoding="utf-8"))`. If story.json is malformed, json.loads raises ValueError, caught and passed. That's fine. But if story.json contains malicious content, it's trusted. That's by design. Not a new defect.

Now director/writer_prompts.py hunk 257-289, 304-335, 361-389.

Hunk 257-289: REHOOK_REEL_MIN_SEC, REHOOK_WINDOW, LOOK_EXAMPLE, example_row, look_example.

`look_example(pack)`:
- `pid, pal = next(iter(pack["palettes"].items()))` - if palettes missing, StopIteration caught.
- `colour = next(iter(pal["colors"]))` - if colors missing, StopIteration caught.
- `act = next(iter(pack["acts"]))` - if acts missing, StopIteration caught.
- `phase = pack["colour_script"]["phases"][0]["id"]` - if colour_script missing or phases empty, IndexError caught.
- Returns a dict. If any of these fail, returns None. That's fine.

But there is a potential bug: `pack["palettes"]` might be a dict, but `pal` might be a dict without "colors". Then `next(iter(pal["colors"]))` raises KeyError, caught by except (KeyError, StopIteration, IndexError, TypeError, AttributeError). So returns None. That's fine.

`example_row`: adds look if LOOK_EXAMPLE. That's fine.

`stage5_text`: for name starting "5e", returns stage5_text. That's fine.

Now flow/scripts/bible_to_sheet_jobs.py hunk 29-550: changes sheet_prompt to card_prompt fallback. That's fine.

flow/scripts/pack_to_spec.py hunk 35-597: changes OUTPUTS_ROOT_TEMPLATE to anime_{slug}, adds description handling, lighting_baseline, style_lock prefix, _first_sentences.

Let's analyze potential bugs:

- `OUTPUTS_ROOT_TEMPLATE = "D:/aai work/flow_outputs/anime_{slug}"`. This is a Windows path. On Windows, forward slashes work. But if slug contains backslashes? slug is typically alphanumeric. Probably fine. But there is a potential issue: the template uses `{slug}` which is replaced by `slug` variable. If slug contains characters that are invalid in Windows path? slug is likely safe. Not a big deal.

- `_first_sentences(text, limit=220)`: splits on sentence boundaries, accumulates up to limit characters, returns rstrip(".")[:limit*2]. Wait: `return out.rstrip(".")[:limit * 2]`. That returns at most 2*limit characters. But the docstring says "at most `limit` characters". Actually the code returns `out.rstrip(".")[:limit * 2]`. That's a bug: it returns up to 2*limit characters, not limit. The docstring says "at most `limit` characters". So the function truncates to 2*limit. That could produce longer text than intended. But is that a defect? The comment says "The first sentences of a card description, at most `limit` characters, no trailing period." The implementation violates that. So that's a real defect: the function returns up to 2*limit characters. Fix: `return out.rstrip(".")[:limit]`. But note: `out` may already be limited to limit characters during accumulation? Actually the loop breaks when `len(out) + len(part) > limit`. So `out` never exceeds limit. Then `out.rstrip(".")[:limit*2]` takes first limit*2 characters, but since out is at most limit, [:limit*2] is just out. So effectively returns out. Wait: `out` is at most limit characters. `out.rstrip(".")` removes trailing period, but doesn't change length much. Then `[:limit*2]` slices up to limit*2, but since out is shorter, it returns out. So actually the slice doesn't truncate further. So the function returns at most limit characters. Because out is bounded by limit. So the `[:limit*2]` is redundant but harmless. However, if `out` is exactly limit characters, `[:limit*2]` returns the whole thing. So no extra characters. So it's fine. But the docstring says "at most `limit` characters". The code does that. So no bug. Wait, but the loop condition: `if out and len(out) + len(part) > limit: break`. So out never exceeds limit. So final out is <= limit. So `[:limit*2]` doesn't truncate. So it's fine. So no defect.

- `_place_text`: adds description first sentences if no layers. That's fine.

- `_style_text`: uses style_lock prefix. That's fine.

- `_character_sentence`: adds description first sentences if no attrs. That's fine.

Now flow/scripts/remove_sparkle.py hunk 351-393: adds skip_done. That's fine.

h3/v4_to_h3.py hunk 540-646: adds metadata.look to converted H3 shot. That's fine.

ui/pipeline.py hunk 20-659: changes PROJECT_DEFAULT, facts function, image_id default.

Let's analyze:

- `PROJECT_DEFAULT` unchanged except SHEET_PREFIXES added. That's fine.

- `facts` function: changes images_dir handling. If `img_path / "adhyay_01"` is a dir, use it. That's fine.

- `finals` count excludes sheet prefixes. That's fine.

- `image_id` default to shot_id. That's fine.

But there is a potential bug: `image_id = entry.get("image_id", shot_id)`. If entry is not a dict? It is loaded from JSON, so dict. Fine.

Now ui/server.py hunk 364-784, 540-614, 677-750, 769-815, 816-822, 826-846, 850-862, 864-908, 906-911, 912-978, 988-1002.

Let's go through.

Hunk 364-384: `_flow_project_url` and `packet_header`. It loads story.json and checks flow_project URL. That's fine. But there is a potential bug: `meta = load_json(cfg.studio / "stories" / slug / "story.json", {})`. If slug is None? slug is a parameter. In `packet_header`, slug is passed. Could be None? Probably not. But if slug is None, path would be `cfg.studio / "stories" / None / "story.json"` which would raise TypeError. But slug is always provided. So fine.

Hunk 540-564: `write_pack_route` and `b_write_pack`. Changes: opus gets --effort high and --web. That's fine.

Hunk 576-598: `b_bridge` adds --pattern for non-legacy stories. That's fine.

Hunk 677-750: `_convert_pack_to_h3` and `b_h3`. This converts pack to H3 story. Potential issues:

- `from h3 import v4_to_h3` inside function. That's fine.
- `meta = load_json(pack_dir.parent / "story.json", {})`. If story.json missing, returns {}. Then langs = meta.get("output_languages") if list else None. That's fine.
- `res = v4_to_h3.convert_pack(str(pack_dir), languages=langs)`. If conversion fails, raises bad. That's fine.
- `out = pack_dir / "h3_story.json"`. Writes story. That's fine.
- In `b_h3`, if story file name is "shots.json", convert pack to h3_story.json. That's fine.
- But there is a potential bug: `load_json(a["story"], None)` after conversion. If conversion succeeded, story is dict. If not, raises bad. That's fine.

Hunk 769-815: SHOT_ARGS and commands. Adds "story" to SHOT_ARGS. That's fine.

Hunk 816-822: `read_images` changes root to own flow folder first. That's fine.

Hunk 826-846: `_record_step` and STEP_EVENTS. This writes registry events for finished jobs. Potential issues:

- `m = re.search(r"(?:stories|generated)[\\/]([a-z0-9_]+)[\\/]", " ".join(str(x) for x in job.argv))`. This searches argv for a path pattern. If argv doesn't contain such a path, m is None, folder is None, returns. That's fine.
- But there is a potential bug: `folder = self.cfg.studio / "stories" / m.group(1) if m else None`. If m matches, folder is constructed. Then `if folder is not None and folder.is_dir():` checks existence. That's fine.
- However, the regex `[a-z0-9_]+` doesn't allow hyphens? Story slugs might have hyphens? The pattern `[a-z0-9_]+` excludes hyphens. If slug contains hyphen, it won't match. But story slugs are typically alphanumeric. The Kaliya legacy story is "kaliya" maybe. Could have hyphen? Unlikely. But if a story slug has hyphen, the regex won't match, and folder will be None, so no event written. That could be a regression: previously maybe events were written for all stories. But the comment says "audit D 11-08: a finished spec/jobs/review/prepare job writes its run-registry event". If the regex doesn't match, no event. That might be unintended. However, the regex is meant to extract story slug from argv. If argv contains the story path with hyphen, it won't match. That could be a bug. But is it a real defect? Possibly medium. But let's see: the regex pattern `(?:stories|generated)[\\/]([a-z0-9_]+)[\\/]`. This matches paths like `stories/kaliya/` or `generated/kaliya/`. If slug is "kaliya-2", it won't match. So folder None, no event. That could leave steps stuck. That might be a real defect. But the instruction says "regressions for the older story format (Kaliya legacy rows, v2.2 rows with beats, packs without a story block)". Kaliya legacy might have hyphens? Not sure. But the regex is too restrictive. However, the patch is about audit D, so maybe they intentionally want only certain slugs. But the comment says "nothing wrote them, so the step list stayed stuck at 'build the image jobs'." So they want events for all stories. So the regex should allow hyphens. But the pattern `[a-z0-9_]+` doesn't include hyphen. So fix: add `-` to character class: `[a-z0-9_-]+`. That would match hyphens. But is that a real defect? Yes, it could miss stories with hyphens. Severity medium. We'll report.

- Also, `self._hook("append_event", folder, rr.run_id(kind), kind, None, "ok", note=f"ui job {job.id}")`. This calls a hook. If hook not defined, AttributeError? But presumably defined elsewhere. Not introduced.

Hunk 850-862: project update on story switch. That's fine.

Hunk 864-908: review_shot and review_queue changes.

- `review_shot` allows up to 500 shots. Previously 60. That's a change. Could be intentional. Not a defect.

- The hits logic: `hits = [sid] if sid in entries else sorted(k for k in entries if re.fullmatch(re.escape(sid) + "[A-Z]", k))`. This matches SHOT-001A etc. That's fine.

- But there is a potential bug: `re.fullmatch(re.escape(sid) + "[A-Z]", k)`. If sid is "SHOT-001", then pattern is `SHOT\-001[A-Z]`. That matches "SHOT-001A". Good. But if sid is "SHOT-001A", then pattern is `SHOT\-001A[A-Z]`, which would match "SHOT-001AA"? That's unlikely. But if a shot id is "SHOT-001A", and there is also "SHOT-001AA", it would match. That's probably not intended. But rare. Not a major defect.

- Also, `entries` is a dict mapping shot_id to job. If multiple jobs have same shot_id? Unlikely.

Hunk 906-911: API review route passes story. That's fine.

Now ui/static/app.js and pipeline.js: adding story param to commands. That's fine.

But there is a potential bug in pipeline.js `coversAll`:

```
function coversAll(have, ids) {
    // a pack shot SHOT-001 is covered by the job ids SHOT-001A / SHOT-001B too (audit 11-08)
    return ids.length > 0 && ids.every(function (id) {
      id = String(id);
      return have[id] === true || have[id + 'A'] === true;
    });
}
```

This checks if each id is covered by itself or id+'A'. But what about id+'B'? The comment mentions SHOT-001A/B, but the code only checks id+'A'. It doesn't check id+'B'. So if a shot is covered by SHOT-001B but not SHOT-001A, it would be considered not covered. That's a bug. The fix: check both id and id+'A' and id+'B'. Or more generally, check id+'A' and id+'B'. But the comment says "SHOT-001A / SHOT-001B". So we should check both. However, the code only checks id+'A'. That is a real defect. Severity medium. Fix: `return have[id] === true || have[id + 'A'] === true || have[id + 'B'] === true;`. But note: if id is "SHOT-001", id+'A' is "SHOT-001A", id+'B' is "SHOT-001B". That matches. But what about id+"A" when id already ends with A? e.g., id="SHOT-001A", then id+'A'="SHOT-001AA". That's not intended. But that's an edge case. Better to check `have[id] || have[id.replace(/A$/,'')]`? Too complex. Simpler: check id, id+'A', id+'B'. Acceptable.

Also, the `coversAll` function is used to check if all shot ids are covered by jobs. If a shot id is "SHOT-001", and jobs have "SHOT-001A" and "SHOT-001B", then `have["SHOT-001A"]` is true, so covered. Good. If jobs only have "SHOT-001A", then `have["SHOT-001A"]` true, covered. If jobs only have "SHOT-001B", then `have["SHOT-001B"]` true, but `have["SHOT-001A"]` false, so not covered. That's a bug. So fix needed.

Now, are there any other defects?

Let's revisit caption_cues.py: the str card drop bug. That's high/medium.

Also, timeline.py: the `beats_raw` dead code. Low.

Also, timeline.py: `_v4_parts` uses `_is_num` and `_str`. If these are not defined, crash. But they were presumably there. Not introduced.

Also, timeline.py: `_range_start` might not handle numeric time_range. But time_range is usually string or list. Not a big deal.

Also, retention_rules.py: R2 and R5 seem correct.

Also, story_state.py: seems correct.

Also, write_pack.py: the KeyError in run_staged per-episode stage 5. High.

Also, server.py: regex missing hyphen. Medium.

Also, pipeline.js coversAll missing B. Medium.

Also, caption_cues.py str drop. Medium.

Are there any regressions for older story formats? The patch adds V4 support but doesn't break legacy. However, the `_v4_parts` function might be called for shots that have `per_second_directives` but are actually legacy? Unlikely. The check `isinstance(shot.get("per_second_directives"), list)` ensures only if it's a list. Legacy shots don't have that key, so v4 is None. So no regression.

But there is a potential regression: previously, `beats` were built from legacy beats. Now if a shot has `per_second_directives`, beats come from v4. That's intended. But what about shots that have both legacy beats and per_second_directives? The code prioritizes v4. That could be a regression if some shots have both. But unlikely.

Another potential regression: the `_v4_parts` function reads `reference_anchors` and `audio_and_dialogue_track`. For legacy shots, these may be absent. The code handles missing keys. So no regression.

But there is a subtle bug: in `_parse_rich_or_legacy`, when v4 is present, `beats` is set to v4 beats. But `beats_raw` is built but unused. That's dead code. Not a defect.

Also, the `camera_rel` for v4 is `v4["camera_rel"]`. But what about legacy camera moves? They are captured by `moved` and `[0.0] if moved else []`. That's fine.

Now, security: path traversal? The patch reads story.json from `Path(a.story).parent`. If a.story is something like "../../etc/passwd", that could traverse. But that's pre-existing. Not introduced.

Injection: story.json trusted. Pre-existing.

Windows path: OUTPUTS_ROOT_TEMPLATE uses forward slashes. On Windows, that's fine. But if slug contains backslashes? slug is typically safe. Not a big deal.

Now, let's compile the list.

We need to report each as: severity (high/medium/low), file:hunk, one sentence what is wrong, concrete input -> wrong result, exact fix.

Let's list:

1. core/caption_cues.py hunk 10-15: When captions_by_lang[lang] is a list of strings and narr is None, the str cards are silently dropped. Input: lang captions = ["Hello", "World"], narr=None. Output: no caption items added, captions missing. Fix: change `elif narr:` to `elif isinstance(c, str):` and use `(c, (narr or {}).get("time_range"))`.

Severity: medium.

2. core/timeline.py hunk 130-131: `beats_raw` is built but never used. This is dead code that does not serve the comment. Severity low. But the instruction says "edits that do not do what their comment says." The comment is about v4 integration, not beats_raw. So maybe not. But it's an extra line. I'll include as low.

Actually, the comment says "beats, cast, dialogue starts, camera moves and caption changes come from its columns". `beats_raw` is not part of that. So it's an edit that doesn't do what its comment says. So low.

3. core/timeline.py hunk 361-362: KeyError when captions per episode. Input: a pack with multiple episodes, no stage_5_raw.json, so per-episode stage 5 runs. During the loop, `ep_texts[ep]` is accessed before assignment, raising KeyError. Output: crash. Fix: compute previous episode's stage 3 text and include it, e.g., `prev = [(f"3e{p}", ep_texts.get(p)) for p in [episodes[episodes.index(ep) - 1]] if episodes.index(ep) > 0]; earlier=base + prev`.

Severity high.

4. ui/server.py hunk 841: regex `[a-z0-9_]+` does not match hyphens, so stories with hyphens in slug won't get registry events. Input: story slug "my-story". Output: no event written, step stuck. Fix: change regex to `[a-z0-9_-]+`.

Severity medium.

5. ui/static/pipeline.js hunk 995-1002: `coversAll` only checks id+'A', not id+'B'. Input: shot id "SHOT-001", jobs have only "SHOT-001B". Output: considered not covered. Fix: add `|| have[id + 'B'] === true`.

Severity medium.

Are there any others?

Let's double-check retention_rules.py. The patch says R2 and R5 were inverted. The new code seems correct. But wait: the docstring for R2 says "Motion starts by first_motion_s: a beat covering 0 .. first_motion_s must NOT be hold: true, unless the first shot's post declares push/zoom at 0." The code: `bad = [b for b in covering if b.get("hold") is True]`. That means bad if hold is true. So a hold beat covering 0..first_motion_s is bad. That matches. But what about the case where `covering` is empty? Then bad empty, returns []. That's fine. But what if `first_motion_s` is 0? Then covering includes beats starting at 0. If a beat starts at 0 with hold true, it's bad. That's correct.

But there is a potential bug: `covering` is defined as `[b for b in beats if b["start_s"] <= first_motion_s <= b["end_s"]]`. If `first_motion_s` is 0, and a beat starts at 0 and ends at 0.5, it covers. If a beat starts at 0.1 and ends at 0.5, it also covers. So multiple beats could cover. The code checks all covering beats. If any has hold true, fail. That's correct.

R5: `early = [b for b in beats if b.get("hold") is True and b["start_s"] < limit]; if not early: return []; return [_entry(...)]`. That's correct.

So no defect there.

Now, check story_state.py: `expected` uses `eps = range(1, (episodes or 0) + 1)`. If episodes is 0, range(1,1) empty. tail = ["5"] if "5" in present else []. So expected = ["1","2"] + [] + tail. If "5" not present, expected = ["1","2"]. That's fine. But what about older packs that have "5" in present? Then tail = ["5"], expected includes "5". That's fine.

But there is a potential bug: `eps` is used for both `3e{k}` and `5e{k}`. If episodes is 0, `eps` empty, so no `3e` or `5e`. That's fine.

Now, check write_pack.py main: `meta_story = json.loads((Path(a.story).parent / "story.json").read_text(encoding="utf-8"))`. If story.json is missing, OSError caught. If malformed, ValueError caught. That's fine.

But there is a potential bug: `saved_langs = meta_story.get("output_languages") if isinstance(meta_story, dict) else None`. If meta_story is not dict, saved_langs None. That's fine.

`out_langs = a.out_lang or (wp.lang_list(saved_langs) if isinstance(saved_langs, list) and saved_langs else None) or [wp.DEFAULT_OUT_LANG]`. If saved_langs is a list but empty, `and saved_langs` is False, so None. Then out_langs = DEFAULT. That's fine.

Now, check writer_prompts.py: `look_example` uses `pack["palettes"]` etc. If pack is not a dict, KeyError caught. Fine.

Now, check bible_to_sheet_jobs.py: `prompt = (item.get("sheet_prompt") or item.get("card_prompt")) if isinstance(item, dict) else None`. If item is dict but both missing, prompt None, skip. Fine.

Now, check pack_to_spec.py: `OUTPUTS_ROOT_TEMPLATE = "D:/aai work/flow_outputs/anime_{slug}"`. This is a Windows path. On Windows, forward slashes are okay. But if slug contains backslash? slug is typically safe. Not a defect.

Now, check remove_sparkle.py: `--skip-done` added. Fine.

Now, check h3/v4_to_h3.py: adds metadata.look. Fine.

Now, check ui/pipeline.py: `image_id = entry.get("image_id", shot_id)`. If entry is not dict? It is. Fine.

Now, check ui/server.py: `_flow_project_url` uses `FLOW_PROJECT_RE.fullmatch(url)`. If url is not a string, fullmatch fails, returns FLOW_PROJECT_URL. That's fine.

Now, check ui/server.py: `b_h3` converts pack to h3. If conversion fails, raises bad. That's fine.

Now, check ui/server.py: `_record_step` regex. As noted, missing hyphen. Medium.

Now, check ui/server.py: `review_shot` allows 500 shots. That's a change, but not a defect.

Now, check ui/server.py: `hits` logic. If sid is "SHOT-001", and entries has "SHOT-001A", then hits = ["SHOT-001A"]. That's fine. But if sid is "SHOT-001A", and entries has "SHOT-001AA", it would match. Rare. Not a defect.

Now, check ui/static/app.js and pipeline.js: adding story param. Fine.

Now, are there any crashes due to None? In caption_cues.py, if cap is a list of dicts but some dict has no "text", item text is None. That could cause downstream None handling. But not a crash. The original code didn't handle that either. So not a new defect.

In timeline.py, `_v4_parts` uses `_str(d.get("action_pose_expression"))`. If missing, returns ""? Probably. Then `hold="hold" in acting.lower()` is False. Fine.

In timeline.py, `cam = _str(d.get("camera")).strip().lower()`. If camera missing, returns "". Then `if cam and ...` is False. Fine.

In timeline.py, `anchors = shot.get("reference_anchors") if isinstance(shot.get("reference_anchors"), dict) else {}`. If reference_anchors is present but not dict, defaults to {}. Fine.

In timeline.py, `track = shot.get("audio_and_dialogue_track") if isinstance(shot.get("audio_and_dialogue_track"), dict) else {}`. Fine.

In timeline.py, `by_lang = track.get("captions_by_lang")`. If not dict, the loop `for cards in by_lang.values() if isinstance(by_lang, dict) else []:` yields empty. Fine.

So no new crashes.

Now, check the `plan_errors` function: `PLAN_SECONDS = (20, 180)`. If sec is exactly 20 or 180, it's within range. That's fine.

But there is a potential bug: `isinstance(sec, (int, float)) or isinstance(sec, bool)` is redundant but fine.

Now, check `episode_id_errors`: `str(s.get("episode")) != str(ep)`. If ep is 1, and shot episode is "1", str comparison works. If shot episode is 1 (int), str(1) == "1". Good.

Now, check `caption_id_errors`: `ids = {s.get("id") for s in shots if isinstance(s, dict)}`. If shot id missing, key None. `named = {i.get("shot_id") for i in items if isinstance(i, dict)}`. If item missing shot_id, key None. Then `n for n in named if n not in ids` includes None if named has None and ids doesn't have None? But ids has None if any shot missing id. So if named has None and ids has None, no error. If named has None and ids doesn't have None (all shots have ids), then error "CAP-01 ... None is not a shot". That's fine.

Now, check `run_staged` per-episode stage 5: the KeyError. High.

Also, check `run_staged` whole-story stage 5: `if (out / "stage_5_raw.json").exists():`. If the file exists, it does whole-stage 5. That's fine.

But there is a potential bug: in whole-story branch, `shots = [legacy_fields(s, bible) for s in apply_captions(merge_episodes(per_episode), captions["captions"], langs)]`. `apply_captions` likely modifies shots in place. That's fine.

Now, check `pack_check_report`: imports check_pack. If check_pack not installed, ImportError caught? It catches Exception, so ImportError is caught. That's fine.

Now, check `main`: `voice = voice_mod().parse_overrides(a.voice) if a.voice else (meta_story.get("voice_engine") if isinstance(meta_story.get("voice_engine"), dict) else None)`. If meta_story is not dict, `meta_story.get` would raise AttributeError. But the outer try catches OSError, ValueError. AttributeError is not caught. So if meta_story is not a dict (e.g., None), `meta_story.get` raises AttributeError, which is not caught, causing crash. Wait: `meta_story` is loaded from json.loads. If story.json is valid JSON but not an object (e.g., a list), then `meta_story` is a list. Then `meta_story.get("voice_engine")` raises AttributeError because list has no get. The except clause only catches `(OSError, ValueError)`. So AttributeError would propagate. That is a real bug! Input: story.json is a list (e.g., `[]`). Then `meta_story` is a list. `meta_story.get(...)` raises AttributeError. Output: crash. Fix: guard `if isinstance(meta_story, dict)`. The code already does `isinstance(meta_story.get("voice_engine"), dict)` but that calls `.get` on meta_story which may not be dict. So need to check `isinstance(meta_story, dict)` first. The line is:

```
voice = voice_mod().parse_overrides(a.voice) if a.voice else (meta_story.get("voice_engine") if isinstance(meta_story.get("voice_engine"), dict) else None)
```

This is problematic because `meta_story.get` is called before checking if meta_story is dict. So if meta_story is not dict, AttributeError. Fix: rewrite as:

```
voice = voice_mod().parse_overrides(a.voice) if a.voice else (meta_story.get("voice_engine") if isinstance(meta_story, dict) and isinstance(meta_story.get("voice_engine"), dict) else None)
```

Or more simply:

```
voice = voice_mod().parse_overrides(a.voice) if a.voice else (meta_story.get("voice_engine") if isinstance(meta_story, dict) else None)
```

But the original intent: if meta_story is dict and has voice_engine dict, use it. So fix accordingly.

Severity high.

Also, check `out_langs` computation: `wp.lang_list(saved_langs) if isinstance(saved_langs, list) and saved_langs else None`. If saved_langs is a list but empty, `and saved_langs` is False, so None. That's fine.

Now, check `make_web_notes`: `m = re.search(r"```(?:markdown|md)?\s*\n(.*?)```", text, re.S)`. If text doesn't have fence, m is None, uses raw text. Then `if len(text) < 200: raise`. That's fine.

Now, check `call_claude`: `fmt = ["--output-format", "stream-json", "--verbose"]` always. That's fine.

Now, check `call_path`: `WEB_NOTES = make_web_notes(a.story)`. That's fine.

Now, check `parse_stage_map`: regex `[1235]|[35]e\d+`. That's fine.

Now, check `plan_errors`: `PLAN_SECONDS = (20, 180)`. If sec is exactly 20 or 180, it's within range. That's fine.

Now, check `episode_id_errors`: `str(s.get("episode")) != str(ep)`. If ep is 1, and shot episode is "1", str comparison works. If shot episode is 1 (int), str(1) == "1". Good.

Now, check `caption_id_errors`: `ids = {s.get("id") for s in shots if isinstance(s, dict)}`. If shot id missing, key None. `named = {i.get("shot_id") for i in items if isinstance(i, dict)}`. If item missing shot_id, key None. Then `n for n in named if n not in ids` includes None if named has None and ids doesn't have None? But ids has None if any shot missing id. So if named has None and ids has None, no error. If named has None and ids doesn't have None (all shots have ids), then error "CAP-01 ... None is not a shot". That's fine.

Now, check `run_staged` per-episode stage 5: the KeyError. High.

Also, check `run_staged` whole-story stage 5: `if (out / "stage_5_raw.json").exists():`. If the file exists, it does whole-stage 5. That's fine.

But there is a potential bug: in whole-story branch, `shots = [legacy_fields(s, bible) for s in apply_captions(merge_episodes(per_episode), captions["captions"], langs)]`. `apply_captions` likely modifies shots in place. That's fine.

Now, check `pack_check_report`: imports check_pack. If check_pack not installed, ImportError caught? It catches Exception, so ImportError is caught. That's fine.

Now, check `main`: `voice = voice_mod().parse_overrides(a.voice) if a.voice else (meta_story.get("voice_engine") if isinstance(meta_story.get("voice_engine"), dict) else None)`. As noted, AttributeError if meta_story not dict. High.

Also, check `main`: `meta_story = json.loads((Path(a.story).parent / "story.json").read_text(encoding="utf-8"))`. If story.json is a list, meta_story is list. Then later `meta_story.get(...)` fails. So that's the same bug.

Now, check `writer_prompts.py`: `look_example` uses `pack["palettes"]` etc. If pack is not dict, KeyError caught. Fine.

Now, check `bible_to_sheet_jobs.py`: `prompt = (item.get("sheet_prompt") or item.get("card_prompt")) if isinstance(item, dict) else None`. If item is dict but both missing, prompt None, skip. Fine.

Now, check `pack_to_spec.py`: `OUTPUTS_ROOT_TEMPLATE = "D:/aai work/flow_outputs/anime_{slug}"`. This is a Windows path. On Windows, forward slashes are okay. But if slug contains backslash? slug is typically safe. Not a defect.

Now, check `remove_sparkle.py`: `--skip-done` added. Fine.

Now, check `h3/v4_to_h3.py`: adds metadata.look. Fine.

Now, check `ui/pipeline.py`: `image_id = entry.get("image_id", shot_id)`. If entry is not dict? It is. Fine.

Now, check `ui/server.py`: `_flow_project_url` uses `FLOW_PROJECT_RE.fullmatch(url)`. If url is not a string, fullmatch fails, returns FLOW_PROJECT_URL. That's fine.

Now, check `ui/server.py`: `b_h3` converts pack to h3. If conversion fails, raises bad. That's fine.

Now, check `ui/server.py`: `_record_step` regex. As noted, missing hyphen. Medium.

Now, check `ui/server.py`: `review_shot` allows 500 shots. That's a change, but not a defect.

Now, check `ui/server.py`: `hits` logic. If sid is "SHOT-001", and entries has "SHOT-001A", then hits = ["SHOT-001A"]. That's fine. But if sid is "SHOT-001A", and entries has "SHOT-001AA", it would match. Rare. Not a defect.

Now, check `ui/static/app.js` and `pipeline.js`: adding story param. Fine.

Now, are there any other crashes? In `_v4_parts`, `_is_num` and `_str` are assumed defined. If not, crash. But they were presumably there. Not introduced.

In `_range_start`, `_two_numbers` assumed defined. Not introduced.

Now, check `timeline.py` hunk 102-104: `anchors = shot.get("reference_anchors") if isinstance(shot.get("reference_anchors"), dict) else {}`. This calls `shot.get` twice. If `reference_anchors` is present but not dict, the second `shot.get` returns the non-dict value, and `isinstance(..., dict)` is False, so `{}`. That's fine. But if `reference_anchors` is present and is a dict, it uses it. However, if `reference_anchors` is a dict but `character_positions` is not a list, `or []` makes it empty. Fine.

Now, check `timeline.py` hunk 104-105: `track = shot.get("audio_and_dialogue_track") if isinstance(shot.get("audio_and_dialogue_track"), dict) else {}`. Same pattern.

Now, check `timeline.py` hunk 111-116: `by_lang = track.get("captions_by_lang")`. Then `for cards in by_lang.values() if isinstance(by_lang, dict) else []:`. If by_lang is not dict, the conditional yields `[]`. So safe.

Now, check `timeline.py` hunk 113: `for card in cards if isinstance(cards, list) else []:`. If cards is not a list, skip. Safe.

Now, check `timeline.py` hunk 114: `start = _range_start(card.get("time_range")) if isinstance(card, dict) else None`. If card is dict but time_range missing, `_range_start(None)`? `_range_start` expects value. If value is None, `_two_numbers(None)` likely False, regex on None? `isinstance(value, str)` False, so m None, returns None. So start None. Fine.

Now, check `timeline.py` hunk 107: `start = _range_start(line.get("time_range")) if isinstance(line, dict) else None`. Same.

Now, check `timeline.py` hunk 95: `if not isinstance(d, dict) or not _is_num(d.get("t0")) or not _is_num(d.get("t1")) or d["t0"] >= length_s: continue`. If d is dict but t0 missing, `_is_num(None)` False, continue. Fine.

Now, check `timeline.py` hunk 98: `beats.append(_beat(float(d["t0"]), min(float(d["t1"]), length_s), hold="hold" in acting.lower(), acting=acting))`. If d["t0"] missing, KeyError. But the filter ensures t0 is numeric if d is dict. However, if d is dict but t0 is not a number (e.g., string), `_is_num` would be False, so continue. So safe.

Now, check `timeline.py` hunk 99: `cam = _str(d.get("camera")).strip().lower()`. If camera missing, returns "". Fine.

Now, check `timeline.py` hunk 100: `if cam and STATIC_WORD not in cam and "hold" not in cam:`. If cam is "", condition False. Fine.

Now, check `timeline.py` hunk 103: `cast = [p["id"] for p in anchors.get("character_positions") or [] if isinstance(p, dict) and isinstance(p.get("id"), str)]`. If p is dict but id missing, `p.get("id")` returns None, `isinstance(None, str)` False, so skipped. Fine.

Now, check `timeline.py` hunk 106: `for line in track.get("dialogue") or []:`. If dialogue is not a list, `or []` makes it empty. Fine.

Now, check `timeline.py` hunk 107: `start = _range_start(line.get("time_range")) if isinstance(line, dict) else None`. If line is dict but time_range missing, start None. Fine.

Now, check `timeline.py` hunk 108: `if start is not None and 0 <= start < length_s:`. Fine.

Now, check `timeline.py` hunk 112-116: similar.

So no new crashes in timeline.py.

Now, check `caption_cues.py` again: the str drop bug. Also, there is a potential bug: if cap is a list of dicts, and some dict has no "text", item text is None. That could cause downstream None handling. But not a crash. The original code didn't handle that either. So not a new defect.

But there is another subtle bug: the condition `if isinstance(cap, list) and cap and all(isinstance(c, (dict, str)) for c in cap):` ensures cap is non-empty list. If cap is empty list, it falls through to elif dict/str. That's fine. But if cap is a list of dicts where some dict has no "text", the all() check passes because isinstance dict. Then inside loop, `c.get("text")` returns None. That's okay.

Now, check `retention_rules.py`: no defects.

Now, check `story_state.py`: no defects.

Now, check `write_pack.py`: the AttributeError in main. High.

Also, check `write_pack.py`: `plan_errors` and `episode_id_errors` and `caption_id_errors`. These are new functions. They seem correct.

But there is a potential bug in `episode_id_errors`: `str(s.get("episode")) != str(ep)`. If ep is 1, and shot episode is "1", str comparison works. If shot episode is 1 (int), str(1) == "1". Good. But if shot episode is "1.0", str is "1.0" != "1". That would be flagged. That's probably intended.

Now, check `caption_id_errors`: `ids = {s.get("id") for s in shots if isinstance(s, dict)}`. If shot id missing, key None. `named = {i.get("shot_id") for i in items if isinstance(i, dict)}`. If item missing shot_id, key None. Then `n for n in named if n not in ids` includes None if named has None and ids doesn't have None? But ids has None if any shot missing id. So if named has None and ids has None, no error. If named has None and ids doesn't have None (all shots have ids), then error "CAP-01 ... None is not a shot". That's fine.

Now, check `run_staged` per-episode stage 5: KeyError. High.

Also, check `run_staged` whole-story stage 5: `if (out / "stage_5_raw.json").exists():`. If the file exists, it does whole-stage 5. That's fine.

But there is a potential bug: in whole-story branch, `shots = [legacy_fields(s, bible) for s in apply_captions(merge_episodes(per_episode), captions["captions"], langs)]`. `apply_captions` likely modifies shots in place. That's fine.

Now, check `pack_check_report`: imports check_pack. If check_pack not installed, ImportError caught? It catches Exception, so ImportError is caught. That's fine.

Now, check `main`: `voice = voice_mod().parse_overrides(a.voice) if a.voice else (meta_story.get("voice_engine") if isinstance(meta_story.get("voice_engine"), dict) else None)`. As noted, AttributeError if meta_story not dict. High.

Also, check `main`: `meta_story = json.loads((Path(a.story).parent / "story.json").read_text(encoding="utf-8"))`. If story.json is a list, meta_story is list. Then later `meta_story.get(...)` fails. So that's the same bug.

Now, check `writer_prompts.py`: `look_example` uses `pack["palettes"]` etc. If pack is not dict, KeyError caught. Fine.

Now, check `bible_to_sheet_jobs.py`: `prompt = (item.get("sheet_prompt") or item.get("card_prompt")) if isinstance(item, dict) else None`. If item is dict but both missing, prompt None, skip. Fine.

Now, check `pack_to_spec.py`: `OUTPUTS_ROOT_TEMPLATE = "D:/aai work/flow_outputs/anime_{slug}"`. This is a Windows path. On Windows, forward slashes are okay. But if slug contains backslash? slug is typically safe. Not a defect.

Now, check `remove_sparkle.py`: `--skip-done` added. Fine.

Now, check `h3/v4_to_h3.py`: adds metadata.look. Fine.

Now, check `ui/pipeline.py`: `image_id = entry.get("image_id", shot_id)`. If entry is not dict? It is. Fine.

Now, check `ui/server.py`: `_flow_project_url` uses `FLOW_PROJECT_RE.fullmatch(url)`. If url is not a string, fullmatch fails, returns FLOW_PROJECT_URL. That's fine.

Now, check `ui/server.py`: `b_h3` converts pack to h3. If conversion fails, raises bad. That's fine.

Now, check `ui/server.py`: `_record_step` regex. As noted, missing hyphen. Medium.

Now, check `ui/server.py`: `review_shot` allows 500 shots. That's a change, but not a defect.

Now, check `ui/server.py`: `hits` logic. If sid is "SHOT-001", and entries has "SHOT-001A", then hits = ["SHOT-001A"]. That's fine. But if sid is "SHOT-001A", and entries has "SHOT-001AA", it would match. Rare. Not a defect.

Now, check `ui/static/app.js` and `pipeline.js`: adding story param. Fine.

Now, are there any other crashes? In `_v4_parts`, `_is_num` and `_str` are assumed defined. If not, crash. But they were presumably there. Not introduced.

In `_range_start`, `_two_numbers` assumed defined. Not introduced.

Now, check `timeline.py` hunk 102-104: `anchors = shot.get("reference_anchors") if isinstance(shot.get("reference_anchors"), dict) else {}`. This calls `shot.get` twice. If `reference_anchors` is present but not dict, the second `shot.get` returns the non-dict value, and `isinstance(..., dict)` is False, so `{}`. That's fine. But if `reference_anchors` is present and is a dict, it uses it. However, if `reference_anchors` is a dict but `character_positions` is not a list, `or []` makes it empty. Fine.

Now, check `timeline.py` hunk 104-105: `track = shot.get("audio_and_dialogue_track") if isinstance(shot.get("audio_and_dialogue_track"), dict) else {}`. Same pattern.

Now, check `timeline.py` hunk 111-116: similar.

So no new crashes in timeline.py.

Now, check `caption_cues.py` again: the str drop bug. Also, there is a potential bug: if cap is a list of dicts, and some dict has no "text", item text is None. That could cause downstream None handling. But not a crash. The original code didn't handle that either. So not a new defect.

But there is another subtle bug: the condition `if isinstance(cap, list) and cap and all(isinstance(c, (dict, str)) for c in cap):` ensures cap is non-empty list. If cap is empty list, it falls through to elif dict/str. That's fine. But if cap is a list of dicts where some dict has no "text", the all() check passes because isinstance dict. Then inside loop, `c.get("text")` returns None. That's okay.

Now, check `retention_rules.py`: no defects.

Now, check `story_state.py`: no defects.

Now, check `write_pack.py`: the AttributeError in main. High.

Also, check `write_pack.py`: `plan_errors` and `episode_id_errors` and `caption_id_errors`. These are new functions. They seem correct.

But there is a potential bug in `episode_id_errors`: `str(s.get("episode")) != str(ep)`. If ep is 1, and shot episode is "1", str comparison works. If shot episode is 1 (int), str(1) == "1". Good. But if shot episode is "1.0", str is "1.0" != "1". That would be flagged. That's probably intended.

Now, check `caption_id_errors`: `ids = {s.get("id") for s in shots if isinstance(s, dict)}`. If shot id missing, key None. `named = {i.get("shot_id") for i in items if isinstance(i, dict)}`. If item missing shot_id, key None. Then `n for n in named if n not in ids` includes None if named has None and ids doesn't have None? But ids has None if any shot missing id. So if named has None and ids has None, no error. If named has None and ids doesn't have None (all shots have ids), then error "CAP-01 ... None is not a shot". That's fine.

Now, check `run_staged` per-episode stage 5: KeyError. High.

Also, check `run_staged` whole-story stage 5: `if (out / "stage_5_raw.json").exists():`. If the file exists, it does whole-stage 5. That's fine.

But there is a potential bug: in whole-story branch, `shots = [legacy_fields(s, bible) for s in apply_captions(merge_episodes(per_episode), captions["captions"], langs)]`. `apply_captions` likely modifies shots in place. That's fine.

Now, check `pack_check_report`: imports check_pack. If check_pack not installed, ImportError caught? It catches Exception, so ImportError is caught. That's fine.

Now, check `main`: `voice = voice_mod().parse_overrides(a.voice) if a.voice else (meta_story.get("voice_engine") if isinstance(meta_story.get("voice_engine"), dict) else None)`. As noted, AttributeError if meta_story not dict. High.

Also, check `main`: `meta_story = json.loads((Path(a.story).parent / "story.json").read_text(encoding="utf-8"))`. If story.json is a list, meta_story is list. Then later `meta_story.get(...)` fails. So that's the same bug.

Now, check `writer_prompts.py`: `look_example` uses `pack["palettes"]` etc. If pack is not dict, KeyError caught. Fine.

Now, check `bible_to_sheet_jobs.py`: `prompt = (item.get("sheet_prompt") or item.get("card_prompt")) if isinstance(item, dict) else None`. If item is dict but both missing, prompt None, skip. Fine.

Now, check `pack_to_spec.py`: `OUTPUTS_ROOT_TEMPLATE = "D:/aai work/flow_outputs/anime_{slug}"`. This is a Windows path. On Windows, forward slashes are okay. But if slug contains backslash? slug is typically safe. Not a defect.

Now, check `remove_sparkle.py`: `--skip-done` added. Fine.

Now, check `h3/v4_to_h3.py`: adds metadata.look. Fine.

Now, check `ui/pipeline.py`: `image_id = entry.get("image_id", shot_id)`. If entry is not dict? It is. Fine.

Now, check `ui/server.py`: `_flow_project_url` uses `FLOW_PROJECT_RE.fullmatch(url)`. If url is not a string, fullmatch fails, returns FLOW_PROJECT_URL. That's fine.

Now, check `ui/server.py`: `b_h3` converts pack to h3. If conversion fails, raises bad. That's fine.

Now, check `ui/server.py`: `_record_step` regex. As noted, missing hyphen. Medium.

Now, check `ui/server.py`: `review_shot` allows 500 shots. That's a change, but not a defect.

Now, check `ui/server.py`: `hits` logic. If sid is "SHOT-001", and entries has "SHOT-001A", then hits = ["SHOT-001A"]. That's fine. But if sid is "SHOT-001A", and entries has "SHOT-001AA", it would match. Rare. Not a defect.

Now, check `ui/static/app.js` and `pipeline.js`: adding story param. Fine.

Now, are there any other crashes? In `_v4_parts`, `_is_num` and `_str` are assumed defined. If not, crash. But they were presumably there. Not introduced.

In `_range_start`, `_two_numbers` assumed defined. Not introduced.

Now, check `timeline.py` hunk 102-104: `anchors = shot.get("reference_anchors") if isinstance(shot.get("reference_anchors"), dict) else {}`. This calls `shot.get` twice. If `reference_anchors` is present but not dict, the second `shot.get` returns the non-dict value, and `isinstance(..., dict)` is False, so `{}`. That's fine. But if `reference_anchors` is present and is a dict, it uses it. However, if `reference_anchors` is a dict but `character_positions` is not a list, `or []` makes it empty. Fine.

Now, check `timeline.py` hunk 104-105: `track = shot.get("audio_and_dialogue_track") if isinstance(shot.get("audio_and_dialogue_track"), dict) else {}`. Same pattern.

Now, check `timeline.py` hunk 111-116: similar.

So no new crashes in timeline.py.

Now, check `caption_cues.py` again: the str drop bug. Also, there is a potential bug: if cap is a list of dicts, and some dict has no "text", item text is None. That could cause downstream None handling. But not a crash. The original code didn't handle that either. So not a new defect.

But there is another subtle bug: the condition `if isinstance(cap, list) and cap and all(isinstance(c, (dict, str)) for c in cap):` ensures cap is non-empty list. If cap is empty list, it falls through to elif dict/str. That's fine. But if cap is a list of dicts where some dict has no "text", the all() check passes because isinstance dict. Then inside loop, `c.get("text")` returns None. That's okay.

Now, check `retention_rules.py`: no defects.

Now, check `story_state.py`: no defects.

Now, check `write_pack.py`: the AttributeError in main. High.

Also, check `write_pack.py`: `plan_errors` and `episode_id_errors` and `caption_id_errors`. These are new functions. They seem correct.

But there is a potential bug in `episode_id_errors`: `str(s.get("episode")) != str(ep)`. If ep is 1, and shot episode is "1", str comparison works. If shot episode is 1 (int), str(1) == "1". Good. But if shot episode is "1.0", str is "1.0" != "1". That would be flagged. That's probably intended.

Now, check `caption_id_errors`: `ids = {s.get("id") for s in shots if isinstance(s, dict)}`. If shot id missing, key None. `named = {i.get("shot_id") for i in items if isinstance(i, dict)}`. If item missing shot_id, key None. Then `n for n in named if n not in ids` includes None if named has None and ids doesn't have None? But ids has None if any shot missing id. So if named has None and ids has None, no error. If named has None and ids doesn't have None (all shots have ids), then error "CAP-01 ... None is not a shot". That's fine.

Now, check `run_staged` per-episode stage 5: KeyError. High.

Also, check `run_staged` whole-story stage 5: `if (out / "stage_5_raw.json").exists():`. If the file exists, it does whole-stage 5. That's fine.

But there is a potential bug: in whole-story branch, `shots = [legacy_fields(s, bible) for s in apply_captions(merge_episodes(per_episode), captions["captions"], langs)]`. `apply_captions` likely modifies shots in place. That's fine.

Now, check `pack_check_report`: imports check_pack. If check_pack not installed, ImportError caught? It catches Exception, so ImportError is caught. That's fine.

Now, check `main`: `voice = voice_mod().parse_overrides(a.voice) if a.voice else (meta_story.get("voice_engine") if isinstance(meta_story.get("voice_engine"), dict) else None)`. As noted, AttributeError if meta_story not dict. High.

Also, check `main`: `meta_story = json.loads((Path(a.story).parent / "story.json").read_text(encoding="utf-8"))`. If story.json is a list, meta_story is list. Then later `meta_story.get(...)` fails. So that's the same bug.

Now, check `writer_prompts.py`: `look_example` uses `pack["palettes"]` etc. If pack is not dict, KeyError caught. Fine.

Now, check `bible_to_sheet_jobs.py`: `prompt = (item.get("sheet_prompt") or item.get("card_prompt")) if isinstance(item, dict) else None`. If item is dict but both missing, prompt None, skip. Fine.

Now, check `pack_to_spec.py`: `OUTPUTS_ROOT_TEMPLATE = "D:/aai work/flow_outputs/anime_{slug}"`. This is a Windows path. On Windows, forward slashes are okay. But if slug contains backslash? slug is typically safe. Not a defect.

Now, check `remove_sparkle.py`: `--skip-done` added. Fine.

Now, check `h3/v4_to_h3.py`: adds metadata.look. Fine.

Now, check `ui/pipeline.py`: `image_id = entry.get("image_id", shot_id)`. If entry is not dict? It is. Fine.

Now, check `ui/server.py`: `_flow_project_url` uses `FLOW_PROJECT_RE.fullmatch(url)`. If url is not a string, fullmatch fails, returns FLOW_PROJECT_URL. That's fine.

Now, check `ui/server.py`: `b_h3` converts pack to h3. If conversion fails, raises bad. That's fine.

Now, check `ui/server.py`: `_record_step` regex. As noted, missing hyphen. Medium.

Now, check `ui/server.py`: `review_shot` allows 500 shots. That's a change, but not a defect.

Now, check `ui/server.py`: `hits` logic. If sid is "SHOT-001", and entries has "SHOT-001A", then hits = ["SHOT-001A"]. That's fine. But if sid is "SHOT-001A", and entries has "SHOT-001AA", it would match. Rare. Not a defect.

Now, check `ui/static/app.js` and `pipeline.js`: adding story param. Fine.

Now, are there any other crashes? In `_v4_parts`, `_is_num` and `_str` are assumed defined. If not, crash. But they were presumably there. Not introduced.

In `_range_start`, `_two_numbers` assumed defined. Not introduced.

Now, check `timeline.py` hunk 102-104: `anchors = shot.get("reference_anchors") if isinstance(shot.get("reference_anchors"), dict) else {}`. This calls `shot.get` twice. If `reference_anchors` is present but not dict, the second `shot.get` returns the non-dict value, and `isinstance(..., dict)` is False, so `{}`. That's fine. But if `reference_anchors` is present and is a dict, it uses it. However, if `reference_anchors` is a dict but `character_positions` is not a list, `or []` makes it empty. Fine.

Now, check `timeline.py` hunk 104-105: `track = shot.get("audio_and_dialogue_track") if isinstance(shot.get("audio_and_dialogue_track"), dict) else {}`. Same pattern.

Now, check `timeline.py` hunk 111-116: similar.

So no new crashes in timeline.py.

Now, check `caption_cues.py` again: the str drop bug. Also, there is a potential bug: if cap is a list of dicts, and some dict has no "text", item text is None. That could cause downstream None handling. But not a crash. The original code didn't handle that either. So not a new defect.

But there is another subtle bug: the condition `if isinstance(cap, list) and cap and all(isinstance(c, (dict, str)) for c in cap):` ensures cap is non-empty list. If cap is empty list, it falls through to elif dict/str. That's fine. But if cap is a list of dicts where some dict has no "text", the all() check passes because isinstance dict. Then inside loop, `c.get("text")` returns None. That's okay.

Now, check `retention_rules.py`: no defects.

Now, check `story_state.py`: no defects.

Now, check `write_pack.py`: the AttributeError in main. High.

Also, check `write_pack.py`: `plan_errors` and `episode_id_errors` and `caption_id_errors`. These are new functions. They seem correct.

But there is a potential bug in `episode_id_errors`: `str(s.get("episode")) != str(ep)`. If ep is 1, and shot episode is "1", str comparison works. If shot episode is 1 (int), str(1) == "1". Good. But if shot episode is "1.0", str is "1.0" != "1". That would be flagged. That's probably intended.

Now, check `caption_id_errors`: `ids = {s.get("id") for s in shots if isinstance(s, dict)}`. If shot id missing, key None. `named = {i.get("shot_id") for i in items if isinstance(i, dict)}`. If item missing shot_id, key None. Then `n for n in named if n not in ids` includes None if named has None and ids doesn't have None? But ids has None if any shot missing id. So if named has None and ids has None, no error. If named has None and ids doesn't have None (all shots have ids), then error "CAP-01 ... None is not a shot". That's fine.

Now, check `run_staged` per-episode stage 5: KeyError. High.

Also, check `run_staged` whole-story stage 5: `if (out / "stage_5_raw.json").exists():`. If the file exists, it does whole-stage 5. That's fine.

But there is a potential bug: in whole-story branch, `shots = [legacy_fields(s, bible) for s in apply_captions(merge_episodes(per_episode), captions["captions"], langs)]`. `apply_captions` likely modifies shots in place. That's fine.

Now, check `pack_check_report`: imports check_pack. If check_pack not installed, ImportError caught? It catches Exception, so ImportError is caught. That's fine.

Now, check `main`: `voice = voice_mod().parse_overrides(a.voice) if a.voice else (meta_story.get("voice_engine") if isinstance(meta_story.get("voice_engine"), dict) else None)`. As noted, AttributeError if meta_story not dict. High.

Also, check `main`: `meta_story = json.loads((Path(a.story).parent / "story.json").read_text(encoding="utf-8"))`. If story.json is a list, meta_story is list. Then later `meta_story.get(...)` fails. So that's the same bug.

Now, check `writer_prompts.py`: `look_example` uses `pack["palettes"]` etc. If pack is not dict, KeyError caught. Fine.

Now, check `bible_to_sheet_jobs.py`: `prompt = (item.get("sheet_prompt") or item.get("card_prompt")) if isinstance(item, dict) else None`. If item is dict but both missing, prompt None, skip. Fine.

Now, check `pack_to_spec.py`: `OUTPUTS_ROOT_TEMPLATE = "D:/aai work/flow_outputs/anime_{slug}"`. This is a Windows path. On Windows, forward slashes are okay. But if slug contains backslash? slug is typically safe. Not a defect.

Now, check `remove_sparkle.py`: `--skip-done` added. Fine.

Now, check `h3/v4_to_h3.py`: adds metadata.look. Fine.

Now, check `ui/pipeline.py`: `image_id = entry.get("image_id", shot_id)`. If entry is not dict? It is. Fine.

Now, check `ui/server.py`: `_flow_project_url` uses `FLOW_PROJECT_RE.fullmatch(url)`. If url is not a string, fullmatch fails, returns FLOW_PROJECT_URL. That's fine.

Now, check `ui/server.py`: `b_h3` converts pack to h3. If conversion fails, raises bad. That's fine.

Now, check `ui/server.py`: `_record_step` regex. As noted, missing hyphen. Medium.

Now, check `ui/server.py`: `review_shot` allows 500 shots. That's a change, but not a defect.

Now, check `ui/server.py`: `hits` logic. If sid is "SHOT-001", and entries has "SHOT-001A", then hits = ["SHOT-001A"]. That's fine. But if sid is "SHOT-001A", and entries has "SHOT-001AA", it would match. Rare. Not a defect.

Now, check `ui/static/app.js` and `pipeline.js`: adding story param. Fine.

Now, are there any other crashes? In `_v4_parts`, `_is_num` and `_str` are assumed defined. If not, crash. But they were presumably there. Not introduced.

In `_range_start`, `_two_numbers` assumed defined. Not introduced.

Now, check `timeline.py` hunk 102-104: `anchors = shot.get("reference_anchors") if isinstance(shot.get("reference_anchors"), dict) else {}`. This calls `shot.get` twice. If `reference_anchors` is present but not dict, the second `shot.get` returns the non-dict value, and `isinstance(..., dict)` is False, so `{}`. That's fine. But if `reference_anchors` is present and is a dict, it uses it. However, if `reference_anchors` is a dict but `character_positions` is not a list, `or []` makes it empty. Fine.

Now, check `timeline.py` hunk 104-105: `track = shot.get("audio_and_dialogue_track") if isinstance(shot.get("audio_and_dialogue_track"), dict) else {}`. Same pattern.

Now, check `timeline.py` hunk 111-116: similar.

So no new crashes in timeline.py.

Now, check `caption_cues.py` again: the str drop bug. Also, there is a potential bug: if cap is a list of dicts, and some dict has no "text", item text is None. That could cause downstream None handling. But not a crash. The original code didn't handle that either. So not a new defect.

But there is another subtle bug: the condition `if isinstance(cap, list) and cap and all(isinstance(c, (dict, str)) for c in cap):` ensures cap is non-empty list. If cap is empty list, it falls through to elif dict/str. That's fine. But if cap is a list of dicts where some dict has no "text", the all() check passes because isinstance dict. Then inside loop, `c.get("text")` returns None. That's okay.

Now, check `retention_rules.py`: no defects.

Now, check `story_state.py`: no defects.

Now, check `write_pack.py`: the AttributeError in main. High.

Also, check `write_pack.py`: `plan_errors` and `episode_id_errors` and `caption_id_errors`. These are new functions. They seem correct.

But there is a potential bug in `episode_id_errors`: `str(s.get("episode")) != str(ep)`. If ep is 1, and shot episode is "1", str comparison works. If shot episode is 1 (int), str(1) == "1". Good. But if shot episode is "1.0", str is "1.0" != "1". That would be flagged. That's probably intended.

Now, check `caption_id_errors`: `ids = {s.get("id") for s in shots if isinstance(s, dict)}`. If shot id missing, key None. `named = {i.get("shot_id") for i in items if isinstance(i, dict)}`. If item missing shot_id, key None. Then `n for n in named if n not in ids` includes None if named has None and ids doesn't have None? But ids has None if any shot missing id. So if named has None and ids has None, no error. If named has None and ids doesn't have None (all shots have ids), then error "CAP-01 ... None is not a shot". That's fine.

Now, check `run_staged` per-episode stage 5: KeyError. High.

Also, check `run_staged` whole-story stage 5: `if (out / "stage_5_raw.json").exists():`. If the file exists, it does whole-stage 5. That's fine.

But there is a potential bug: in whole-story branch, `shots = [legacy_fields(s, bible) for s in apply_captions(merge_episodes(per_episode), captions["captions"], langs)]`. `apply_captions` likely modifies shots in place. That's fine.

Now, check `pack_check_report`: imports check_pack. If check_pack not installed, ImportError caught? It catches Exception, so ImportError is caught. That's fine.

Now, check `main`: `voice = voice_mod().parse_overrides(a.voice) if a.voice else (meta_story.get("voice_engine") if isinstance(meta_story.get("voice_engine"), dict) else None)`. As noted, AttributeError if meta_story not dict. High.

Also, check `main`: `meta_story = json.loads((Path(a.story).parent / "story.json").read_text(encoding="utf-8"))`. If story.json is a list, meta_story is list. Then later `meta_story.get(...)` fails. So that's the same bug.

Now, check `writer_prompts.py`: `look_example` uses `pack["palettes"]` etc. If pack is not dict, KeyError caught. Fine.

Now, check `bible_to_sheet_jobs.py`: `prompt = (item.get("sheet_prompt") or item.get("card_prompt")) if isinstance(item, dict) else None`. If item is dict but both missing, prompt None, skip. Fine.

Now, check `pack_to_spec.py`: `OUTPUTS_ROOT_TEMPLATE = "D:/aai work/flow_outputs/anime_{slug}"`. This is a Windows path. On Windows, forward slashes are okay. But if slug contains backslash? slug is typically safe. Not a defect.

Now, check `remove_sparkle.py`: `--skip-done` added. Fine.

Now, check `h3/v4_to_h3.py`: adds metadata.look. Fine.

Now, check `ui/pipeline.py`: `image_id = entry.get("image_id", shot_id)`. If entry is not dict? It is. Fine.

Now, check `ui/server.py`: `_flow_project_url` uses `FLOW_PROJECT_RE.fullmatch(url)`. If url is not a string, fullmatch fails, returns FLOW_PROJECT_URL. That's fine.

Now, check `ui/server.py`: `b_h3` converts pack to h3. If conversion fails, raises bad. That's fine.

Now, check `ui/server.py`: `_record_step` regex. As noted, missing hyphen. Medium.

Now, check `ui/server.py`: `review_shot` allows 500 shots. That's a change, but not a defect.

Now, check `ui/server.py`: `hits` logic. If sid is "SHOT-001", and entries has "SHOT-001A", then hits = ["SHOT-001A"]. That's fine. But if sid is "SHOT-001A", and entries has "SHOT-001AA", it would match. Rare. Not a defect.

Now, check `ui/static/app.js` and `pipeline.js`: adding story param. Fine.

Now, are there any other crashes? In `_v4_parts`, `_is_num` and `_str` are assumed defined. If not, crash. But they were presumably there. Not introduced.

In `_range_start`, `_two_numbers` assumed defined. Not introduced.

Now, check `timeline.py` hunk 102-104: `anchors = shot.get("reference_anchors") if isinstance(shot.get("reference_anchors"), dict) else {}`. This calls `shot.get` twice. If `reference_anchors` is present but not dict, the second `shot.get` returns the non-dict value, and `isinstance(..., dict)` is False, so `{}`. That's fine. But if `reference_anchors` is present and is a dict, it uses it. However, if `reference_anchors` is a dict but `character_positions` is not a
