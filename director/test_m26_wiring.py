"""M-26 wiring tests: master audio gate in build_final_reel, QA inputs (route and chain_prev) in run_colab_batch,
render gate (render_allowed + record_drift_step) in run_colab_batch. Offline; ffmpeg only for the 0.5 s silence master."""
import json
import random
import shutil
import subprocess
import sys
import wave
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))

import build_final_reel as b  # noqa: E402
import run_colab_batch as rcb  # noqa: E402
from h3 import fallback_policy as fp  # noqa: E402
from h3 import gate_d_audio as gd  # noqa: E402

HAS_FFMPEG = shutil.which("ffmpeg") is not None


def write_wav(path, samples, rate=48000):
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(b"".join(int(v).to_bytes(2, "little", signed=True) for v in samples))
    return path


def test_master_wav_argv_decodes_video_only_pcm_48k_stereo(tmp_path):
    argv = b.master_wav_argv(tmp_path / "v.mp4", tmp_path / "master.wav")
    assert argv[0] == "ffmpeg"
    assert "-vn" in argv
    assert argv[argv.index("-ar") + 1] == "48000"
    assert argv[argv.index("-ac") + 1] == "2"
    assert argv[argv.index("-c:a") + 1] == "pcm_s16le"
    assert argv[-1] == str(tmp_path / "master.wav")


def test_premix_quiet_is_warning_only(tmp_path):
    # G2: the pre-mix clip audio is never a defect; 0.5 s of digital zero is only a CLIP_AUDIO_QUIET warning
    wav = write_wav(tmp_path / "silence.wav", [0] * 24000)
    errors, warnings = b.audio_gate_from_wav(wav)
    assert errors == []
    assert warnings and all(w.startswith("CLIP_AUDIO_QUIET") for w in warnings)


def test_low_noise_bed_master_passes(tmp_path):
    rng = random.Random(7)
    samples = [rng.randint(-500, 500) for _ in range(48000)]          # RMS about -41 dBFS: above the -50 dBFS floor, never quiet
    wav = write_wav(tmp_path / "bed.wav", samples)
    errors, _ = b.audio_gate_from_wav(wav)
    assert errors == []


def test_lra_above_11_warns_but_does_not_fail():
    assert b.lra_warnings(12.5) and "LRA" in b.lra_warnings(12.5)[0]
    assert b.lra_warnings(11.0) == []
    assert b.lra_warnings(None) == []


@pytest.mark.skipif(not HAS_FFMPEG, reason="ffmpeg not on PATH")
def test_decoded_half_second_silence_is_a_clip_warning(tmp_path):
    src = tmp_path / "silent.m4a"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo", "-t", "0.5",
                    "-c:a", "aac", str(src)], check=True)
    errors, warnings = b.master_audio_check(src, tmp_path / "work")
    assert errors == [] and any("CLIP_AUDIO_QUIET" in w for w in warnings)


def test_qa_route_maps_start_only_to_S_and_skips_the_end_frame(tmp_path):
    routes = {"routes": {"SHOT-001": {"route": "REF_S"}, "SHOT-002": {"route": "SE"}}}
    qa = rcb.qa_inputs("SHOT-001", {}, routes, tmp_path)
    assert qa == {"route": "S", "chain_prev": None}
    assert rcb.qa_inputs("SHOT-002", {}, routes, tmp_path)["route"] == "SE"


def test_qa_unknown_route_is_refused(tmp_path):
    with pytest.raises(ValueError, match="route"):
        rcb.qa_inputs("SHOT-001", {}, {"routes": {"SHOT-001": {"route": "POST"}}}, tmp_path)


def test_chained_clip_gets_the_saved_previous_png(tmp_path):
    png = tmp_path / "chain" / "SHOT-001-last.png"
    png.parent.mkdir(parents=True)
    png.write_bytes(b"png")
    routes = {"routes": {"SHOT-002": {"route": "S"}}}
    qa = rcb.qa_inputs("SHOT-002", {"chain_from": "SHOT-001"}, routes, tmp_path)
    assert qa["chain_prev"] == png


def test_chained_clip_without_its_saved_png_is_refused(tmp_path):
    routes = {"routes": {"SHOT-002": {"route": "S"}}}
    with pytest.raises(ValueError, match="chain"):
        rcb.qa_inputs("SHOT-002", {"chain_from": "SHOT-001"}, routes, tmp_path)


def _history(counts):
    return {"schema": fp.HISTORY_SCHEMA, "shots": {sid: [{"n": i} for i in range(n)] for sid, n in counts.items()}}


def test_fourth_render_of_a_shot_is_refused_without_owner_flag():
    problems, _ = rcb.render_gate(_history({"SHOT-001": 3}), ["SHOT-001"], drift_step="simplify")
    assert problems and "escalate" in problems[0]


def test_fourth_render_passes_with_owner_flag_and_drift_step():
    problems, log = rcb.render_gate(_history({"SHOT-001": 3}), ["SHOT-001"], owner_flag=True, drift_step="simplify")
    assert problems == []
    assert log == {"SHOT-001": ["simplify"]}


def test_re_render_needs_a_drift_step():
    problems, _ = rcb.render_gate(_history({"SHOT-001": 1}), ["SHOT-001"])
    assert problems and "drift" in problems[0]


def test_drift_steps_must_follow_the_order():
    problems, _ = rcb.render_gate(_history({"SHOT-001": 1}), ["SHOT-001"], drift_log={"SHOT-001": ["move_b_closer"]},
                                  drift_step="simplify")
    assert problems and "out of order" in problems[0]


def test_first_render_needs_no_drift_step():
    problems, log = rcb.render_gate(_history({}), ["SHOT-001", "SHOT-002"])
    assert problems == [] and log == {}
