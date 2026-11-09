# ABR review: score/ableton_build.py + score/tests/test_ableton_build.py (2026-11-09)

Reviewer: ABR (independent, read-only). No commit, no network, no model calls, no Ableton or serum-mcp calls.
Checked against: research/SCORE_BUILD_CHECKLIST_STRICT_2026-11-09.md section D, .claude/skills/score-reel/SKILL.md steps 6-7,
owner server.py at `D:\ableton claude final best\serum2\ableton\ableton_mcp_extended\server.py`.

Caveat on the Remote Script: the owner tree has no live Remote Script. The only one found is a backup at
`D:\ableton claude final best\youtube_to_serum\ableton-mcp-extended\ableton-mcp-extended.bak-1790504451\AbletonMCP_Remote_Script\__init__.py`
(called "Remote" below). It may differ from the live Ableton install. Remote findings are "per backup copy".

## Test run

`python -m pytest score/tests/test_ableton_build.py -q` gave: **16 passed in 0.08s** (0 skipped, owner server.py found).
Malformed-input snippets (inline python, no files saved): build_recipe, serum_briefs, check_inputs and main never raised.
Results of the snippets are cited in the findings.

## Counts

- HIGH: 2
- MED: 5
- LOW: 4
- Total: 11

## Answers to the six questions

1. **Envelope points (manual?)** Confirmed: no existing points writer. server.py `manage_clip_automation` (1715-1749) takes only
   track_index, clip_index, clip_name, action, parameter_name. Remote backup `_manage_clip_automation` (1462-1505) only calls
   `create_automation_envelope` and `clear_envelope` / `clear_all_envelopes`. `set_device_parameter` (server.py 1843-1909) sets one static
   value, which is not automation. A grep of the whole owner tree (excluding .venv*) found no insert-step or breakpoint writer. The
   manual step is correct as a fallback, but it means the SKILL step 7 requirement (envelopes for macros 1-4 and volume) is not met.
   See ABR-02.
2. **Add-notes-to-arrangement** Confirmed at the MCP surface: server.py has no `@mcp.tool` for it and `create_arrangement_midi_clip`
   takes no notes. The name `add_notes_to_arrangement_clip` appears only in the send_command modifying list (server.py:123). The Remote
   backup does handle it (`_add_notes_to_arrangement_clip`, Remote:1376-1394), so a tool wrapper could be added by the owner. The
   session-clip plus `duplicate_clip_to_arrangement` route is valid. See ABR-08.
3. **create_midi_track without index, and '@role:' refs** The server drops the index: server.py:416-430 returns only a string,
   although the Remote returns `{"index", "name"}` (Remote:637-655). The recipe never reads an index back. The '@role:' values are
   strings where server.py types are int, so they are not valid MCP arguments until a replayer resolves them, and no replayer exists in
   the repo. The scheme is safe only if each index is read right after creation (MARKERS is created last, so track_count works). See ABR-04.
4. **Cue points with bar=0** Works. server.py `_convert_bar_to_beat` (1249-1254) returns beat as-is when bar <= 0. `create_cue_point`
   (1418-1433) passes time and name. Remote:1264-1280 moves the playhead, toggles the cue and sets the name. A duplicate time raises
   in Remote. The readback `get_cue_points` (server.py 1304-1322) returns name and time. See ABR-09 for duplicate markers.
5. **Clip length and start units** Correct. `set_tempo` (server.py 701-715) sets BPM, `create_clip` (624-646) takes length in beats,
   and `create_arrangement_midi_clip` (1454-1506) takes start_beat and length_beats. Live beats are quarter notes, so at 60 BPM 1 beat
   equals 1 s. No finding.
6. **'Macro n' as a real alias** Partly. `plugin_aliases.py:44-51` maps "macro 1" to "Macro 1", but it applies only inside
   `set_device_parameter` (server.py 1873-1885) and only when the device name contains "Serum" (`_find_profile` substring match).
   `manage_clip_automation` sends the raw name and gets no alias (server.py 1737-1742). The live Serum parameter name is unverified.
   See ABR-07.

## Findings

### ABR-01 HIGH: MARKERS clip names are dropped, so the "named clip per shot" requirement fails silently
- Ours: score/ableton_build.py:172-174 (`create_arrangement_midi_clip` args include `name`). Test: test_ableton_build.py:144-149
  asserts the name in the args, which encodes the bug.
