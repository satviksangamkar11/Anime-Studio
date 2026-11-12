"""G2 / G13 / G14 / G22 wiring of build_final_reel: NO_SILENCE v2 on the real export and the mix, the SRT next to the export, YouTube
line mode, text-card QA from --ocr. Offline: ffmpeg/ffprobe are replaced by a fake subprocess, so no media tool runs."""
import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))

import build_final_reel as b  # noqa: E402
import test_build_final_reel_lock as L  # noqa: E402
import waivers as wv  # noqa: E402
from h3 import gate_d_audio as gd  # noqa: E402

R = 48000
CARD = [{"t0": 0.0, "t1": 2.0, "text": "ब्रह्मा"}]


def tone(sec, db=-20.0):
    t = np.arange(int(sec * R)) / R
    return np.tile((10 ** (db / 20) * np.sqrt(2) * np.sin(2 * np.pi * 220 * t))[:, None], (1, 2))


def setup(tmp_path, monkeypatch, master, fail_mux=False):
    """main() on reel 2, language hi, title-card captions. `master` is the array the fake decode writes."""
    pack, lock, story, clips, vo = L.full_setup(tmp_path)
    calls = []

    def fake_run(argv, **kw):
        calls.append(list(argv))
        if fail_mux and argv[0] == "mux":
            raise subprocess.CalledProcessError(1, argv)
        if "pcm_s16le" in argv:
            b.write_wav_pcm16(argv[-1], master, R)
        elif argv[0] == "mux":
            Path(argv[-1]).write_bytes(b"mp4")
        return subprocess.CompletedProcess(argv, 0, "", "")

    ok_loud = {"ok": True, "stats": {}, "errors": []}
    monkeypatch.setattr(b, "subprocess", SimpleNamespace(run=fake_run, CalledProcessError=subprocess.CalledProcessError))
    monkeypatch.setattr(b, "assemble_video", lambda *a, **k: {"total_frames": 432, "total_duration_sec": 18.0, "fps": 24})
    monkeypatch.setattr(b, "probe_size", lambda path: (768, 1344))
    monkeypatch.setattr(b, "master_audio_check", lambda *a, **k: ([], []))
    monkeypatch.setattr(b, "mux_argv", lambda rows, lg, vo_, video, export, *a, **k: (["mux", str(export)], 18.0))
    monkeypatch.setattr(b, "measure", lambda export: ok_loud)
    monkeypatch.setattr(b, "correct_loudness", lambda export, loud: ok_loud)
    monkeypatch.setattr(b, "check_free_disk", lambda *a, **k: None)
    monkeypatch.setattr(gd, "build_captions", lambda *a, **k: ("", []))
    monkeypatch.setattr(gd, "plan_language_outputs", lambda *a, **k: {
        "reports": {"hi": {"errors": [], "warnings": []}}, "languages": {"hi": {"captions": CARD}}})
    return pack, lock, story, clips, vo, calls


def run(tmp_path, monkeypatch, master, extra=(), **kw):
    pack, lock, story, clips, vo, calls = setup(tmp_path, monkeypatch, master, **kw)
    rc = L.run_main(tmp_path, pack, lock, story, clips, vo, extra=("--langs", "hi", "--title-cards", *extra))
    rep = json.loads((tmp_path / "out" / "kalika_reel2_build_report.json").read_text(encoding="utf-8")) if rc is not None else None
    return rc, rep, calls


def test_runs_on_export_not_premix(tmp_path, monkeypatch):
    rc, rep, calls = run(tmp_path, monkeypatch, tone(3))
    export = tmp_path / "out" / "export" / "kalika_reel2_hi_r1.mp4"
    decodes = [c for c in calls if "pcm_s16le" in c]
    assert rc == 0 and len(decodes) == 1
    assert decodes[0][decodes[0].index("-i") + 1] == str(export)         # the decoded file is the export, not <reel>_video.mp4
    assert rep["languages"]["hi"]["silence"]["ok"] is True


def test_silence_fail_blocks_language(tmp_path, monkeypatch):
    master = np.vstack([tone(1), np.zeros((int(0.06 * R), 2)), tone(1)])
    rc, rep, _ = run(tmp_path, monkeypatch, master)
    exp = tmp_path / "out" / "export"
    entry = rep["languages"]["hi"]
    assert rc == 1
    assert "DIGITAL_SILENCE" in [e["code"] for e in entry["blocking_errors"]]
    assert (exp / "kalika_reel2_hi_r1_REJECTED.mp4").is_file() and not (exp / "kalika_reel2_hi_r1.mp4").exists()
    assert list(exp.glob("*.srt")) == []


def test_srt_named_like_export(tmp_path, monkeypatch):
    rc, rep, _ = run(tmp_path, monkeypatch, tone(3))
    srt = tmp_path / "out" / "export" / "kalika_reel2_hi_r1.srt"
    raw = srt.read_bytes()
    assert rc == 0 and rep["languages"]["hi"]["srt_path"] == str(srt)
    assert not raw.startswith(b"\xef\xbb\xbf") and b"\r" not in raw
    assert raw.decode("utf-8") == "1\n00:00:00,000 --> 00:00:02,000\nब्रह्मा\n\n"
    assert rep["languages"]["hi"]["srt_sha256"]


