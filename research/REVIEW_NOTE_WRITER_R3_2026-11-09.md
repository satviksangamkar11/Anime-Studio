# NWR3 review of score/note_writer.py and its tests (2026-11-09)

Reviewer NWR3 (Haiku, high). Review only: no code or test edited, nothing committed or pushed.
Scope: score/note_writer.py (Decisions 1-29), score/tests/test_note_writer.py, research/STYLE_STUDY_Anirudh_Sai_2026-11-09.md
(reel-1 map table), .claude/skills/score-reel/SKILL.md, blot.md rules 43-45, research/BIBLE_STYLE_FIX_SPEC_2026-11-09.md,
stories/kalika_puran_bhag1/music_bible.json, cue_sheet.json (pack_opus_high_20261108_v4_deva/score/ep1).

Evidence: `python -m pytest score/tests/test_note_writer.py -q` = 90 passed. Probes: research/_probe_nwr3_reel.py
(real reel notes from the test fixture, all checks) and research/_probe_nwr3_fuzz.py (17 malformed cases, 25 s limit each).
Determinism (two runs identical) and MIDI round trip (555 notes, 13 tracks, markers, tempo 60 BPM) pass. No gated note sounds
under voice, no note sounds in a drop-out, every bass root has its mid harmonic, every theme motif is complete, the 34.0 kick
exists, the 60.0 hit is pitch 38, the end sting is at 69.85 (after 69.846) and clipped at 70.0.

NWR3-1 | HIGH | score/note_writer.py:905-906 with stories/kalika_puran_bhag1/music_bible.json:183-185 | Piano is not gated (bible busy false), so the MAIN cliffhanger plays under speech at full velocity: piano D4 at 65.0 s, F4 at 66.0 s, E4 at 67.0 s, all vel 100, inside voice window 64.6-67.598 (probe _probe_nwr3_reel.py voice section). Breaks SKILL rule 2 and spec item 5 (piano busy true); the bible note "may sit softly under voice" is not implemented anywhere (theme velocity is fixed 100 at line 664). Test test_note_writer.py:608 and :669-671 enshrine the defect. Fix: set piano busy true in the bible (spec item 5), gate it, and keep the quiet moment as a gap-only statement; update those tests.

NWR3-2 | HIGH | score/note_writer.py:543-544 and 577-584 (half-time drums run from the section start, plan 48-64) | Shiva's reveal at 48.0 s is hit by drums: kick 36 vel 104 at 48.000, snare 38 vel 94 at 48.682, hats vel 79 at 48.341 and 49.023, all during his theme (probe, 47.5-50.8 dump). Rule 8 and the study row 008 ("0.4 s silence, then his theme ... Never a drop on a divine reveal") require the drums to stay out until the theme has been heard. Test test_note_writer.py:418-423 enshrines the kick at 104. Fix: cut drums from the divine entry's drop-out end to the end of its theme (about 50.8 s) in the shot pass, and keep the kick out of the elevation hit.

NWR3-3 | MED | score/note_writer.py:494-501 (_ramp_onsets), 527-534 (_grid), 604-607 (bass loop), 612-613 (kick loop) | No upper bound on bpm or density_per_beat: a finite bpm of 1e9, a density of 1e9, or a bpm of 1e300 never returns (fuzz: TIMEOUT >25 s), while bpm 1e6 returns in 0.32 s. Breaks "never raises, returns a report" in practice (hang or memory blow-up). Fix: bound bpm (for example 20-400) in _sections (line 247) and density (0-16) at line 258-260, with a SECTION_BPM / SECTION_DENSITY error.

NWR3-4 | MED | score/note_writer.py:136 and 669-670 | The end sting is always the low cluster D2 E2 A2 (38, 40, 45, vel 110), even after the last word (69.85 s is after last_speech_end_s 69.846). The study row 010 asks for "end sting's bright attack after the last word", and SKILL rule 2 allows a bright attack after the last word. Fix: use a bright cluster (for example Dsus2 D5 E5 A5) when the sting starts at or after retention.last_speech_end_s, keep the low cluster when it starts under voice; add a test.

NWR3-5 | MED | score/tests/test_note_writer.py:34-63 (REEL_PLAN) vs research/STYLE_STUDY_Anirudh_Sai_2026-11-09.md:123, 128, 130 | The fixture does not carry three items of the reel-1 map: row 002 "half-time heartbeat kick" 6-11 s (no drums there: HOOK is ambient, probe shows none), row 007 "chaos from 16ths and Kamadeva's hook" at 41 s (no theme event 41-48), and row 009 "Kamadeva's hook slowed and pitched down; silence" 56-64 (no event; the full half-time kit runs until 59.6 s). Either add them to the plan (with bible shot_genres and the curse_56_64s transform) or write the deviation into the bible and the test docstring.

