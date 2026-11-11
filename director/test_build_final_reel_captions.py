"""Tests for X-16: spoken captions from the voice manifest plus caption_fields (no CAPTION_FIXES), and the 768x1344 -> 1080x1920
delivery crop that runs before the ass burn (rule 51). Offline except test_export_probes_1080x1920, which runs local ffmpeg on a
synthetic lavfi source (no model call, no network)."""
import hashlib
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import build_final_reel as b  # noqa: E402
from h3 import gate_d_audio as gd  # noqa: E402

FONTS = HERE.parent / "styles" / "fonts"


def sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def line_row(sid, text, caption=None, approved=None):
    """A shots.json row with one Hindi dialogue line, optionally with the owner's caption keys."""
    d = {"text": text}
    if caption is not None:
        d["caption_text"] = caption
    if approved is not None:
        d["caption_diff_approved"] = approved
    return {"id": sid, "editorial_duration_sec": 6.0,
            "audio_and_dialogue_track": {"narration_by_lang": {}, "dialogue_by_lang": {"hi": [d]}}}


def report_for(sid, line_id):
    return [{"shot": sid, "lang": "hi", "lines": [{"id": line_id, "start": 0.5, "end": 5.5}]}]


def manifest_for(line_id, text, lang="hi", sha_text=None):
    return [{"id": f"{line_id}.{lang}", "text": text, "text_sha256": sha(sha_text if sha_text is not None else text)}]


def test_no_caption_fixes_symbol():
    assert not hasattr(b, "CAPTION_FIXES")
    assert "for _fix in" not in (HERE / "build_final_reel.py").read_text(encoding="utf-8")   # the loop is gone too


def test_unapproved_caption_diff_raises():
    spoken, caption = "गलती हुई", "ग़लती हुई"
    rw = [line_row("SHOT-010", spoken, caption, approved=False)]
    with pytest.raises(SystemExit, match="not approved"):
        b.spoken_cues_real(rw, report_for("SHOT-010", "SHOT-010-D1"), "hi", manifest_for("SHOT-010-D1", spoken))


def test_approved_diff_used():
    spoken, caption = "गलती हुई", "ग़लती हुई"
    rw = [line_row("SHOT-010", spoken, caption, approved=True)]
    cues = b.spoken_cues_real(rw, report_for("SHOT-010", "SHOT-010-D1"), "hi", manifest_for("SHOT-010-D1", spoken))
    words = [w["text"] for c in cues for w in c["words"]]
    assert words == ["ग़लती", "हुई"]                                  # the approved caption is shown, same word count as the spoken line


def test_manifest_text_is_the_spoken_text_not_shots_text():
    rw = [line_row("SHOT-004", "शब्द ए")]                            # shots.json text differs from the manifest on purpose
    cues = b.spoken_cues_real(rw, report_for("SHOT-004", "SHOT-004-D1"), "hi", manifest_for("SHOT-004-D1", "शब्द बी"))
    assert [w["text"] for c in cues for w in c["words"]] == ["शब्द", "बी"]


def test_manifest_sha_mismatch_raises():
    rw = [line_row("SHOT-004", "शब्द बी")]
    man = manifest_for("SHOT-004-D1", "शब्द बी", sha_text="कुछ और")
    with pytest.raises(SystemExit, match="text_sha256"):
        b.spoken_cues_real(rw, report_for("SHOT-004", "SHOT-004-D1"), "hi", man)


def test_missing_manifest_row_raises():
    rw = [line_row("SHOT-004", "शब्द बी")]
    with pytest.raises(SystemExit, match="no row in the voice manifest"):
        b.spoken_cues_real(rw, report_for("SHOT-004", "SHOT-004-D1"), "hi", [])


def test_manifest_duplicate_ids_raise():
    with pytest.raises(SystemExit, match="duplicate"):
        b.manifest_by_id(manifest_for("SHOT-004-D1", "a") + manifest_for("SHOT-004-D1", "a"))


def _rows():
    return [{"id": "SHOT-001", "editorial_duration_sec": 6.0, "offset_sec": 0.0},
            {"id": "SHOT-002", "editorial_duration_sec": 5.0, "offset_sec": 6.0}]


def test_crop_before_ass_in_argv(tmp_path):
    argv, _ = b.mux_argv(_rows(), "hi", tmp_path, tmp_path / "v.mp4", tmp_path / "o.mp4", tmp_path / "c.ass", "styles/fonts",
                         pre_vf=b.DELIVERY_VF)
    graph = argv[argv.index("-filter_complex") + 1]
    assert "[0:v]scale=1098:1920:flags=lanczos,crop=1080:1920:9:0,ass=filename=" in graph   # crop first, then the burn
    assert graph.index("crop=1080:1920:9:0") < graph.index("ass=filename=")


def test_delivery_crop_hand_check():
    assert 768 * 1920 / 1344 > 1097 and 1098 % 2 == 0                                    # 1097.14 -> even 1098
    assert (1098 - 1080) // 2 == 9
    assert b.DELIVERY_VF == "scale=1098:1920:flags=lanczos,crop=1080:1920:9:0"


@pytest.mark.parametrize("size,expected", [((768, 1344), b.DELIVERY_VF), ((1080, 1920), None)])
def test_delivery_vf_by_source_size(size, expected):
    assert b.delivery_vf(size) == expected


def test_other_source_size_stops_the_build():
    with pytest.raises(SystemExit, match="640x480"):
        b.delivery_vf((640, 480))


def test_gate_d_default_unchanged():
    graph_default = gd.build_final_mux_argv("v.mp4", ["a.wav"], "[1:a]anull[master]", "o.mp4", ass_path="c.ass",
                                            fonts_dir="styles/fonts")
    graph = graph_default[graph_default.index("-filter_complex") + 1]
    assert graph == "[1:a]anull[master];[0:v]ass=filename=c.ass:fontsdir=styles/fonts:shaping=complex[vsub]"
    with pytest.raises(ValueError, match="burn_captions=True"):
        gd.build_final_mux_argv("v.mp4", ["a.wav"], "[1:a]anull[master]", "o.mp4", burn_captions=False, pre_vf=b.DELIVERY_VF)


@pytest.mark.skipif(not (shutil.which("ffmpeg") and shutil.which("ffprobe")), reason="needs local ffmpeg and ffprobe")
def test_export_probes_1080x1920(tmp_path):
    video = tmp_path / "v.mp4"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "testsrc=size=768x1344:rate=24:duration=2",
                    "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000", "-t", "2", "-c:v", "libx264", "-pix_fmt", "yuv420p",
                    "-c:a", "aac", str(video)], check=True)
    ass = tmp_path / "c.ass"
    ass.write_text(b.caption_ass(b.word_cues("At dawn", 0.0, 2.0, "en"), "en", FONTS), encoding="utf-8")
    export = tmp_path / "e.mp4"
    rows = [{"id": "SHOT-001", "editorial_duration_sec": 2.0, "offset_sec": 0.0}]
    argv, _ = b.mux_argv(rows, "en", tmp_path, video, export, ass, str(FONTS), pre_vf=b.delivery_vf(b.probe_size(video)))
    subprocess.run(argv, check=True, cwd=str(HERE.parent))
    assert b.probe_size(export) == (1080, 1920)
