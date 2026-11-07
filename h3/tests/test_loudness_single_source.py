"""One loudness standard (owner 2026-11-07): -16 LUFS integrated, max true peak -1 dBTP, read from core/core.json."""
from core.style_pack import load_core
from h3 import assemble_reel, gate_d_audio as gd
from h3.shot_table_spec import LOUDNESS


def test_every_stage_reads_the_core_json_target():
    a = load_core()["delivery"]["audio"]
    assert (a["lufs"], a["true_peak_db"]) == (-16.0, -1.0)
    assert LOUDNESS == {"target_lufs": a["lufs"], "tolerance": a["tolerance_lu"], "loudnorm_tp": a["loudnorm_tp_db"],
                        "tp_ceiling_dbtp": a["true_peak_db"], "lra": a["lra"]}
    assert (assemble_reel.TARGET_LUFS, assemble_reel.TRUE_PEAK_DB) == (a["lufs"], a["true_peak_db"])
    assert a["loudnorm_tp_db"] < a["true_peak_db"]                  # the filter aims below the ceiling that Gate D checks


def test_gate_d_mix_and_check_use_the_same_target():
    mix = gd.build_mix_filter([{"input_index": 0, "trim_in_sec": 0.0, "trim_out_sec": 5.0}], 1, None, 5.0)
    assert "loudnorm=I=-16:TP=-1.3:LRA=11[master]" in mix
    at_target = "Input Integrated:    -16.02 LUFS\nInput True Peak:    -1.00 dBTP\n"
    assert gd.check_post_aac_loudness(at_target)["ok"]
    old_target = "Input Integrated:    -14.02 LUFS\nInput True Peak:    -1.50 dBTP\n"       # the retired -14 LUFS profile
    assert [e["code"] for e in gd.check_post_aac_loudness(old_target)["errors"]] == ["LOUDNESS_OUT_OF_TARGET"]
