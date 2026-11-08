"""Audit gaps of 2026-11-08: lattice fit (gap 2), tail-second mouth, camera words, editorial clock (gap 4)."""
from h3 import v4_to_h3 as v
from h3.schema_and_linter import SFX_CUE_RE


def _rows(eds, ep=1):
    return [{"id": f"SHOT-00{i + 1}", "episode": ep, "editorial_duration_sec": e, "lattice_n": 7,
             "pixel_frames": 124, "latent_slots": 37} for i, e in enumerate(eds)]


def test_fit_lattice_gives_every_cut_legal_handles():
    rows = _rows([5.0, 5.0, 6.0, 5.0])
    new, changes, problems = v.fit_lattice(rows)
    assert problems == [] and changes
    for r in new:
        assert r["pixel_frames"] == 5 + 17 * r["lattice_n"] and r["latent_slots"] == 5 * r["lattice_n"] + 2
        assert r["pixel_frames"] - round(r["editorial_duration_sec"] * 24) >= 14     # first/last need one handle, middle two
    assert rows[0]["lattice_n"] == 7                                                 # input is never mutated


def test_fit_lattice_is_idempotent_and_keeps_editorial_length():
    new, _, _ = v.fit_lattice(_rows([5.0, 7.0, 8.0]))
    again, changes, _ = v.fit_lattice(new)
    assert changes == [] and again == new
    assert [r["editorial_duration_sec"] for r in new] == [5.0, 7.0, 8.0]


def test_one_shot_reel_keeps_the_models_n():
    new, changes, problems = v.fit_lattice(_rows([5.0]))
    assert changes == [] and problems == [] and new[0]["lattice_n"] == 7


def test_mouth_state_follows_the_editorial_clock_through_the_head_handle():
    ms = {"0": "closed", "1": "open_non_verbal_breath", "2": "closed", "3": "closed", "4": "closed", "5": "closed"}
    track = {"performance_notes": {"narrator_mouth_closed": True, "mouth_state": ms}}
    probs = []
    # pf 175 = 8 clip seconds, editorial 144 frames (6 s) starting 20 frames into the clip (head handle 20)
    states, rule = v._mouth(track, 175, "S", probs, ed=144, ti=20)
    assert probs == []
    assert states["1"] == "open_non_verbal_breath" or states["2"] == "open_non_verbal_breath"   # the breath second moved with the handle
    assert states["0"] == "closed" and states["7"] == "closed"                                    # handle seconds are closed
    assert list(states) == [str(i) for i in range(8)]
    _, _ = v._mouth(track, 175, "S", probs, ed=144, ti=0)
    short = {"performance_notes": {"narrator_mouth_closed": True, "mouth_state": {"0": "closed"}}}
    probs = []
    v._mouth(short, 175, "S", probs, ed=144, ti=0)
    assert any("second 2" in p for p in probs)                                                    # a visible second with no state is a problem


def test_stage_sentences_are_placed_after_the_head_handle():
    d = [{"t0": 0.0, "t1": 1.0, "action_pose_expression": "first move", "audio_cue": "a bell rings"},
         {"t0": 5.0, "t1": 6.0, "action_pose_expression": "last move", "audio_cue": "wind hum"}]
    p0, p1 = [], []
    st0, _ = v._stages(d, 175, "S", p0, 0)
    st1, _ = v._stages(d, 175, "S", p1, 30)
    assert "first move" in st0["1_starting_state"]
    assert "first move" in st1["1_starting_state"] or "first move" in st1["2_anticipation"]


def test_camera_words_and_sound_words_of_the_writer_are_read():
    assert v._motion_of("wide, pull back continues") == "Pull Out"
    assert v._motion_of("slow crane down continues") == "Pedestal Down"
    assert v._motion_of("medium, slow arc right begins") == "Arc Shot"
    for word in ("birdsong and the stream", "a light bowstring twang", "a deep conch-like swell"):
        assert SFX_CUE_RE.search(word)
