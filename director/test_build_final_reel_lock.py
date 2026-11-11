"""Offline tests for the X-15 assembly rules of build_final_reel: required --reel, the closed reel 1, the timeline lock as the only
timing source, no silent fallbacks, waivers.json, and the clip_qa.json gate. No ffmpeg and no model call: every failure is raised
before the first ffmpeg command."""
import hashlib
import json
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import build_final_reel as b  # noqa: E402
import timeline_lock_io as tli  # noqa: E402
import waivers as wv  # noqa: E402
from h3 import gate_d_audio as gd  # noqa: E402

# Three shots of 7, 5 and 6 seconds at 24 fps: offsets 0.0, 7.0, 12.0. pixel_frames obey the lock rule (107..345, (p-5) % 17 == 0).
SHOTS = [("SHOT-001", 168, 175), ("SHOT-002", 120, 124), ("SHOT-003", 144, 158)]


def pack_rows(lines=None):
    """shots.json rows (a list). lines maps shot id -> hi narration text, for the rows that have a spoken line."""
    lines = lines or {}
    rows = []
    for sid, frames, _ in SHOTS:
        hi = lines.get(sid)
        rows.append({"id": sid, "editorial_duration_sec": frames / 24,
                     "audio_and_dialogue_track": {"narration_by_lang": {"hi": {"text": hi}} if hi else {}, "dialogue_by_lang": {}}})
    return rows


def write_pack(tmp_path, lines=None):
    pack = tmp_path / "pack"
    pack.mkdir()
    (pack / "shots.json").write_text(json.dumps(pack_rows(lines), ensure_ascii=False), encoding="utf-8")
    return pack


def write_lock_for(tmp_path, pack):
    """A real version 2 lock over the pack's shots.json (write_lock checks every field)."""
    shots, start = [], 0
    for sid, frames, pixel in SHOTS:
        shots.append({"id": sid, "edit_frames": frames, "start_frame": start, "pixel_frames": pixel,
                      "trim_in_frame": 0, "trim_out_frame": frames, "end_frame_position": frames - 1, "error_ms": 5.0})
        start += frames
    lock_path = tmp_path / "timeline_lock_v1.json"
    tli.write_lock(lock_path, shots, [pack / "shots.json"], {"source": "test"}, fps=24)
    return lock_path


def write_story(tmp_path):
    story = {"episodes": [{"shots": [{"shot_id": sid, "timing_and_lattice": {"trim_in_frame": 0, "trim_out_frame": frames}}
                                     for sid, frames, _ in SHOTS]}]}
    path = tmp_path / "story.json"
    path.write_text(json.dumps(story), encoding="utf-8")
    return path


def write_clip(tmp_path, sid, verdict_pass=True, owner_accept=None, reasons=()):
    """A clip in its shot folder with a clip_qa.json that matches it (X-14 contract)."""
    folder = tmp_path / "clips" / sid
    folder.mkdir(parents=True, exist_ok=True)
    clip = folder / f"{sid}.mp4"
    clip.write_bytes(b"clip bytes " + sid.encode())
    qa = {"clip_sha256": hashlib.sha256(clip.read_bytes()).hexdigest(), "window": [0, 1],
          "results": {}, "verdict": {"pass": verdict_pass, "reasons": list(reasons), "accepted": []},
          "sfx_keep": [], "bed_db": None, "owner_accept": owner_accept}
    (folder / "clip_qa.json").write_text(json.dumps(qa), encoding="utf-8")
    return clip


def write_clips_map(tmp_path, **kw):
    clips = {sid: str(write_clip(tmp_path, sid, **kw)) for sid, _, _ in SHOTS}
    path = tmp_path / "clips.json"
    path.write_text(json.dumps(clips), encoding="utf-8")
    return path


def full_setup(tmp_path, lines=None, **clip_kw):
    pack = write_pack(tmp_path, lines)
    lock = write_lock_for(tmp_path, pack)
    story = write_story(tmp_path)
    clips = write_clips_map(tmp_path, **clip_kw)
    vo = tmp_path / "vo"
    vo.mkdir()
    return pack, lock, story, clips, vo


def run_main(tmp_path, pack, lock, story, clips, vo, reel="kalika_reel2", extra=()):
    argv = ["--pack", str(pack), "--story", str(story), "--clips", str(clips), "--vo", str(vo), "--lock", str(lock),
            "--out", str(tmp_path / "out"), "--reel", reel, *extra]
    return b.main(argv)


