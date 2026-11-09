# PCR2 review: score/plan_check.py and score/tests/test_plan_check.py (2026-11-09)

Reviewer PCR2 (Haiku, high). Review only: no code or test file was edited.
Evidence: `python -m pytest score/tests/test_plan_check.py -q` = 98 passed (98 collected).
Probes (rerun them to reproduce): research/_probe_pcr2_scenarios.py, research/_probe_pcr2_more.py, research/_probe_pcr2_voice.py, research/_probe_pcr2_fuzz.py (args: seed count).
Inputs used: real cue sheet stories/kalika_puran_bhag1/pack_opus_high_20261108_v4_deva/score/ep1/cue_sheet.json, stories/kalika_puran_bhag1/music_bible.json, the SKILL, the strict checklist section A, blot rules 43-45, the style study.

PCR2-1 | HIGH | score/plan_check.py:381 (act lookup), :352-372 (_bible_tempo_ok), :375-409 (_check_tempo) | The section act is checked only as a name in the cue act list. Its time span is never compared with the cue act spans, so candidates, bible tempo and bible genre are judged on the label, not on the time. Proof: one section 0-70 s, act BUILD, bpm 128, genre hypnotic_techno (rest of the good plan kept) -> ok True. 128 is no candidate for HOOK (60, 90, 125, 175, 174), DROP (60, 90, 124, 176) or OUTRO. Likewise DROP 34-64 relabelled BUILD at 128 hypnotic -> ok True (probe S1, S3). Fix: take each section's act from the cue act whose span holds its start, require the section to lie inside that span (split at act boundaries), then run candidate and bible checks against that act.

PCR2-2 | HIGH | score/plan_check.py:497-512 (busy set at :499, skip for non-busy roles at :508) | The voice-window rule only consults bible busy flags. brass, horn, pad, drone and bass are not busy, so themes and drops on them inside speech pass. Proof: MAIN theme_entry on brass at 20.0 s (inside voice union) -> ok True; drop event on horn at 20.0 s -> ok True; MAIN theme on pad at 20.0 s -> ok True (probe V3, V5, V6; control V4 on vocal correctly gives BUSY_IN_VOICE). SKILL rule 2: inside voice only drone, pad, bass and soft pulse; themes go in the gaps. Bible note for brass: low brass only under voice. Fix: inside the voice union allow only drone, pad, bass and soft pulse; any theme_entry or drop inside the union is BUSY_IN_VOICE; brass or horn entries and hits inside the union need band low.

PCR2-3 | MED | score/plan_check.py:609-611; score/tests/test_plan_check.py:615-619; research/STYLE_STUDY_Anirudh_Sai_2026-11-09.md:131 | Style study row 010 asks for the end sting bright attack after the last word, at 69.8 s. 69.8 is before last_speech_end_s (69.846), so the checker demands band low at 69.8 and a test asserts it. Blot rule 44 (style first) says stop and ask the owner. Fix: owner decision. If bright is wanted, the sting must start at or after 69.846 (GOOD uses 69.85).

PCR2-4 | MED | score/plan_check.py:235-252 (_shape_section); D11 docstring at :48 | D11 says every key the SKILL lists is required, but harmony, density_per_beat and intensity are not checked. Proof: those three removed from every section -> ok True (probe S5). Fix: add them to the section shape check, or change D11 to name the optional keys.

PCR2-5 | MED | score/plan_check.py:398-409 (_check_tempo), :423-457 (_check_cuts) | SKILL rule 6 (something new enters or leaves at every shot boundary) is not enforced, and it is missing from the enforced list at SKILL.md:137. Proof: 48-64 split into two identical sections with a plain cut at 56 -> ok True (probe S6c). Fix: at each cue cut require a change in bpm, genre, roles_on, or an event within 0.5 s of the cut; otherwise a new code (for example SHOT_BOUNDARY_STATIC).

PCR2-6 | MED | score/plan_check.py:535-553 (_check_gods); D13 at :53-55; fast test at :545-549 | Checklist A6 and A8 and SKILL.md:137 say every god theme entry needs a drop-out and half feel. The checker demands them only where the section bpm is 120 or more. Proof: SHIVA at 0.0 s in the 60 BPM HOOK, no drop-out, feel normal -> ok True (probe S22). Fix: enforce unconditionally as the checklist says, or get owner sign-off and change the checklist and SKILL text to match D13.

