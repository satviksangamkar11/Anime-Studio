"""M-34 (voice_rest / silence_ok reach the lock rows and the silence rule) and G15 (clean export is the default)."""
import hashlib
import json
import shutil
import subprocess

import numpy as np
import pytest

import build_final_reel as b
import timeline_lock_io as lio
import write_timeline_lock as wtl
from h3 import silence_rule as sr
from test_write_timeline_lock import FREE_NATURAL, _free_rows, _pack, _secs

R = 48000


def tone(sec, rms_db):
    t = np.arange(int(round(sec * R))) / R
    return np.tile(((10 ** (rms_db / 20) * np.sqrt(2)) * np.sin(2 * np.pi * 220 * t))[:, None], (1, 2))


def _lock(tmp_path, rows):
    pack, root, manifest = _pack(tmp_path, rows, FREE_NATURAL)
    lock_rows = wtl.plan_lock(rows, _secs(root), ["en", "hi"], None, {})
    target = wtl.write_version(tmp_path / "lock", lock_rows, [pack / "shots.json", manifest], {"fps": 24})
    return pack, target


def test_sheet_entry_and_overlay_carry_the_windows():
    sheet = {"voice_rest": [0.5, 2.0], "silence_ok": [0.5, 1.9], "writer_seconds": 3.0}
    entry = wtl.sheet_entry(sheet, _free_rows()[1], ["en", "hi"])
    assert entry["voice_rest"] == [0.5, 2.0] and entry["silence_ok"] == [0.5, 1.9]
    row = wtl._overlay({"id": "S1"}, entry, {})
    assert row["voice_rest"] == [0.5, 2.0] and row["silence_ok"] == [0.5, 1.9]


def test_sheet_without_windows_adds_no_keys():
    entry = wtl.sheet_entry({"writer_seconds": 3.0}, _free_rows()[1], ["en", "hi"])
    assert "voice_rest" not in entry and "silence_ok" not in entry


def test_lock_rows_hold_the_windows_and_older_locks_still_verify(tmp_path):
    rows = _free_rows()
    rows[1]["voice_rest"], rows[1]["silence_ok"] = [0.5, 2.0], [0.5, 1.9]
    (tmp_path / "new").mkdir()
    (tmp_path / "old").mkdir()
    pack, target = _lock(tmp_path / "new", rows)
    shots = {s["id"]: s for s in lio.load_lock(target)["shots"]}
    assert shots["S1"]["voice_rest"] == [0.5, 2.0] and shots["S1"]["silence_ok"] == [0.5, 1.9]
    assert "voice_rest" not in shots["S0"]
    old_pack, old_target = _lock(tmp_path / "old", _free_rows())          # no windows anywhere
    lock = lio.verify_lock(old_target, lio.load_lock(old_target)["inputs"], lio.load_lock(old_target)["params"])
    assert lock["shots"]
    assert b.rest_windows(b.lock_rows_for_pack(old_target, old_pack)) == ([], [])


def test_silence_ok_window_exempts_a_quiet_span_end_to_end(tmp_path):
    rows = _free_rows()
    rows[1]["silence_ok"] = [0.5, 1.9]                                   # shot-relative, 1.4 s
    pack, target = _lock(tmp_path, rows)
    lrows = b.lock_rows_for_pack(target, pack)
    rest, ok = b.rest_windows(lrows)
    off = 80 / 24
    assert rest == [] and ok == [(pytest.approx(off + 0.5), pytest.approx(off + 1.9))]
    x = np.vstack([tone(off + 0.5, -20), tone(1.4, -65), tone(3.0, -20)])
    assert "DEAD_AIR" in [e["code"] for e in sr.check_array(x, R)["errors"]]        # no window: fails
    assert sr.check_array(x, R, rest, ok)["ok"]                                      # window from the lock: passes


def test_voice_rest_window_exempts_quiet_warning(tmp_path):
    rows = _free_rows()
    rows[1]["voice_rest"] = [0.5, 1.5]
    pack, target = _lock(tmp_path, rows)
    rest, ok = b.rest_windows(b.lock_rows_for_pack(target, pack))
    off = 80 / 24
    x = np.vstack([tone(off + 0.5, -20), tone(1.0, -55), tone(3.0, -20)])
    assert "QUIET" in [w["code"] for w in sr.check_array(x, R)["warnings"]]
    assert "QUIET" not in [w["code"] for w in sr.check_array(x, R, rest, ok)["warnings"]]


