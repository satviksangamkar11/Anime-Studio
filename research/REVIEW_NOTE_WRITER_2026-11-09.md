# Review: score/note_writer.py (NWR, 2026-11-09)

Scope: score/note_writer.py, score/tests/test_note_writer.py against checklist section C (C1-C6), SKILL.md rules 1-12, the cut and shot tables, clock mode, music_bible.json and score/cue_sheet.py. Read only; no commit, no network, no model calls.

Pytest (run by reviewer): `python -m pytest score/tests/test_note_writer.py -q` -> `36 passed in 0.11s`

Probe scripts live in the scratchpad, not in the repo.

## Summary

- C1-C6 are present and pass. C2 (voice rule) and C6 (low-band rule) hold on the real reel. C5 MIDI is clean (see M-section below).
- Findings: 19 total. HIGH 5, MED 8, LOW 6.
- The writer is a faithful renderer of the plan. It silently drops or ignores several SKILL.md rules that the plan can carry (hard_cut swell, re-hook, peak, bass harmonic, hook_type behaviour). None of these is caught by the writer, and in some cases the test suite locks in the wrong behaviour.

## Judgement: SHIVA roles

Yes, the writer should honour the bible roles, or at least check them. Bible SHIVA roles are brass, pad, drone. Plan event role is lead. Lead is busy, so the writer cuts the theme to 2 of 4 notes in the 48.0-49.2 gap. SHIVA's degrees D2 A2 C3 D3 are 38, 45, 48, 50. All four are at or below LOW_MAX (50), so on brass they are exempt under voice and all four survive at half-time spacing (0.6818 s at 176 BPM). Rule 8 also asks for weighty instruments (low brass, choir pad, conch-like horn), not a lead preset.

Recommendation: the plan should set the SHIVA entry role to brass (H1 fix). The writer should refuse or warn when a god theme entry is on a role not in its bible roles, and warn when a theme loses notes to voice. The writer should not silently reroute the role.

## Findings

### H1 HIGH: SHIVA entry on lead (weighty-role rule broken, theme truncated silently)
- Where: score/note_writer.py:63 (EVENT_ROLE theme_entry = lead), :223-233 (role taken from plan, bible themes[..].roles ignored), :377-381 (theme notes), :411-421 (busy clip on lead).
- What is wrong: rule 8 wants a god's theme on weighty instruments. Lead is the glass lead preset. The writer keeps 2 of 4 SHIVA notes and emits no warning.
- Reproduction (probe1, real reel, plan REEL_PLAN as in tests):
  lead = [{t_s 48.0, dur 0.613636, pitch 38}, {t_s 48.681818, dur 0.518182, pitch 45}]
  Same plan with events[2].role = "brass":
  brass = [(48.0, 38), (48.681818, 45), (49.363636, 48), (50.045455, 50)], all four kept, spacing 0.6818 s.
- Fix: plan role brass for SHIVA. In writer, for a theme_entry whose theme has bible roles, error or warn (THEME_ROLE_NOT_IN_BIBLE) when the event role is not in that list. Add THEME_TRUNCATED warning (see M6).