NWR3-6 | MED | score/tests/test_note_writer.py:65 (_cut(11.0, "act_change")) vs stories/.../cue_sheet.json cuts (11.0: hard_cut true) | The 11.0 s cut is a hard cut in the cue sheet but the plan gives act_change, so no swell or riser ends on that frame (study row 002 "Riser ends on the 11 s hard cut"; SKILL cut table: hard_cut needs a swell ending on the cut frame). Fix: plan reverse_swell_to_cut (or hard_cut) at 11.0 and add a test that the 1 s swell ends at 11.000.

NWR3-7 | LOW | score/note_writer.py:74-75 (Decision 22) and 608-609 | The docstring says genre comes from "bible tempo_map genre"; the code reads only the plan section genre, and bible tempo_map.genre and shot_genres are never read in note_writer.py. score/plan_check.py:40-44 does check the genre against the bible, so this is a documentation mismatch. Fix: correct Decision 22.

NWR3-8 | LOW | score/note_writer.py:115 and 906 (GATED_EXTRA = brass only) | Horn is not gated (bible busy false, music_bible.json:191-193): a SHIVA theme on horn at 2.0 s plays its octave partners (62 at 2.0 s, 63 at 3.0 s, vel 70) under the voice window 0.5-3.49 s (probe with an added horn event). Latent in the reel (the fixture uses brass). Fix: add horn to GATED_EXTRA, or change the bible note to say horn is gated.

NWR3-9 | LOW | score/note_writer.py:998 (ch = idx % 16) | MIDI channel is the position among tracks with notes, so it changes with the role set and the vocal track lands on channel 10 (index 9), the GM drum channel (probe: track order drone 0 ... vocal 9, piano 10, folk_perc 11). Fix: a fixed role-to-channel map that skips channel 9.

NWR3-10 | LOW | score/tests/test_note_writer.py:5-7 (docstring) | The docstring says SANDHYA enters at 18.0 s and BRAHMA at 26.0 s; the fixture has SANDHYA at 25.36 (line 54) and no BRAHMA event. Fix: update the docstring to match the fixture.

NWR3-11 | LOW | score/note_writer.py:341-342 | A bible theme with roles as a string ("lead") skips the role check because the check needs a list, so any role is accepted (fuzz case bible_theme_roles_str: ok true). Fix: require a list of role names, else THEME_ROLE_NOT_IN_BIBLE.

NWR3-12 | LOW | stories/kalika_puran_bhag1/music_bible.json:258-260 vs research/STYLE_STUDY_Anirudh_Sai_2026-11-09.md:127 and spec item 10 | The re-hook is at 40.25 s; the study (row 006 and the text "the re-hook moves to 34.0 s") and spec item 10 say 34.0 s. The bible note explains the move (speech covers 34.3-40.2), so this is an owner decision, not a code defect. Fix: owner to confirm 40.25 or 34.0 and record it in DECISION_LOG.md.

Counts: HIGH 2, MED 4, LOW 6 (NWR3-7 to NWR3-12).

## Re-check (round 6, Haiku high, one re-check per blot rule 8)

Probes rerun: research/_probe_nwr3_reel.py, research/_probe_nwr3_fuzz.py, and research/_probe_nwr3_recheck.py (new, round 6).
pytest score/tests/test_note_writer.py: 105 passed. Git cannot diff the fix: score/ is untracked (no snapshot), so the
test expectations below are the ones I read at review time plus the r6 tests; I did not get a full diff list of the 7.

Per finding:
- NWR3-1 PARTLY RESOLVED. Piano, brass and horn under speech are now capped at velocity 50 (Decision 31); MAIN piano
  65/66/67 s are 50 (probe). Piano is still not gated and the bible still says busy false, while spec item 5 says busy
  true. The soft cap follows the bible note "may sit softly under voice", so this is an owner call, not a code defect.
- NWR3-2 RESOLVED. No drum or folk_perc onset in 48.0-50.7 s; SHIVA's last note ends 50.659 s; first drum 50.727 s at vel 50 (Decision 32).
- NWR3-3 RESOLVED. Fuzz: bpm 1e9, 1e300, density 1e9 return SECTION_BPM / SECTION_DENSITY in under 1 s (bounds 20-300, 0-16).
- NWR3-4 RESOLVED. Sting at 69.85 s writes low 38/40/45 and bright 74/76/81, all vel 110, clipped at 70.0 (Decision 34).
- NWR3-5a RESOLVED. Heartbeat kicks 6.0, 6.25, 7.0 ... 10.25 s in the 6-11 s shot.
- NWR3-5b RESOLVED. Chaos entry at 43.2 s: 74 75 81 84 80 on lead at 0.117 s steps, all inside gap 43.036-44.2.
- NWR3-5c NOT RESOLVED, see NWR3-R-1 (the curse motif is swallowed).
- NWR3-6 RESOLVED. Plan cut 11.0 is reverse_swell_to_cut; pad 64 swell at 10.0 s, 1.0 s long, ends at 11.0 s.
- NWR3-7 NOT RESOLVED. note_writer.py:75 (Decision 22) still says "bible tempo_map genre"; note_writer never reads bible tempo_map (grep). plan_check.py:40-44 does check the bible genres. LOW, doc only.
- NWR3-8 RESOLVED. Horn is in GATED_EXTRA and LOW_OK; SHIVA-on-horn partners at 2.0/3.0 s are gone, low notes 38/39 remain at vel 50.
- NWR3-9 RESOLVED. MIDI_CHANNEL: drums 9, vocal 10, piano 11, folk_perc 12, horn 13; no other role on channel 9.
- NWR3-10 RESOLVED. Test docstring now says SANDHYA 25.36, KAMADEVA 29.69, no BRAHMA.
- NWR3-11 RESOLVED. A string roles value gives THEME_ROLE_NOT_IN_BIBLE (fuzz).
- NWR3-12 rejected by coordinator, not re-opened.