def test_reel_required():
    parser = b.build_arg_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["--pack", "p", "--story", "s", "--clips", "c", "--vo", "v", "--lock", "l", "--out", "o"])


def test_reel_name_must_match_the_pattern(capsys):
    base = ["--pack", "p", "--story", "s", "--clips", "c", "--vo", "v", "--lock", "l", "--out", "o"]
    with pytest.raises(SystemExit):
        b.build_arg_parser().parse_args([*base, "--reel", "Kalika Reel 2"])
    assert "must match [a-z0-9_]+" in capsys.readouterr().err
    assert b.build_arg_parser().parse_args([*base, "--reel", "kalika_reel2"]).reel == "kalika_reel2"


def test_reel1_refused(tmp_path):
    pack, lock, story, clips, vo = full_setup(tmp_path)
    with pytest.raises(SystemExit, match="closed"):
        run_main(tmp_path, pack, lock, story, clips, vo, reel="kalika_reel1")


def test_offsets_from_lock(tmp_path, monkeypatch):
    pack = write_pack(tmp_path)
    lock = write_lock_for(tmp_path, pack)
    rows = b.lock_rows_for_pack(lock, pack)
    assert [r["offset_sec"] for r in rows] == [0.0, 7.0, 12.0]
    seen = {}

    def spy(sfx, vo_input, bgm, total):
        seen["sfx"], seen["total"] = sfx, total
        return "[master]"
    monkeypatch.setattr(gd, "build_mix_filter", spy)
    vo_dir = tmp_path / "vo"
    vo_dir.mkdir()
    argv, total = b.mux_argv(rows, "hi", vo_dir, tmp_path / "v.mp4", tmp_path / "o.mp4", tmp_path / "c.ass", "styles/fonts")
    assert [s["trim_in_sec"] for s in seen["sfx"]] == [0.0, 7.0, 12.0]
    assert [s["trim_out_sec"] for s in seen["sfx"]] == [7.0, 12.0, 18.0]
    assert total == 18.0 and argv[0] == "ffmpeg"
    # the lock's offset_sec is the clock, not a running sum of durations: a lock offset of 7.5 must reach the mix as 7.5
    shifted = [dict(r) for r in rows]
    shifted[1]["offset_sec"] = 7.5
    b.mux_argv(shifted, "hi", vo_dir, tmp_path / "v.mp4", tmp_path / "o.mp4", tmp_path / "c.ass", "styles/fonts")
    assert [s["trim_in_sec"] for s in seen["sfx"]] == [0.0, 7.5, 12.0]
    assert [s["trim_out_sec"] for s in seen["sfx"]] == [7.0, 12.5, 18.0]


def test_missing_vo_with_lines_raises(tmp_path):
    pack = write_pack(tmp_path, lines={"SHOT-002": "नमस्ते"})
    rows = b.lock_rows_for_pack(write_lock_for(tmp_path, pack), pack)
    vo_dir = tmp_path / "vo"
    (vo_dir / "hi").mkdir(parents=True)                       # no SHOT-002.wav: that shot has a line
    with pytest.raises(SystemExit, match="SHOT-002"):
        b.mux_argv(rows, "hi", vo_dir, tmp_path / "v.mp4", tmp_path / "o.mp4", tmp_path / "c.ass", "styles/fonts")


def test_missing_report_raises(tmp_path):
    pack, lock, story, clips, vo = full_setup(tmp_path)           # no vo_tracks_report.json in vo
    with pytest.raises(SystemExit, match="vo_tracks_report"):
        run_main(tmp_path, pack, lock, story, clips, vo)


class Reached(Exception):
    """Raised by the stubbed mux: the build got past the gate for that language."""