### H2 HIGH: hard_cut transition writes no swell
- Where: score/note_writer.py:385-387 (only reverse_swell_to_cut gets a swell). Docstring decision 8 at :27-29.
- What is wrong: SKILL.md cut table says hard_cut needs a swell or reverse swell ending exactly on the cut frame. The plan's hard_cut at 48.0 gets nothing. Rule 4 (every cut is scored) is not met, and the writer returns ok True.
- Reproduction: REEL_PLAN cut at 48.0 is hard_cut. pad notes at 47.5-49.5: only the D4/A4 chord restart at 48.0 (dur 22.0). No swell ends at 48.0.
- Fix: write a swell for hard_cut too (same 1 s E4 swell, or the bible's signature reverse_swell), or error CUT_NO_SCORE when a hard_cut has no swell in the plan.

### H3 HIGH: bass is root only, no mid harmonic (rule 11)
- Where: score/note_writer.py:341-345 (bass segments use DRONE_PITCH 38 only), docstring decision 13 at :35.
- What is wrong: rule 11 (phone first) asks for bass below 200 Hz in mono plus a mid harmonic so phones hear it. The writer defers the harmonic to the preset. Nothing in the bible, plan or writer carries it, so the mid harmonic is silently missing.
- Reproduction: bass pitches on the real reel = {38} only, 153 notes.
- Fix: add a second bass-role note per step at a mid harmonic (for example D4 62 at a lower velocity, or A3 57), not gated by voice (it is pad-range, not busy). Add a test that bass has at least one pitch above 50.

### H4 HIGH: rehook_at_s and peak_at_s accepted and silently discarded
- Where: score/note_writer.py:32 (decision 11), _build :464-481 (never reads plan rehook_at_s or peak_at_s).
- What is wrong: rule 6 says the main re-hook must sit inside retention.rehook_window_s, and rule 7 says one peak. The writer does nothing with either, and does not check that an event of the plan exists at that time. The reel's MAIN theme is never played (no theme_entry with theme MAIN); lead has no notes between 31.5 and 42 s.
- Fix: for rehook_at_s, require a theme_entry or hit within one frame (error REHOOK_NO_EVENT) and warn when absent. Same for peak_at_s. Add a test.

### H5 HIGH: hook_type behaviour is not implemented or cross-checked
- Where: score/note_writer.py:301-302 (markers use hook_type only); no reads of cue shot beats, audio_cue, closing_hook anywhere in the file.
- What is wrong: SKILL.md rule 3 and the shot table say each hook_type has its own music. The writer does none of it and does not check the plan for it:
  - reveal (shots 1, 4, 5, 8; starts 0, 18, 26, 48): no bloom on the reveal second. Only shot 8 has an event (SHIVA).
  - reversal (shots 7 at 41 s, 9 at 56 s): drop-out, hit, re-enter darker. Only the 43.083 and 60.0 hits exist; there is no re-enter darker and no drop-out at 41 or 56.
  - closing: no unresolved chord, see M3; SHOT-010 is not labelled closing (M4).
  - suspense (shots 3, 6, 10): no ostinato density rise (M2).
- Fix: the writer should cross-check each shot: reversal shots need a drop-out + hit at the shot's impact, reveal shots need a theme or bloom event within one second of the reveal beat, closing shots need an end_sting and an unresolved tail. Emit an error code per missing element. The plan can then satisfy it. Rule 3 is in the owner spec, so this is required, not nice to have.

### M1 MED: ostinato density is per felt step, not per beat, under half or double feel
- Where: score/note_writer.py:350-353 (`sub = step / sec["steps"]`, where step is already multiplied by FEEL_STEP).
- What is wrong: decision 14 (docstring) says density_per_beat notes per beat. Half feel doubles the spacing, so the density halves.
- Reproduction (probe2, 120 BPM, SMALL_PLAN with feel half, density [2,2]): ostinato onsets 0.0, 0.5, ... = 1 note per beat. Normal feel gives 0.25 s spacing (4 notes per second = 2 per beat).
- Fix: `sub = (60.0 / sec["bpm"]) / sec["steps"]`, and add a test for half and double feel density.

### M2 MED: density upper bound and rising density ignored
- Where: score/note_writer.py:166-167 and :175 (`dens[0]` only).
- What is wrong: density_per_beat [2, 4] in BUILD is read as 2 for the whole section. SKILL.md suspense row says density rising across the shot. No ramp is produced.
- Fix: ramp from dens[0] to dens[1] across the section (or per shot, using the cue sheet shot boundaries). Test a [2,4] section and check the onset count in the first and last second.

### M3 MED: closing end sting is a single D2, not an unresolved chord
- Where: score/note_writer.py:382-383 (end_sting = LOW_PITCH 38 only).
- What is wrong: SKILL.md closing row says unresolved chord. Bible key_colours.unresolved is Dsus2 / Bb over D. A single tonic root is the opposite.
- Fix: end sting as a small chord (for example D2 with A2 and E3 for Dsus2, or Bb over D), low band, under voice. Keep the 0.3 s length and the low-band rule.

### M4 MED: marker names ignore closing_hook; SHOT-010 is labelled suspense
- Where: score/note_writer.py:301-302 (`name = f"{id} {hook_type}"`).
- What is wrong: cue sheet SHOT-010 has hook_type suspense and closing_hook true. The Ableton marker reads "SHOT-010 suspense", so the closing shot is not identifiable in the set.
- Reproduction: markers[-1] = {t_s 64.0, name "SHOT-010 suspense"}.
- Fix: when closing_hook is true, name the marker "<id> closing" (or include both), and add a test on the real cue sheet.

### M5 MED: quiet melodic moment not produced; bible quiet_moment contradicted
- Where: score/note_writer.py has no quiet-moment handling; bible quiet_moment at 11-18 says drone + MUNIS only.
- What is wrong: in 11-18 the writer emits bass, drums, ostinato and pad. No MUNIS theme is played (the plan has no event for it), and the writer does not check the bible's quiet_moment window.
- Reproduction: roles with notes in [11, 18) = bass, drums, ostinato, pad.
- Fix: the plan needs a MUNIS theme entry (drone + pad) in 11-18 with drums and ostinato off. The writer should warn when a bible quiet_moment window contains busy roles.

### M6 MED: theme truncation is silent
- Where: score/note_writer.py:411-421 (busy clip drops theme notes), :380-381.
- What is wrong: a theme that loses notes to voice has no warning, so the output looks fine.
- Fix: warn THEME_TRUNCATED with the count kept and dropped, per theme entry.

### M7 MED: incomplete or overlapping plans accepted with ok True
- Where: score/note_writer.py:152-177 (_sections does not check contiguity or overlap), :255-259 (cue cut not in plan is only a warning).
- What is wrong: section start 12.0 (gap 11-12) and section start 10.0 (overlap) both return ok True. A missing cut returns ok True with a warning. Rule 4 requires every cut scored.
- Reproduction: sections[1].start_s = 12.0 -> ok True, errors []. start_s = 10.0 -> ok True.
- Fix: errors for gaps and overlaps (or leave to plan_check, but make the writer refuse), and make a missing cue cut an error CUT_MISSING.

### M8 MED: tests lock in wrong behaviour and miss the rules above
- Where: score/tests/test_note_writer.py:253-260 (test_theme_entry_is_half_time_and_cut_by_voice_on_lead): asserts `len(lead) < 4`. This passes for any lead output, including a theme dropped to zero notes. It enshrines the SHIVA-on-lead truncation (H1). It checks no half-time spacing on lead.
- Missing tests: half/double ostinato density (M1), hard_cut swell (H2), bass mid harmonic (H3), rehook/peak (H4), closing marker (M4), section gap (M7), bible roles (H1), quiet moment (M5).
- Fix: rewrite the lead test to assert the agreed role (brass) keeps all four notes and spacing 1.0 s at 60 BPM, and add the missing tests.

### L1 LOW: drop-out limit test checks the fixture, not the writer
- Where: test_note_writer.py:243-244. It asserts REEL_PLAN events are <= MAX_DROPOUT_S. It would pass with the writer broken. The writer's own DROPOUT_TOO_LONG path is tested at :358-362, so this one is redundant.

### L2 LOW: busy-role zero-overlap test is vacuous for pluck and brass
- Where: test_note_writer.py:209-215. The reel has 0 pluck and 0 brass notes, so the loop never runs for them. The test covers drums, ostinato, hits and lead only.

### L3 LOW: malformed-plan test does not check error codes
- Where: test_note_writer.py:344-349 checks only that errors is non-empty. Probe4 confirmed each case gives its intended code today (PLAN, PLAN_SECTIONS, SECTION_BPM, ...). Adding the code assertion keeps it that way.

### L4 LOW: list or dict input for feel gives INTERNAL, not SECTION_FEEL
- Where: score/note_writer.py:159 and :216 (`feel not in FEEL_STEP` with an unhashable value).
- Reproduction: sections[0].feel = ["half"] -> errors [{"code": "INTERNAL", "message": "TypeError: cannot use 'list' as a dict key"}]. No crash, but the wrong code. Fuzz (400 mutated plans, 0 raises, 5 INTERNAL, all of this kind).
- Fix: `isinstance(feel, str) and feel in FEEL_STEP`.

### L5 LOW: BUSY is hard-coded and ignores the bible track_roles busy flags
- Where: score/note_writer.py:58. Bible track_roles brass busy is false, writer treats brass as busy. The output is stricter, so it is safe, but a bible edit will not change behaviour.
- Fix: derive BUSY from bible track_roles (with the current set as fallback).

### L6 LOW: too-short fragments dropped with only a counter
- Where: score/note_writer.py:399-400 and :441-442. stats.too_short counts silently dropped fragments; no warning is emitted. Harmless at current settings (1 fragment on the real reel), but it hides a lost note.
- Fix: warning NOTE_TOO_SHORT with role, time and pitch.

## MIDI (C5): no defects found

Checked by writing the reel MIDI to a scratch dir and parsing it with an independent minimal parser (probe3, not in repo):
- Header: format 1, 10 tracks, 480 ppq.
- 336 note-ons, 336 matching note-offs, no hanging notes, no note-off without note-on, end-of-track present and last in every track.
- Tempo meta 1,000,000 us on track 0, time signature 4/4, markers as meta 0x06 on track 0.
- Explicit status bytes (no running status); VLQ handled correctly for multi-byte deltas.
- Fuzz of write_midi with junk notes, markers and track types (150 cases): no exception escapes.

## Fuzz of write_notes (C-level robustness)

400 random mutations of REEL_PLAN plus junk cue voice unions: 0 exceptions escaped, 0 invariant violations in ok outputs (times within 0..total_s, velocity 1-127, pitch 0-127, positive durations). See L4 for the INTERNAL cases.

## Spec mapping (SKILL.md rules and checklist C)

| Item | Status | Required for owner spec? |
| --- | --- | --- |
| C1 deterministic, returns tracks/markers/automation | pass | yes |
| C2 times in 0..total, busy zero overlap under voice | pass (vacuous for pluck, brass) | yes |
| C3 events on frame, drop-out empty | pass for reel events | yes |
| C4 one marker per shot | pass (name wrong for closing, M4) | yes |
| C5 MIDI type 1, 480 ppq, 60 BPM | pass | yes |
| C6 hits under voice <= D3 | pass | yes |
| Rule 2 low hits under voice, gaps for bright | pass | yes |
| Rule 3 hook_type behaviour | missing (H5) | yes |
| Rule 4 every cut scored, hard_cut swell | missing (H2), coverage not checked (M7) | yes |
| Rule 6 re-hook, end hook | missing (H4), closing chord (M3) | yes |
| Rule 7 one peak | not checked (H4) | yes |
| Rule 8 god theme on weighty roles | broken for SHIVA (H1) | yes |
| Rule 11 mid harmonic on bass | missing (H3) | yes |
| Style: one quiet melodic moment | missing (M5) | yes (style section) |
| Ostinato density per beat | wrong under half/double (M1) | yes (decision 14) |
| Density rising in suspense | missing (M2) | yes (shot table) |
| Bible busy flags | ignored (L5) | nice to have |

## Test run

`python -m pytest score/tests/test_note_writer.py -q` -> `36 passed in 0.11s`