# ---- G15
PRE = "scale=1098:1920:flags=lanczos,crop=1080:1920"


def _burned_argv(pre):
    gd = b.gd
    mix = "[0:a]anull[master]"
    return gd.build_final_mux_argv("v.mp4", ["a.wav"], mix, "out.mp4", burn_captions=True, ass_path="c.ass", fonts_dir="f", pre_vf=pre)


def test_clean_export_has_no_subtitle_filter():
    burned = _burned_argv(PRE)
    assert "ass=filename" in " ".join(burned)
    clean = b.clean_argv(burned, PRE)
    text = " ".join(clean)
    assert "ass=" not in text and "subtitles" not in text
    graph = clean[clean.index("-filter_complex") + 1]
    assert graph.endswith(f";[0:v]{PRE}[vsub]")
    assert graph.startswith("[0:a]anull[master]")


def test_clean_argv_without_crop_uses_null():
    clean = b.clean_argv(_burned_argv(None), None)
    assert clean[clean.index("-filter_complex") + 1].endswith(";[0:v]null[vsub]")


def test_clean_keeps_audio_args_and_video_codec_identical():
    burned = _burned_argv(PRE)
    clean = b.clean_argv(burned, PRE)
    i, j = burned.index("-filter_complex"), clean.index("-filter_complex")
    assert burned[:i] == clean[:j] and burned[i + 2:] == clean[j + 2:]


def test_burned_is_made_only_from_the_flag_and_copies_audio():
    assert b.build_arg_parser().parse_args(
        ["--pack", "p", "--story", "s", "--clips", "c", "--vo", "v", "--lock", "l", "--out", "o", "--reel", "r"]
    ).burned_captions is False
    assert b.build_arg_parser().parse_args(
        ["--pack", "p", "--story", "s", "--clips", "c", "--vo", "v", "--lock", "l", "--out", "o", "--reel", "r",
         "--burned-captions"]).burned_captions is True
    argv = b.burned_from_clean_argv("clean.mp4", "burned.mp4", "c.ass", "fonts")
    assert argv[argv.index("-c:a") + 1] == "copy" and "ass=filename" in argv[argv.index("-vf") + 1]


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="needs ffmpeg")
def test_burned_audio_sha_equals_clean(tmp_path):
    clean, burned = tmp_path / "clean.mp4", tmp_path / "burned.mp4"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "color=c=black:s=128x224:d=1:r=24",
                    "-f", "lavfi", "-i", "sine=f=440:d=1", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac",
                    str(clean)], check=True)
    ass = tmp_path / "c.ass"
    ass.write_text("[Script Info]\nScriptType: v4.00+\nPlayResX: 128\nPlayResY: 224\n\n[V4+ Styles]\n"
                   "Format: Name, Fontname, Fontsize, PrimaryColour, Alignment\nStyle: Default,Arial,20,&H00FFFFFF,5\n\n"
                   "[Events]\nFormat: Layer, Start, End, Style, Text\nDialogue: 0,0:00:00.00,0:00:01.00,Default,hi\n",
                   encoding="utf-8")
    subprocess.run(b.burned_from_clean_argv(clean, burned, ass.name, "."), check=True, cwd=str(tmp_path))
    assert b.audio_sha256(clean) == b.audio_sha256(burned)
    assert hashlib.sha256(clean.read_bytes()).hexdigest() != hashlib.sha256(burned.read_bytes()).hexdigest()


def test_preset_is_passed_to_plan_shots(tmp_path, monkeypatch):
    seen = []
    real = wtl.core.plan_shots
    monkeypatch.setattr(wtl.core, "plan_shots", lambda *a, **k: (seen.append(k.get("preset")), real(*a, **k))[1])
    pack, root, manifest = _pack(tmp_path, _free_rows(), FREE_NATURAL)
    wtl.plan_lock(_free_rows(), _secs(root), ["en", "hi"], None, {})
    with pytest.raises(SystemExit):          # 80-frame edits do not fit the 124-frame floor (W2-B finding)
        wtl.plan_lock(_free_rows(), _secs(root), ["en", "hi"], None, {}, preset="pika")
    assert seen == [None, "pika"]
    assert wtl.main(["--pack", str(pack), "--wav-root", str(root), "--manifest", str(manifest), "--out-dir",
                     str(tmp_path / "o"), "--langs", "en,hi"]) == 0
    assert "preset" not in lio.load_lock(tmp_path / "o" / "timeline_lock_v1.json")["params"]