def dead_air_run(tmp_path, monkeypatch, waivers_text=None):
    """main() on reel 2 with a stubbed cut and gate: the gate reports DEAD_AIR_PAUSE for hi. No ffmpeg runs. A build that gets
    past the gate reaches the stubbed mux_argv and raises Reached."""
    pack, lock, story, clips, vo = full_setup(tmp_path)
    (vo / "vo_tracks_report.json").write_text("[]", encoding="utf-8")
    import voice_manifest as vm                                   # D-VOICE: the manifest is a voice_manifest/1 file, empty here
    manifest = vm.write_manifest(tmp_path, "hi", [])
    if waivers_text is not None:
        (pack / "waivers.json").write_text(waivers_text, encoding="utf-8")
    gate_report = {"errors": [{"code": "DEAD_AIR_PAUSE", "where": "SHOT-002", "message": "dead air"}], "warnings": []}

    def fake_mux(*args, **kwargs):
        raise Reached()
    monkeypatch.setattr(b, "assemble_video", lambda *a, **k: {"total_frames": 432, "total_duration_sec": 18.0, "fps": 24})
    monkeypatch.setattr(b, "probe_size", lambda path: (768, 1344))
    monkeypatch.setattr(b, "mux_argv", fake_mux)
    monkeypatch.setattr(gd, "build_captions", lambda *a, **k: ("", []))
    monkeypatch.setattr(gd, "plan_language_outputs",
                        lambda *a, **k: {"reports": {"hi": gate_report}, "languages": {"hi": {"captions": []}}})
    rc = run_main(tmp_path, pack, lock, story, clips, vo, extra=("--langs", "hi", "--manifest", str(manifest)))
    report = json.loads((tmp_path / "out" / "kalika_reel2_build_report.json").read_text(encoding="utf-8"))
    return rc, report


def test_reel2_no_waivers_blocks_dead_air(tmp_path, monkeypatch):
    records, problems = b.load_waivers(tmp_path, "kalika_reel2")
    assert records == [] and problems == []                                  # no waivers.json: nothing is waived
    errors = [{"code": "DEAD_AIR_PAUSE"}, {"code": "VO_MISSING"}]
    waived, blocking = b.split_findings(errors, frozenset())
    assert waived == [] and [e["code"] for e in blocking] == ["DEAD_AIR_PAUSE", "VO_MISSING"]
    rc, report = dead_air_run(tmp_path, monkeypatch)                         # no mux reached: the gate stopped the build
    assert rc == 1
    assert [e["code"] for e in report["languages"]["hi"]["blocking_errors"]] == ["DEAD_AIR_PAUSE"]


def test_reel2_legacy_waiver_lets_dead_air_through(tmp_path, monkeypatch):
    legacy = {"reel": 2, "codes": ["DEAD_AIR_PAUSE"], "owner": "owner", "date": "2026-11-11", "reason": "owner accepts pause"}
    with pytest.raises(Reached):                                             # the waived code no longer blocks: the build reaches mux
        dead_air_run(tmp_path, monkeypatch, waivers_text=json.dumps(legacy))


def test_refused_waiver_is_reported_and_still_blocks(tmp_path, monkeypatch):
    self_signed = {"waivers": [{"waiver_id": "W-1", "scope": "reel", "story_id": "pack", "reel_id": "kalika_reel2",
                                "codes": ["DEAD_AIR_PAUSE"], "status": "approved", "owner": "Satvik", "approved_by": "Satvik",
                                "approved_at": "2026-11-11T10:00:00"}]}
    rc, report = dead_air_run(tmp_path, monkeypatch, waivers_text=json.dumps(self_signed))
    assert rc == 1
    assert report["waiver_problems"] == [{"waiver_id": "W-1", "reason": "approved_by equals owner: self-approval refused"}]
    assert [e["code"] for e in report["languages"]["hi"]["blocking_errors"]] == ["DEAD_AIR_PAUSE"]


def test_scoped_waiver_applies_only_to_its_story_reel_language_and_version(tmp_path):
    scoped = {"waivers": [{"waiver_id": "W-HI", "scope": "language_render", "story_id": "pack", "reel_id": "kalika_reel2",
                           "language": "hindi", "render_version": "rv1", "codes": ["DEAD_AIR_PAUSE"], "status": "approved",
                           "owner": "Satvik", "approved_by": "Reviewer", "approved_at": "2026-11-11T10:00:00"}]}
    (tmp_path / "waivers.json").write_text(json.dumps(scoped), encoding="utf-8")
    records, problems = b.load_waivers(tmp_path, "kalika_reel2")
    assert problems == []
    waived, blocking = wv.split_waived(["DEAD_AIR_PAUSE"], records, "pack", "kalika_reel2", "hindi", "rv1")
    assert waived == {"DEAD_AIR_PAUSE": ["W-HI"]} and blocking == []
    for story, reel, lang, version in (("pack", "kalika_reel2", "english", "rv1"), ("pack", "kalika_reel2", "hindi", "rv2"),
                                       ("other", "kalika_reel2", "hindi", "rv1"), ("pack", "kalika_reel3", "hindi", "rv1")):
        waived, blocking = wv.split_waived(["DEAD_AIR_PAUSE"], records, story, reel, lang, version)
        assert waived == {} and blocking == ["DEAD_AIR_PAUSE"], (story, reel, lang, version)


