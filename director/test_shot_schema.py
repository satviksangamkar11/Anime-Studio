from shot_schema import validate_shot, validate_shots

# SPEC_v2.2.md SHOT-07, beats filled to 5.2 s (the spec example stops at 1.6 s)
RICH = {"id": "SHOT-07", "episode": 2, "scene": "kadamba_leap", "mode": "fl2va", "seconds": 5.2, "aspect": "9:16",
        "purpose": "Krishna commits to the leap; the river is the stakes",
        "cast": [{"id": "CHAR-KRISHNA", "screen": "center", "facing": "right", "start_pose": "POSE-crouch-branch", "end_pose": "POSE-dive"}],
        "props": [{"id": "PROP-KALI-KAMLI", "where": "tied at waist"}], "set": "ENV-KADAMBA-BANK",
        "beats": [{"t": [0.0, 0.8], "acting": "bare foot grips the branch, hand tightens on bark, gaze settles on the river", "bhava": "resolve"},
                  {"t": [0.8, 1.6], "acting": "lowers centre of gravity, knees bend, shoulders tilt forward", "secondary": "sash still settling", "primary": True},
                  {"t": [1.6, 3.4], "acting": "holds the crouch, eyes fixed on the water", "hold": True, "bhava": "resolve"},
                  {"t": [3.4, 5.2], "acting": "launches, body arcs out over the bank", "secondary": "hair and sash trail"}],
        "camera": {"move": "track down with the fall", "lens_mm": 24, "height": "branch level", "start_framing": "full body", "end_framing": "water surface"},
        "layers": {"fg": "kadamba leaves, out of focus", "mid": "Krishna (cel)", "bg": "painted river and far bank", "fx": "splash sheet, composited"},
        "light": {"key": "low morning sun from screen left", "rim": "warm gold on Krishna", "mood": "earthy Braj daylight"},
        "compositing": {"generated": "character motion + splash", "held": "background plate", "post": "on-2s holds, impact frame at 4.1s"},
        "start_state": "Krishna crouched on the high branch, facing river (screen right)",
        "end_state": "white water sheet rising where Krishna entered",
        "cut_in": "match on action from SHOT-06", "cut_out": "splash wipe into SHOT-08",
        "keyframes": {"start": "keyframes/SHOT-07-FRAME-A.png", "end": "keyframes/SHOT-07-FRAME-B.png"},
        "refs": [], "subjects": [],
        "sound": "branch creak, wind, splash (no dialogue words)",
        "dialogue": [{"who": "SHRIDAMA", "t": [0.2, 1.4], "line_hi": "नहीं-नहीं लाला!", "line_en": "No, no, Lala!"}]}


def edit(**kw):
    return {**RICH, **kw}


def test_the_spec_shot_is_clean():
    assert validate_shot(RICH) == []
    assert validate_shots([RICH]) == []


def test_a_missing_field_is_named():
    shot = {k: v for k, v in RICH.items() if k != "purpose"}
    assert validate_shot(shot) == ["SHOT-07: missing purpose"]


def test_a_gap_and_an_overlap_between_beats():
    beats = RICH["beats"]
    gap = edit(beats=[beats[0], dict(beats[1], t=[1.0, 1.6])] + beats[2:])
    assert any("gap" in p for p in validate_shot(gap))
    overlap = edit(beats=[beats[0], dict(beats[1], t=[0.5, 1.6])] + beats[2:])
    assert any("overlap" in p for p in validate_shot(overlap))


def test_beats_must_reach_the_shot_length_within_tolerance():
    short = edit(beats=RICH["beats"][:3] + [dict(RICH["beats"][3], t=[3.4, 5.0])])
    assert any("beats end at 5.0" in p for p in validate_shot(short))
    assert validate_shot(edit(beats=RICH["beats"][:3] + [dict(RICH["beats"][3], t=[3.4, 5.23])])) == []


def test_the_brief_example_shot_is_valid():
    import json, re
    from pathlib import Path
    brief = (Path(__file__).parent / "MASTER_PROMPT_v2.2.md").read_text(encoding="utf-8")
    example = json.loads(re.search(r"## \(c\) RICH SHOT CONTRACT.*?```json\n(.*?)\n```", brief, re.S).group(1))
    assert validate_shot(example) == []


def test_two_primary_beats_fail_and_none_warns():
    beats = RICH["beats"]
    two = edit(beats=[beats[0], dict(beats[1], primary=True), dict(beats[2], primary=True), beats[3]])
    assert any("primary" in p and "at most one" in p for p in validate_shot(two))
    none = edit(beats=[dict(b, primary=False) for b in RICH["beats"]])
    assert any(p.startswith("SHOT-07: WARN") for p in validate_shot(none))


def test_a_hold_beat_needs_its_emotional_purpose():
    beats = [dict(b) for b in RICH["beats"]]
    beats[2].pop("bhava")
    assert any("hold beat 3 has no emotional purpose" in p for p in validate_shot(edit(beats=beats)))


def test_ref2va_needs_refs_and_subjects():
    shot = edit(mode="ref2va")
    assert any("ref2va needs refs and subjects" in p for p in validate_shot(shot))
    ok = edit(mode="ref2va", refs=["krishna_sheet.png"], subjects=["<Subject 1> is Bala Krishna in <Picture 1>"])
    assert validate_shot(ok) == []


def test_fl2va_needs_a_start_or_end_keyframe():
    assert validate_shot(edit(keyframes={"end": "b.png"})) == []
    assert any("fl2va needs a keyframe" in p for p in validate_shot(edit(keyframes={})))


def test_seconds_must_fit_one_h3_window():
    assert any("longer than one H3 window" in p for p in validate_shot(edit(seconds=16, beats=[{"t": [0, 16], "acting": "x"}])))


def test_unknown_ids_are_reported_only_when_a_bible_is_given():
    assert validate_shot(RICH, bible_ids={"CHAR-KRISHNA", "PROP-KALI-KAMLI", "ENV-KADAMBA-BANK"}) == []
    problems = validate_shot(RICH, bible_ids={"CHAR-KRISHNA"})
    assert "SHOT-07: unknown id PROP-KALI-KAMLI (not in style bible)" in problems
    assert "SHOT-07: unknown id ENV-KADAMBA-BANK (not in style bible)" in problems


def test_validate_shots_checks_unique_ids_and_episodes():
    assert any("duplicate id" in p for p in validate_shots([RICH, dict(RICH)]))
    assert any("missing episode" in p for p in validate_shots([edit(episode=None)]))