Test expectations checked (the coordinator's 7):
- (2) test_c24_peak_in_highest_section_is_accepted (test lines 425-436): the assertion moved to 50.727 s at vel 50, but the comment
  above it still says "velocity ... = 104" (stale comment, see NWR3-R-4). Whether 48.0 is still the one peak: see NWR3-R-3.
- (7) test_r6_kamadeva_curse_entry_is_half_time_on_pad (test lines 1061-1067): asserts only the F4 (65) and C5 (72) onsets and
  says the D4 and A4 are "the base pad". That acceptance is the defect in NWR3-R-1.
- test_c25_closing_end_sting_is_dsus2_cluster: now six notes (low plus bright). Matches Decision 34; OK.
- test_c26_quiet_moment_only_listed_roles_on_reel: piano onsets 64-67 unchanged; still passes with piano soft. OK.
- test_c27_busy_roles_come_from_bible_track_roles: unchanged, still asserts piano busy false. OK against the bible.
- test_r6_heartbeat_survives_the_expression_beat_shot: kicks 0.0, 0.25, 1.0, 1.25. OK.
- test_r6_kamadeva_chaos_entry_is_quad_and_transformed: five notes in the gap. OK.

NEW defects from the fixes:

NWR3-R-1 | HIGH | score/note_writer.py:901 (merge takes max, Decision 16) with the curse entry at 56.0 (test_note_writer.py:66-67) | The curse motif on pad is swallowed: its D4 (62) at 56.0 s and A4 (69) at 57.364 and 58.727 s have no attack, because the base pad notes 62 and 69 run 48.0-59.6 s and the merge keeps them. Probe: "onset 56.0 pitch 62: NO ATTACK", "57.3636 pitch 69: NO ATTACK", "58.7273 pitch 69: NO ATTACK"; only F4 65 at 56.68 and C5 72 at 58.05 are heard. Violates the transform rule (the motif must be heard, transformed, not swallowed; coordinator's point 7). Fix: when a theme note has the same pitch as a base note, cut the base note at the theme onset and resume it at the theme note's end, or move the curse to a role without the base pad (for example piano or lead), so the MIDI same-pitch merge never hides an onset.

NWR3-R-2 | MED | score/note_writer.py:901 (merged[-1][2] = max(...)) | The same merge raises the base pad 62/69 that starts at 48.0 s from velocity 84 (the section level, probe with the curse removed) to 100 (probe: "pad 62 vel 100 at 48.0"), because the curse's theme velocity 100 is merged into the note that starts 8 s earlier. So the level at the elevation comes from a note at 56 s. Fix: a merged note keeps the velocity of its first note (or theme notes are never merged), same root cause as R-1.

NWR3-R-3 | MED | score/note_writer.py:707 (every theme note fixed at velocity 100), 710 (partner 70) | Answer to the coordinator's question 2: the 48.0 elevation is the highest section (the peak check passes) but it is no longer the one musically distinct attack. Theme notes are all velocity 100, so loud (vel 100) attacks at 3.5, 4.5, 5.5, 25.36, 29.69, 40.25, 43.2, 48.0 and 56.68 s tie with the elevation, and the hits at 34.0, 43.083, 60.0 and 69.85 s (vel 110) are louder than it (probe, "loudest attacks" dump). The kick that marked the 48.0 entry is gone (fix 2), so after the fix the entry's only louder-than-norm element is the R-2 pad artifact. Fix: theme velocity from the section (vel of the entry's section, with the elevation entry above the rest) and hits below the elevation at the peak, then re-check rule 7 (one peak per reel).

NWR3-R-4 | LOW | score/note_writer.py:21 (Decision 3: "The end sting is always ... low"); score/tests/test_note_writer.py:425-427 (stale "= 104" comment); note_writer.py:75 (see NWR3-7) | Stale docs: Decision 3 contradicts Decision 34 (bright sting after last speech); the peak test comment states 104 while the assertion is 50. Fix: update the text.

Re-check counts: NEW HIGH 1 (R-1), NEW MED 2 (R-2, R-3), NEW LOW 1 (R-4). Original NWR3-1..11: 10 resolved (2, 3, 4, 5a, 5b, 6, 8, 9, 10, 11), 1 partly (NWR3-1, owner call on busy flag), 2 not resolved (NWR3-5c = R-1; NWR3-7, doc only). NWR3-12 rejected by the coordinator.