PCR2-7 | MED | score/plan_check.py:366-368 (set comprehension over tempo_map.shot_genres values); _bible_shape at :192-202 does not look at tempo_map; score/tests/test_plan_check.py:721-768 (fuzz) | A non-string value in tempo_map.shot_genres (list or dict) raises TypeError: unhashable. check_plan catches it and reports CHECK_CRASH, not BIBLE_SHAPE. Proof: SHOT-004 = ["melodic_techno"] -> CHECK_CRASH (probe S7b). Random fuzz of cue and bible (research/_probe_pcr2_fuzz.py) found 26 crashes in 15000 cases, all from this path. The test fuzz mutates only the plan, so the D9 guarantee that CHECK_CRASH never fires is untested for cue and bible. Fix: keep only string values in that comprehension, validate tempo_map shape in _bible_shape, and extend the fuzz to cue and bible.

PCR2-8 | MED | score/plan_check.py:412-420 (_cut_transition); test at score/tests/test_plan_check.py:348-351 | The check forbids act_change on a same-act cut, but nothing requires an act_change cue cut (not hard) to carry act_change or a hard transition. Proof: cue cut 34.0 (act_change true, hard_cut false) with transition bed_continues -> ok True (probe S4). SKILL table: bed continues is the same-act rule. Fix: if cue act_change is true, the transition must be act_change or a hard transition; otherwise CUT_TRANSITION_BAD.

PCR2-9 | MED | score/plan_check.py:602 and :609 (last_speech_end_s); SKILL.md:19-20 (last_voice_end_s) | SKILL rule 2 says an end sting before retention.last_voice_end_s needs band low; the checker uses last_speech_end_s. The real cue sheet has both at 69.846, but the blot rule 43 amendment says last_voice_end_s is 70.0, so the spec and the data disagree. Proof: last_voice_end_s set to 70.0 in the cue and a bright sting at 69.9 -> ok True (probe S8). Fix: owner says which field the rule means; checker, SKILL and checklist A12 must name the same one.

PCR2-10 | LOW | score/plan_check.py:592-614 (_check_end) | The tail is never compared with the end of the reel. at_s + tail_s may run past total_s, and at_s = 70.0 is accepted (window inclusive). Proof: sting at 69.95 with tail 0.45 (ends 70.40) -> ok True (probe S19). Fix: require at_s + tail_s <= total_s.

PCR2-11 | LOW | .claude/skills/score-reel/SKILL.md:127 vs score/plan_check.py:612-614 | The SKILL plan example end_sting has no tail_s, but the checker requires it. Proof: that event alone gives END_STING (probe S9). Fix: add tail_s to the example.

PCR2-12 | LOW | score/plan_check.py:30-31 (D6); score/tests/test_plan_check.py:282 (comment) | D6 says the voice window 44.2-48.0 ends at the SHIVA entry; the cue union window is [44.2, 47.899]. The test comment calls cuts 18.0 and 26.0 plain cuts, but cue cut 18.0 has hard_cut true. Comments only; asserted behaviour is unaffected. Fix: correct the text.

PCR2-13 | LOW | score/tests/test_plan_check.py:151-152, :181-182, :268-269 | Three tests assert only that one code is absent, not ok or the rest of the report, so they would pass with the rule deleted. Impact is low because other tests check that the good plan is ok. Fix: assert ok True on the good plan variant, or assert the exact error set.

Counts: HIGH 2, MED 7, LOW 4 (13 findings).
What holds: the 98 tests pass; most BAD variants assert exact code sets; no CHECK_CRASH from plan-only fuzz (190 plan mutations plus 120 nested); the frame, cut-pairing, dropout range, logo, rehook, peak and bible-reference rules behave as their docstrings say on the probes.

## Re-check (coordinator, blot rule 8; Haiku high)

Reran: pytest score/tests/test_plan_check.py = 113 passed. Probes research/_probe_pcr2_scenarios.py, _probe_pcr2_more.py, _probe_pcr2_voice.py, research/_probe_pcr2_fuzz.py (seeds 1, 7, 99: 15000 cases) = 0 CHECK_CRASH. Extra probes: cue acts missing or non-numeric start_s/end_s -> CUE_SHAPE (no crash); feel quad on a section -> ok True; cut 41 theme_handover with nothing new -> ok True, no warning; identical split at 56 with theme_handover -> ok True, no warning; swell_to_cut at 56 with nothing new -> ok True, no warning.