def test_srt_not_written_when_export_fails(tmp_path, monkeypatch):
    with pytest.raises(subprocess.CalledProcessError):
        run(tmp_path, monkeypatch, tone(3), fail_mux=True)
    assert list((tmp_path / "out" / "export").glob("*.srt")) == []


def test_text_card_qa_runs_when_ocr_given(tmp_path, monkeypatch):
    ocr = tmp_path / "ocr.json"
    ocr.write_text(json.dumps([{"lang": "hi", "expected_text": "ब्रह्मा",
                                "items": [{"text": "ब्रम्हा", "box": [10, 300, 900, 1300]}]}], ensure_ascii=False), encoding="utf-8")
    rc, rep, calls = run(tmp_path, monkeypatch, tone(3), extra=("--ocr", str(ocr)))
    entry = rep["languages"]["hi"]
    assert rc == 1 and entry["text_card_qa"]["ok"] is False
    assert [e["code"] for e in entry["blocking_errors"]] == ["TEXT_CARD_QA"]
    assert not [c for c in calls if c[0] == "mux"]                       # blocked before the export


def test_no_ocr_no_text_card_qa(tmp_path, monkeypatch):
    rc, rep, _ = run(tmp_path, monkeypatch, tone(3))
    assert rc == 0 and "text_card_qa" not in rep["languages"]["hi"]


def test_intake_runs_silence_rule_on_the_mix(tmp_path):
    mix, voice = tmp_path / "mix.wav", tmp_path / "voice.wav"
    loud = np.vstack([tone(1), np.zeros((int(0.06 * R), 2)), tone(1)])
    b.write_wav_pcm16(mix, loud, R)
    b.write_wav_pcm16(voice, loud * 0.9, R)
    rows = [{"offset_sec": 0.0, "lines": [{"start": 0.0, "end": 0.9}]}]
    with pytest.raises(SystemExit, match="DIGITAL_SILENCE"):
        b.intake(mix, voice, 49, rows, work_dir=tmp_path / "w")


def test_critical_codes_not_waivable():
    assert {"DIGITAL_SILENCE", "DROPOUT", "CHANNEL_DROP"} <= wv.CRITICAL_CODES
    assert "DEAD_AIR" not in wv.CRITICAL_CODES


def test_waiver_for_dropout_is_refused(tmp_path):
    scoped = {"waivers": [{"waiver_id": "W-D", "scope": "reel", "story_id": "pack", "reel_id": "kalika_reel2",
                           "codes": ["DROPOUT", "DEAD_AIR"], "status": "approved", "owner": "Satvik",
                           "approved_by": "Reviewer", "approved_at": "2026-11-12T10:00:00"}]}
    (tmp_path / "waivers.json").write_text(json.dumps(scoped), encoding="utf-8")
    records, problems = b.load_waivers(tmp_path, "kalika_reel2")
    assert [sorted(r["codes"]) for r in records] == [["DEAD_AIR"]]
    assert any("DROPOUT" in why for _, why in problems)


# ---- G14: YouTube line mode

LINES = [("पहली पंक्ति है। दूसरी पंक्ति थोड़ी लंबी है जो दो लाइनों में बँटेगी ज़रूर, क्योंकि यह बहुत ही लंबी हो गई है।", 2.0, 8.0),
         ("ब्रह्मा ने कहा।", 8.0, 10.0)]


def test_srt_line_mode_max_42_chars_2_lines():
    cues = b.srt_line_cues(LINES)
    assert len(cues) >= 4
    for c in cues:
        rows = c["text"].split("\n")
        assert 1 <= len(rows) <= 2 and all(len(r) <= 42 for r in rows)


def test_srt_times_equal_voice_report():
    cues = b.srt_line_cues(LINES)
    assert cues[0]["t0"] == 2.0 and cues[-1]["t1"] == 10.0
    assert [c["t1"] for c in cues if c["text"].endswith("ब्रह्मा ने कहा।")] == [10.0]
    for a, nxt in zip(cues, cues[1:]):
        assert a["t1"] <= nxt["t0"] + 1e-9 and a["t0"] < a["t1"]


def test_srt_devanagari_conjunct_roundtrips(tmp_path):
    cues = b.srt_line_cues([("ब्रह्मा ने कहा क्या दक्ष आया।", 0.0, 3.0)])
    path = tmp_path / "x.srt"
    b.write_srt(cues, path)
    text = path.read_text(encoding="utf-8")
    assert "ब्रह्मा" in text and "क्या" in text and "दक्ष" in text


def test_short_cue_stretched_to_one_second_without_overlap():
    cues = b.srt_line_cues([("एक।", 0.0, 0.4), ("दो।", 3.0, 4.0)])
    assert cues[0]["t1"] == 1.0 and cues[1]["t0"] == 3.0