def test_critical_code_is_never_waived(tmp_path):
    scoped = {"waivers": [{"waiver_id": "W-C", "scope": "reel", "story_id": "pack", "reel_id": "kalika_reel2",
                           "codes": ["VO_MISSING", "DEAD_AIR_PAUSE"], "status": "approved", "owner": "Satvik",
                           "approved_by": "Reviewer", "approved_at": "2026-11-11T10:00:00"}]}
    (tmp_path / "waivers.json").write_text(json.dumps(scoped), encoding="utf-8")
    records, problems = b.load_waivers(tmp_path, "kalika_reel2")
    assert [sorted(r["codes"]) for r in records] == [["DEAD_AIR_PAUSE"]]
    assert any("VO_MISSING" in reason for _, reason in problems)
    legacy = {"reel": 2, "codes": ["VO_MISSING"], "owner": "owner", "date": "2026-11-11", "reason": "x"}
    (tmp_path / "waivers.json").write_text(json.dumps(legacy), encoding="utf-8")
    with pytest.raises(SystemExit, match="critical"):
        b.load_waivers(tmp_path, "kalika_reel2")


def test_waivers_reel_mismatch_raises(tmp_path):
    legacy = {"reel": 1, "codes": ["DEAD_AIR_PAUSE"], "owner": "owner", "date": "2026-11-11", "reason": "test"}
    (tmp_path / "waivers.json").write_text(json.dumps(legacy), encoding="utf-8")
    with pytest.raises(SystemExit, match="not reel 2"):
        b.load_waivers(tmp_path, "kalika_reel2")
    records, _ = b.load_waivers(tmp_path, "kalika_reel1")
    assert [sorted(r["codes"]) for r in records] == [["DEAD_AIR_PAUSE"]]


def test_waivers_without_owner_raise(tmp_path):
    legacy = {"reel": 2, "codes": ["DEAD_AIR_PAUSE"], "date": "2026-11-11", "reason": "test"}
    (tmp_path / "waivers.json").write_text(json.dumps(legacy), encoding="utf-8")
    with pytest.raises(SystemExit):
        b.load_waivers(tmp_path, "kalika_reel2")


def test_clip_qa_fail_blocks(tmp_path):
    pack, lock, story, clips, vo = full_setup(tmp_path, verdict_pass=False, reasons=[{"code": "FLICKER", "text": "x"}])
    with pytest.raises(SystemExit, match="clip QA blocks"):
        run_main(tmp_path, pack, lock, story, clips, vo)


def test_clip_qa_owner_accept_passes_and_sha_mismatch_blocks(tmp_path):
    clip = write_clip(tmp_path, "SHOT-001", verdict_pass=False, reasons=[{"code": "FLICKER", "text": "x"}],
                      owner_accept={"code": "FLICKER", "date": "2026-11-11", "note": "accepted"})
    assert b.clip_qa_problems(clip) == []
    clip.write_bytes(b"changed after QA")
    assert any("sha256 mismatch" in p for p in b.clip_qa_problems(clip))


def test_clip_qa_missing_verdict_blocks_even_with_owner_accept(tmp_path):
    clip = write_clip(tmp_path, "SHOT-001", owner_accept={"code": "FLICKER", "date": "2026-11-11", "note": "accepted"})
    qa_path = clip.parent / "clip_qa.json"
    for bad in (None, "pass", ["pass"]):
        doc = json.loads(qa_path.read_text(encoding="utf-8"))
        doc["verdict"] = bad
        qa_path.write_text(json.dumps(doc), encoding="utf-8")
        problems = b.clip_qa_problems(clip)
        assert problems and "verdict missing" in problems[0], (bad, problems)


def test_stale_lock_blocks(tmp_path):
    pack, lock, story, clips, vo = full_setup(tmp_path)
    (pack / "shots.json").write_text("[]", encoding="utf-8")          # an input changed after the lock was written
    with pytest.raises(SystemExit, match="input hash mismatch"):
        run_main(tmp_path, pack, lock, story, clips, vo)