Per finding:
- PCR2-1 RESOLVED. S1, S2, S3 now give SECTION_ACT_MISMATCH (plan_check.py:407-417, D20). Tests test_pcr2_1_* added.
- PCR2-2 PARTLY RESOLVED. Themes and drops that start in speech now fail (THEME_IN_VOICE / DROP_IN_VOICE, plan_check.py:556-561): probes V3, V5, V6 fail. Still open for sustained non-busy roles: see PCR2-R-1.
- PCR2-3 REJECTED by coordinator (69.85 bright sting allowed). Not re-checked against STYLE_STUDY row 010.
- PCR2-4 RESOLVED. SECTION_FIELD_MISSING for harmony, density_per_beat, intensity (plan_check.py:262-264); section still judged; parametrised test added.
- PCR2-5 PARTLY RESOLVED. NOTHING_NEW_AT_CUT is a warning only, so ok stays True. It exempts every transition except none and bed_continues, so theme_handover and swell_to_cut with no change pass silently. See PCR2-R-2.
- PCR2-6 REJECTED by coordinator (SKILL rule 8 = fast act only). Still open against checklist A6/A8 and SKILL.md:137; S22 still ok True.
- PCR2-7 RESOLVED. tempo_map shape validated (plan_check.py:213-218): S7, S7b give BIBLE_SHAPE; 0 crashes in the fuzz; cue-acts shape added (CUE_SHAPE, plan_check.py:177-179); fuzz tests for bible and cue (200+ cases each).
- PCR2-8 RESOLVED. act_change cut needs act_change or a hard transition (plan_check.py:466-468). S4 gives CUT_TRANSITION_BAD; test_pcr2_8.
- PCR2-9 REJECTED by coordinator (both values 69.846). Not changed in code: _check_end still reads last_speech_end_s (plan_check.py:674).
- PCR2-10 RESOLVED. D24 at plan_check.py:687-688. S19 gives END_STING; test_pcr2_10.
- PCR2-11 RESOLVED. SKILL.md:127 end_sting example now has tail_s.
- PCR2-12 RESOLVED. D6 text now uses [44.2, 47.899) (plan_check.py:30-31); test comment at test_plan_check.py ~281 says 18.0 is a hard cut.
- PCR2-13 RESOLVED. test_a1_coverage_passes_on_good_plan, test_a2_candidate_tempo_passes, test_a3_change_at_act_change_passes now assert exact empty code sets.

New defects from the fixes:
- PCR2-R-1 HIGH (completes PCR2-2). plan_check.py:547-567 (_check_busy). Only busy roles are muted in speech, and brass and horn are not busy. The good plan itself plays brass and horn through speech: section 48-64 has roles_on [bass, brass, pad, horn, drums], voice_gated true, and speech windows [49.2, 55.89) and [57.2, 63.876) fall inside it; GOOD returns ok True with no warnings. SKILL rule 2 allows only drone, pad, bass and soft pulse inside voice windows. Fix: for each voice-gated section, roles outside the allowed set must be muted inside the union (or brass and horn treated as busy); add a test that GOOD fails when brass stays in roles_on through speech.
- PCR2-R-2 MED (completes PCR2-5). plan_check.py:658. The exemption list is only none and bed_continues. Proof: N2 (identical split at 56 with theme_handover) and N4 (swell_to_cut, no change) both give ok True with no warning. Warning-only, so ok stays True. Fix: make an unchanged cut an error unless it has a named reason in the plan, and do not exempt transitions by name.
- PCR2-R-3 LOW. plan_check.py:102 accepts feel quad with no docstring decision (no D-note), and .claude/skills/score-reel/SKILL.md:117 still lists normal|half|double only. Proof: section feel quad -> ok True. Fix: document quad in D-notes and SKILL, or remove it.
- PCR2-R-4 LOW (design limit, not a regression). plan_check.py:556-560. A theme or drop is judged on its start only, and the plan has no duration, so a theme that starts in a gap at 18.2 s can run into speech. Proof: the existing test test_a7_busy_theme_in_voice_gap_passes (18.2 s) passes. Fix: the note writer must truncate at voice starts (checklist C2), and the checker should say so in D21.

Counts after re-check: resolved 8 (PCR2-1, 4, 7, 8, 10, 11, 12, 13); partly resolved 2 (PCR2-2, 5); rejected by coordinator 3 (PCR2-3, 6, 9); new: HIGH 1 (R-1), MED 1 (R-2), LOW 2 (R-3, R-4).
