# W2-E (G11, G12)
- G11: voice_rest = shot-relative seconds everywhere. story_shape.reel_window() converts (shot start + value); SHAPE-10 checks 0<t0<t1<=own shot, span 2-4 s. cue_sheet.blocking_window() same conversion for voice_rest and silence_ok. blocking/1.1: silence_ok validated (shot-relative, max 2.0 s, within writer_seconds); 1.0 unaffected.
- director/test_story_shape.py voice_rest values moved from reel clock to shot-relative (old clock was the bug).
- G12: score.cue_sheet CLI --blocking-dir; writes cue_sheet.json["cue_rows"] ({rows, notes}) and cue_rows.csv. cue_rows(sheet, blocking=) takes hits from blocking sound_cues kind hit, rest from blocking voice_rest.
- Tests: director/test_voice_rest_clock.py, score/tests/test_cue_sheet_cli_rows.py.
