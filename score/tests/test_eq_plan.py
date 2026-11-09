"""Tests for score/eq_plan.py: the EQ filters do what they claim, the masking finder sees two tones in one
band, and the sidechain helpers duck only when the key is active."""
import numpy as np
from scipy.signal import sosfreqz

from score import eq_plan as eq

SR = eq.SR


def _gain_db(sos, f):
    w, h = sosfreqz(sos, worN=[f], fs=SR)
    return 20 * np.log10(np.abs(h[0]))


def _sine(f, seconds=1.0, amp=0.5):
    t = np.arange(int(seconds * SR)) / SR
    return amp * np.sin(2 * np.pi * f * t)


def _rms(x):
    return float(np.sqrt(np.mean(x[len(x) // 4: 3 * len(x) // 4] ** 2)))


def test_bed_high_pass_removes_50_hz():
    chain = eq.chain_for("bed", "bed", "loop", "pad.wav")
    x = np.stack([_sine(50.0)] * 2)
    y = eq.apply_chain(x, chain)
    assert _rms(y[0]) / _rms(x[0]) < 0.15       # about -20 dB at 50 Hz with a 180 Hz high-pass
    z = eq.apply_chain(np.stack([_sine(800.0)] * 2), chain)
    assert _rms(z[0]) / _rms(_sine(800.0)) > 0.9  # musical content passes


def test_mud_cut_lowers_320_hz_by_set_db():
    peak = eq.peaking_sos(eq.MUD_HZ, eq.MUD_DB, eq.MUD_Q)
    assert abs(_gain_db(peak, eq.MUD_HZ) - eq.MUD_DB) < 0.05
    chain_mud = eq.chain_for("chords", "chords", "loop", "chord.wav", (), mud=True)
    chain_none = eq.chain_for("chords", "chords", "loop", "chord.wav", (), mud=False)
    assert len(chain_mud) == len(chain_none) + 1
    # the mud cut is the only difference, so the combined response at 320 Hz drops by MUD_DB
    total_mud = sum(_gain_db(s, 320.0) for s in chain_mud)
    total_none = sum(_gain_db(s, 320.0) for s in chain_none)
    assert abs((total_mud - total_none) - eq.MUD_DB) < 0.05


def test_bass_low_pass_above_job():
    chain = eq.chain_for("bass", "bass", "loop", "bass_loop.wav", (), mud=False)
    assert _gain_db(chain[-1], 6000.0) < -20.0           # bass is low-passed well above 3 kHz
    reese = eq.chain_for("bass", "bass", "loop", "reese_bass.wav", (), mud=False)
    assert _gain_db(reese[-1], 3500.0) > -3.0            # the reese keeps grit up to ~4 kHz


def test_measured_clash_cut_goes_to_the_lower_priority_layer():
    rows = [[{"band": 1000, "a": "indian_lead", "b": "bed", "frac": 0.6, "db": -20.0},
             {"band": 250, "a": "groove", "b": "bass", "frac": 0.4, "db": -25.0}]]
    cuts = eq.clash_cuts(rows)
    assert cuts[0]["bed"] == [(1000.0, -2.5)]            # lead owns 1 kHz, the bed is cut
    assert cuts[0]["bass"] == [(250.0, -2.5)]            # groove owns the low end, the bass is cut
    assert "indian_lead" not in cuts[0]


def test_masking_finder_detects_two_tones_in_one_band():
    t = np.arange(SR * 2) / SR
    a = 0.1 * np.sin(2 * np.pi * 1000.0 * t)   # 1 kHz tone
    b = 0.1 * np.sin(2 * np.pi * 1100.0 * t)   # 1.1 kHz tone: same 1/3-octave band
    c = 0.1 * np.sin(2 * np.pi * 8000.0 * t)   # far away: no clash with a
    levels = eq.section_band_levels({"bed": np.stack([a, a]), "chords": np.stack([b, b]),
                                     "hit": np.stack([c, c])}, [(0, len(t))])
    rows = eq.find_clashes(levels)[0]
    top = rows[0]
    assert {top["a"], top["b"]} == {"bed", "chords"}
    assert top["band"] == 1000 and top["frac"] > 0.9
    assert not any({r["a"], r["b"]} == {"bed", "hit"} and r["frac"] >= eq.SUSTAIN for r in rows)
    assert abs(top["db"] - (-23.0)) < 1.5      # 0.1 amplitude sine: about -23 dBFS mean-square per band


def test_masking_finder_ignores_quiet_layers():
    t = np.arange(SR) / SR
    loud = np.stack([0.1 * np.sin(2 * np.pi * 1000.0 * t)] * 2)
    quiet = loud * 1e-4                          # about -80 dB: below the floor
    rows = eq.find_clashes(eq.section_band_levels({"bed": loud, "chords": quiet}, [(0, SR)]))[0]
    assert all(r["frac"] < eq.SUSTAIN for r in rows)


def test_duck_only_while_key_is_active_and_depth_matches():
    total = SR * 4
    key = np.zeros(total)
    for k in range(4):                           # four kicks, one per beat at 60 BPM, in the span only
        key[SR // 4 + k * SR: SR // 4 + k * SR + 480] = 0.9
    spans = [(0, SR * 2, 60.0, 1)]               # active for the first two seconds only
    gr = eq.duck_gr_db(key, spans, depth_db=5.0, attack_ms=3.0, release_beats=0.5)
    assert abs(gr.max() - 5.0) < 0.1             # depth matches (peak of the span envelope)
    assert gr[SR * 2:].max() == 0.0              # nothing outside the span
    assert gr[SR * 2 - 10: SR * 2].max() < 5.0   # ramp into the span edge, no hard step
    silent = eq.duck_gr_db(np.zeros(total), spans, 5.0, 3.0, release_beats=0.5)
    assert silent.max() == 0.0                   # key inactive, no duck


def test_duck_has_no_steps_and_tracks_the_tempo():
    total = SR * 2
    key = np.zeros(total)
    key[1000:1480] = 0.9
    fast = eq.duck_gr_db(key, [(0, total, 176.0, 1)], 5.0, 3.0, release_beats=0.5)
    slow = eq.duck_gr_db(key, [(0, total, 60.0, 1)], 5.0, 3.0, release_beats=0.5)
    assert eq.max_step_db(fast) < 0.2 and eq.max_step_db(slow) < 0.2
    # the release follows the tempo: at 176 BPM the duck is gone sooner than at 60 BPM
    assert fast[1000 + SR // 4] < slow[1000 + SR // 4]


def test_event_dip_depth_and_timing():
    total = SR * 2
    gr = eq.event_dip_db(total, [SR // 2], depth_db=4.5, attack_ms=3.0, release_ms=180.0)
    assert gr[:SR // 2].max() == 0.0            # nothing before the hit
    assert abs(gr.max() - 4.5) < 0.1            # the dip reaches its depth
    assert gr[SR // 2] < 0.5                    # fast ramp in: starts from zero
    assert gr[SR // 2 + int(0.6 * SR)] < 0.2    # 180 ms release: about 0.16 dB left after 600 ms


def test_band_duck_only_touches_1_to_4_khz():
    t = np.arange(SR) / SR
    low = 0.3 * np.sin(2 * np.pi * 300.0 * t)
    mid = 0.3 * np.sin(2 * np.pi * 2000.0 * t)
    x = np.stack([low + mid] * 2)
    gr = np.full(SR, 2.5)
    y = eq.band_duck(x, gr, 1000.0, 4000.0)
    assert abs(_rms(y[0]) ** 2 - _rms(low) ** 2 - (_rms(mid) * 10 ** (-2.5 / 20)) ** 2) < 1e-3  # 300 Hz kept
    lo_only = eq.band_duck(np.stack([low] * 2), gr, 1000.0, 4000.0)
    assert abs(_rms(lo_only[0]) / _rms(low) - 1.0) < 0.02
    mid_only = eq.band_duck(np.stack([mid] * 2), gr, 1000.0, 4000.0)
    assert abs(20 * np.log10(_rms(mid_only[0]) / _rms(mid)) + 2.5) < 0.3


def test_role_and_hats_detection():
    assert eq.role_of("groove", "loop", "Kick loop.wav") == "kick"
    assert eq.role_of("groove", "pulse", "Closed hat 01.wav") == "hats"
    assert eq.role_of("indian_perc", "loop", "tabla.wav") == "perc"
    assert eq.role_of("indian_lead", "bed", "flute.wav") == "lead"