- server.py:1454-1506. The `name` parameter is never sent. Line 1489-1493 sends only `track_index`, `position`, `length`.
- Remote:1311-1330 `_create_arrangement_clip(track_index, position, length)` takes no name either.
- Evidence: the probe `build_recipe` with marker name "1A hook" gives args `{..., "name": "1A hook"}`, and the server then ignores it.
- Fix: after each marker create, emit `set_arrangement_clip_property` with `track_index: "@role:markers"`, `clip_index: k` (1-based, in
  start-time order; MARKERS is a new track so the order is known), and `name: <marker name>`. server.py:1607-1673 accepts these
  arguments and Remote:1406-1419 sets `name`. Change the test to assert the rename step.

### ABR-02 HIGH: envelope coverage does not match D2 or SKILL step 7; points are manual, with no writer in the owner stack
- Ours: score/ableton_build.py:181-202. Envelopes are emitted only for automation entries in the notes. Nothing creates envelopes for
  Macros 1-4 and volume by default, even though D2 says "manage_clip_automation for macros 1-4 and volume" and SKILL step 7 says "clip
  automation envelopes for the 4 macros and volume". Test test_ableton_build.py:159-163 hard-codes the fixture (["Macro 1", "volume"]).
- The points are a manual step (ab:201-202). This is correct given the tree (see Q1), but the requirement is not met by the replay alone.
- server.py:1716-1749 has no points argument. Remote:1462-1505 has no points writer.
- Fix: (a) the recipe emits a create for Macro 1-4 and volume for every Serum role that has an arrangement clip; (b) to remove the
  manual step the owner adds a Remote command that writes envelope steps (the Live Python API has a clip envelope insert-step call;
  verify on the owner's Live 12 build) plus a server.py tool. Until then keep it manual and say so at gate M2.

### ABR-03 MED: automation is emitted for a role that has no arrangement clip
- Ours: score/ableton_build.py:157-158 skips the clip creation when a role has no good notes (`continue`), but automation at 181-200
  does not check whether that role got a clip.
- Remote:517-546 `_resolve_arrangement_clip` raises IndexError when the arrangement list is empty, so the create call fails.
- Evidence: probe with automation for "drone" and no drone notes gives `manage_clip_automation` with `track_index "@role:drone"`,
  `clip_index 1`, and no `create_clip` for drone.
- Fix: track the roles that got a clip and skip automation (with a manual SKIPPED line) for any other role.

### ABR-04 MED: '@role:' references are not valid MCP arguments, have no readback, and the index is dropped by the server
- Ours: ab:65 (`_ref`), ab:140-141 (create_midi_track then `@role:markers`), and the `track_index` values throughout.
- server.py:416-430 drops the `index` that Remote returns (Remote:637-655). server.py types `track_index: int`, so the string form is
  rejected at call time.
- No replayer exists in the repo (module docstring says "a later step replays the recipe"). The rule "read with get_session_info
  track_count right after the create step" (ab docstring line 14) is not a recipe step.
- Fix: add an explicit get_session_info readback after each create (or use the `track_index` in create_serum_track's JSON,
  server.py:500), and have the replayer write the role-to-index map. Add a test that every `track_index` is an int after resolution.

### ABR-05 MED: the recipe has no success checks, and failures come back as strings or JSON, not exceptions
- Most tools return text beginning "Error ..." (for example server.py:427-430, 672-675, 1505-1506, 1906-1909). `create_serum_track`
  returns JSON with `status` (server.py:453-505); a failure gives status FAILED and may roll the track back.
- The recipe has no check after any step, and the module docstring does not say the replayer must check.
- Fix: write the replay rule into the module docstring and into the recipe output: stop on "Error" prefix or status FAILED, then
  re-plan. This is cheaper than adding checks inside the recipe.

### ABR-06 MED: the Serum preset path is a placeholder string that the server will reject
- Ours: ab:134-135 emits `"preset_path": "<path of %s>"`. server.py:467-468 returns PRESET_FILE_INVALID for any path that is not an
  existing .SerumPreset file.
- Probe: `build_recipe` gives `{'preset_path': '<path of Pad A>', 'name': 'pad'}`.
- The generate_preset result (serum-mcp, `src/serum_mcp/server.py:952`, returns the path string) only exists at runtime, so the recipe
  needs a named token the replayer fills from that result, plus a manual step that records it.
- Fix: a token such as `"<preset_path:pad>"` and a replay rule that fills it from the generate_preset output.

### ABR-07 MED: "Macro 1" as a parameter name is unverified, and the alias does not apply to automation
- Ours: ab:136-139 (set_device_parameter "Macro n"), ab:189-200 (manage_clip_automation "Macro n").
- plugin_aliases.py:44-51 maps "macro 1" to "Macro 1" only inside set_device_parameter (server.py:1873-1885), and only for device
  names containing "Serum". manage_clip_automation (server.py:1737-1742) gets no alias. Remote:1462-1485 and 1849-1890 do an exact or
  partial name match on the live parameter.
- serum-mcp macros are user-named strings (`MacroSpec.name`, spec.py:844-846; `macro0..7` index base). The owner PLAYBOOK
  (line 205) lists macro1..8.name as STATE_NOT_OBSERVED. So the live Serum macro name is unknown.
- The serum_briefs text (ab:252-253) says "Macro 1 brightness" but never tells the generator which macros[] index or name to use.
- Fix: before the first build, run get_device_parameters on one Serum track and check the real macro names; use `parameter_index`
  (server.py:1850) if names differ. Map brief macro 1-4 to macros[0..3] with names.

### ABR-08 LOW: no MCP tool for add-notes-to-arrangement, so the session-clip route is required
- Confirmed (Q2). server.py has no @mcp.tool for `add_notes_to_arrangement_clip` (only the list entry at server.py:123). The
  recipe's route (ab:159-165) is valid and needs no change. D2 says "create_arrangement_midi_clip + add_notes_to_clip per role", so
  the deviation should be recorded in the checklist (ab:23-24 documents it in code only).
- Fix: none required. Optional: owner adds a wrapper tool.

### ABR-09 LOW: duplicate marker times produce two cue steps at one time and a misleading reason
- Ours: ab:112-113 reports a duplicate marker as "outside 0..total_s" (length 0), and ab:175-176 still emits a cue for the kept marker.
- Probe: markers at t=0 twice gives `SKIPPED marker a outside 0..total_s`. Remote:1264-1275 raises when a cue already exists at a
  time, so a duplicate would fail at replay.
- Fix: reject duplicate times with the reason "duplicate marker time" and do not emit cues for them.

### ABR-10 LOW: validation is inconsistent between check_inputs and build_recipe, and automation points are not range-checked
- ab:219 runs `_clean_note(item, 10**9)`, so notes past total_s pass check_inputs (probe: check_inputs returned []), and only then
  become manual SKIPPED steps (probe confirmed). check_inputs should take the real total.
- ab:194-197 accepts points at t=-5 and t=999 and emits them into the manual step (probe confirmed). Add range and ordering checks.

### ABR-11 LOW: the tests are weaker than their names suggest
- test_ableton_build.py:87-93 checks only extra argument names, not required arguments or types (so a missing `preset_path` would
  pass). Fix: compare against the signature's required params.
- test_ableton_build.py:81-84 uses a substring check (`"def %s(" % tool in text`), which is weak. Use the AST helper already in the file.
- test_ableton_build.py:144-149 asserts the marker name in the create args (encodes ABR-01).
- test_ableton_build.py:152-156 and 159-163 hard-code the fixture values (ok as fixtures, but they do not test D3 Macros 1-4 for every
  role when automation is absent).
- test_ableton_build.py:204-216 asserts no exception only; it does not check the output shape.
- test_ableton_build.py:19-20 skips silently when server.py is absent. The checklist allows skips with a reason, so this is acceptable
  as long as the skip reason shows in the report. Currently pytest shows 0 skipped here.

## Not a finding (checked and correct)
- Order: get_session_info first, then set_tempo 60 (test lines 96-99 hold).
- create_clip and add_notes_to_clip argument names match server.py (624-675) and Remote:747-814 (pitch, start_time, duration, velocity, mute).
- set_device_parameter argument names match server.py:1844-1852; device_index 1 and chain_index 0 are valid (chain 0 maps to None).
- manage_clip_automation argument names match server.py:1716-1723.
- create_cue_point bar=0 handling (Q4), and clip/start units (Q5).
- Stdlib-only module and the 5 MB JSON limit hold (tests pass).
