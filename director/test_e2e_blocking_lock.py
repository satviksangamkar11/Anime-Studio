"""X-24: offline end-to-end test of one reel-2 blocking lock.

One blocking sheet per shot drives the router, the prompt, the keyframe gate, the clip QA and Gate B.
One timeline lock is the only clock for the voice tracks, the cue sheet, the H3 pixel frames, Gate D and the final reel.
A synthetic 3-shot reel
is built in tmp_path with the real modules. No network, no model, no Colab, no ElevenLabs.

Real gaps found while writing this file are marked xfail(strict=True) with the module and function named in the reason.
"""

import array
import copy
import json
import shutil
import subprocess
import sys
import wave
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
for _p in (str(HERE), str(REPO / "h3"), str(REPO)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import approval_sheet  # noqa: E402
import blocking  # noqa: E402
import blocking_lint  # noqa: E402
import build_final_reel as bfr  # noqa: E402
import build_h3_batch as bhb  # noqa: E402
import build_vo_tracks as bvt  # noqa: E402
import clip_qa  # noqa: E402
import keyframe_gate as kg  # noqa: E402
import keyframe_jobs as kj  # noqa: E402
import shot_router  # noqa: E402
import timeline_lock_core as tlc  # noqa: E402
import timeline_lock_io as tli  # noqa: E402
import waivers as wv  # noqa: E402
import write_timeline_lock as wtl  # noqa: E402
from h3 import gate_d_audio as gd  # noqa: E402
from h3 import render_controller as rc  # noqa: E402
from h3 import v4_to_h3 as v4  # noqa: E402
from h3.schema_and_linter import write_minimal_valid_png  # noqa: E402
from h3.tests.test_v4_to_h3 import _row  # noqa: E402
from core.style_pack import load_core  # noqa: E402
from score import cue_sheet as cs  # noqa: E402

FPS = 24
IDS = ("SHOT-001", "SHOT-002", "SHOT-003")
EDIT = {"SHOT-001": 168, "SHOT-002": 120, "SHOT-003": 192}      # 7.0 s, 5.0 s, 8.0 s -> offsets 0.0, 7.0, 12.0
# the real lock planner (timeline_lock_core.plan_pixels) gives each shot's lattice, pixel frames, trims and seams
PLAN = dict(zip(IDS, tlc.plan_pixels(list(IDS), [EDIT[s] for s in IDS], FPS)))
PIXEL = {sid: PLAN[sid]["pixel_frames"] for sid in IDS}
TRIM = {sid: (PLAN[sid]["trim_in_frame"], PLAN[sid]["trim_out_frame"]) for sid in IDS}
SEAMS = {sid: (PLAN[sid]["incoming_seam"], PLAN[sid]["outgoing_seam"]) for sid in IDS}
LANGS = ("en", "hi", "mr")
LINE_SEC = {"en": 2.0, "hi": 2.5, "mr": 2.2}                       # synthetic narration length per language
PARAMS = {"margin_frames": 0, "fps": FPS, "langs": list(LANGS), "lattice": "v4_to_h3.fit_lattice"}
BIBLE = {"style_lock": {"prefix": "2D hand-drawn cel-shaded anime, organic line weight."},
         "forbidden_looks": ["3D CG"],
         "characters": {"CHAR-RAJ": {"name": "Raj"}, "CHAR-SATI": {"name": "Sati"}},
         "environments": {"ENV-HALL": {"name": "Teak hall", "continuity_landmarks": ["carved teak door"],
                                       "lighting_baseline": {"key": "warm lamp light from the right"}}},
         "props": {"PROP-LAMP": {"name": "Brass lamp"}}}
STAGE = {"output_languages": list(LANGS), "output_language": "en",
         "voice_engine": {"en": "elevenlabs", "hi": "elevenlabs", "mr": "elevenlabs"}}
ANCHORS = {"SHOT-001": ("CHAR-RAJ", "CHAR-SATI"), "SHOT-002": ("CHAR-RAJ",), "SHOT-003": ("CHAR-SATI",)}


# ---------------------------------------------------------------- fixture builders

def _write_wav(path, seconds, value=1000):
    path.parent.mkdir(parents=True, exist_ok=True)
    n = int(round(seconds * 44100))
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(44100)
        w.writeframes((array.array("h", [value]) * n).tobytes())


def _member(cid, name, x, end_x=None, *, y=0.8, scale=0.5, end_pose="standing"):
    end_x = x if end_x is None else end_x

    def pose(px, pz):
        return {"x": px, "y": y, "scale": scale, "facing": "right", "pose": pz, "mouth_moves": False}

    return {"id": cid, "name": name, "speaks": False, "arms": 2, "source_refs": ["ch2:p10"],
            "start": pose(x, "standing"), "end": pose(end_x, end_pose)}


def _sheet(sid, cast, *, arc=2.0):
    return {"schema": "blocking/1", "shot_id": sid, "plate_id": "PLATE-hall", "location_id": "ENV-HALL",
            "kind": "acting", "camera": {"mode": "fixed", "framing": "medium", "move": None},
            "light": {"key_dir": "left", "palette_id": "PAL-warm"},
            "props": [{"id": "P1", "class": "throne", "x": 0.5, "y": 0.9, "visible": ["A", "B"]}],
            "entries": [], "exits": [], "sound_cues": [{"t": 1.0, "text": "soft wind"}],
            "arc_sec": arc, "writer_seconds": 5.0, "cut_to_next": "cut", "source_refs": ["ch2:p10"], "cast": cast}


def _sheets():
    return {"SHOT-001": _sheet("SHOT-001", [_member("CHAR-RAJ", "Raj", 0.3), _member("CHAR-SATI", "Sati", 0.7)]),
            "SHOT-002": _sheet("SHOT-002", [_member("CHAR-RAJ", "Raj", 0.3)]),
            "SHOT-003": _sheet("SHOT-003", [_member("CHAR-SATI", "Sati", 0.5)])}


def _pack_rows():
    rows = [_row("SHOT-001", 1, incoming=SEAMS["SHOT-001"][0], outgoing=SEAMS["SHOT-001"][1]),
            _row("SHOT-002", 1, incoming=SEAMS["SHOT-002"][0], outgoing=SEAMS["SHOT-002"][1]),
            _row("SHOT-003", 1, incoming=SEAMS["SHOT-003"][0], outgoing=SEAMS["SHOT-003"][1])]
    for row in rows:
        sid = row["id"]
        p = PLAN[sid]
        row["pixel_frames"] = p["pixel_frames"]                    # the pack describes the same picture as the lock
        row["lattice_n"] = p["lattice_n"]
        row["latent_slots"] = 5 * p["lattice_n"] + 2
        row["editorial_duration_sec"] = EDIT[sid] / FPS
        row["h3_fields"]["incoming_seam_type"], row["h3_fields"]["outgoing_seam_type"] = SEAMS[sid]
        a = row["audio_and_dialogue_track"]
        a["narration_by_lang"] = {lang: {"text": sid + " line " + lang, "time_range": [0.5, 0.5 + LINE_SEC[lang]]}
                                  for lang in LANGS}
        a["dialogue_by_lang"] = {}
        row["is_opening_0_2s_hook"] = sid == "SHOT-001"
        row["is_closing_hook"] = sid == "SHOT-003"
        row["reference_anchors"]["character_positions"] = [{"id": c, "screen": "center", "depth": "mid"}
                                                          for c in ANCHORS[sid]]
    return rows


def _lock_shots():
    out, start = [], 0
    for sid in IDS:
        p = PLAN[sid]
        edit, pf = EDIT[sid], p["pixel_frames"]
        ti, to = TRIM[sid]
        out.append({"id": sid, "edit_frames": edit, "start_frame": start, "method": "plan_pixels", "beats": [],
                    "error_ms": 0.0, "spare": 0, "lattice_n": p["lattice_n"], "pixel_frames": pf,
                    "trim_in_frame": ti, "trim_out_frame": to, "head_handle_frames": p["head_handle"],
                    "tail_handle_frames": pf - to, "incoming_seam_type": SEAMS[sid][0],
                    "outgoing_seam_type": SEAMS[sid][1], "end_frame_position": to - 1,
                    "bpm": None, "snap": False, "cue": "act1", "act_start_frame": 0})
        start += edit
    return out


@pytest.fixture
def reel(tmp_path):
    """Synthetic reel 2: blocking sheets, pack rows, bible, keyframes, line WAVs (3 languages) and one lock."""
    root = tmp_path / "reel2"
    blk = root / "blocking"
    blk.mkdir(parents=True)
    sheets = _sheets()
    for sid, sheet in sheets.items():
        (blk / (sid + ".json")).write_text(json.dumps(sheet), encoding="utf-8")
    pack = root / "pack"
    pack.mkdir()
    (pack / "shots.json").write_text(json.dumps(_pack_rows()), encoding="utf-8")
    (pack / "bible.json").write_text(json.dumps(BIBLE), encoding="utf-8")
    raw = root / "raw"
    for lang in LANGS:
        for sid in IDS:
            _write_wav(raw / lang / f"{sid}-N.{lang}.wav", LINE_SEC[lang])
    (root / "keyframes").mkdir()
    for sid in IDS:
        for letter in ("A", "B"):
            write_minimal_valid_png(str(root / "keyframes" / f"{sid}-{letter}.png"), 864, 1536)
    inputs = sorted(blk.glob("*.json")) + [pack / "shots.json"] + sorted(raw.rglob("*.wav"))
    lock_path = root / "lock" / "timeline_lock_v1.json"
    lock = tli.write_lock(lock_path, _lock_shots(), [str(p) for p in inputs], PARAMS)
    return SimpleNamespace(root=root, blk=blk, pack=pack, raw=raw, sheets=sheets, lock_path=lock_path,
                           lock=lock, inputs=inputs, story_dir=root)


def _story(reel_fx):
    """convert_pack from the pack rows with the lock and the blocking folder (dict input, no folder reads)."""
    shots = json.loads((reel_fx.pack / "shots.json").read_text(encoding="utf-8"))
    res = v4.convert_pack({"shots": shots, "bible": copy.deepcopy(BIBLE), "stage": copy.deepcopy(STAGE),
                           "asset_root": str(reel_fx.root)},
                          languages=list(LANGS), lock=reel_fx.lock, blocking_dir=str(reel_fx.blk))
    return res


def _routes(reel_fx, sheets=None):
    return shot_router.plan_from_blocking(sheets or reel_fx.sheets, reel_fx.lock)


def _cast_lock_cast(reel_fx, sheets, folder, sid):
    """The cast the V4 converter writes into the shot's cast_lock (the prompt input) from these sheets."""
    folder.mkdir(parents=True)
    for k, sh in sheets.items():
        (folder / (k + ".json")).write_text(json.dumps(sh), encoding="utf-8")
    shots = json.loads((reel_fx.pack / "shots.json").read_text(encoding="utf-8"))
    res = v4.convert_pack({"shots": shots, "bible": copy.deepcopy(BIBLE), "stage": copy.deepcopy(STAGE),
                           "asset_root": str(reel_fx.root)}, languages=list(LANGS), blocking_dir=str(folder))
    shot = next(s for s in res["story"]["episodes"][0]["shots"] if s["shot_id"] == sid)
    return shot["cast_lock"]["cast"]


def _pictures():
    rng = np.random.default_rng(7)
    plate = rng.integers(0, 256, size=(256, 256, 3), dtype=np.uint8)
    img_a = plate.copy()
    img_a[20:40, 20:40] = 255
    img_b = plate.copy()
    img_b[60:80, 60:80] = 255
    return plate, img_a, img_b


def _review(sid, chars):
    side = {"cast_count": len(chars), "chars": {c: {"arms": 2, "posture": "standing"} for c in chars},
            "extra_figures": [], "marks_or_letters": []}
    return {"shot_id": sid, "reviewer": "owner", "full_size": True, "A": dict(side), "B": copy.deepcopy(side)}


def _gate_sheet(sheet, sid):
    """The gate's sheet: blocking.image_expect of the sheet, unchanged. Its posture is (start, end) per character,
    the shape keyframe_gate.posture_matches takes (A = start, B = end)."""
    return {"shot_id": sid, "expect": blocking.image_expect(sheet, EDIT[sid])}


def _run_gate(reel_fx, sid, img_b=None):
    plate, img_a, good_b = _pictures()
    seconds = EDIT[sid] / FPS
    lock = {"seconds": seconds, "input_sha256": reel_fx.lock["input_sha256"],
            "flow_root": str(reel_fx.root / "flow")}
    chars = [c["id"] for c in reel_fx.sheets[sid]["cast"]]
    ok = kg.gate(plate, img_a, good_b if img_b is None else img_b, _gate_sheet(reel_fx.sheets[sid], sid),
                 _review(sid, chars), lock)
    record = kg.keyframe_dir(reel_fx.root / "flow") / (sid + ".json")
    return ok, record


def _make_clip(path, seconds=8):
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i",
                    "testsrc=size=192x336:rate=24:duration=" + str(seconds), "-pix_fmt", "yuv420p", str(path)],
                   check=True)


# ================================================================ (a) one clock

def test_lock_is_consistent_and_three_languages_share_the_clock(reel):
    rows = tli.lock_rows(reel.lock)
    assert [r["offset_sec"] for r in rows] == [0.0, 7.0, 12.0]
    assert [r["editorial_duration_sec"] for r in rows] == [7.0, 5.0, 8.0]
    # every consumer that takes the lock sees the same editorial length in every language (no retime set)
    for lang in LANGS:
        vo = bvt.apply_lock([{"id": sid} for sid in IDS], reel.lock, lang)
        assert [r["editorial_duration_sec"] for r in vo] == [r["editorial_duration_sec"] for r in rows]


def test_voice_tracks_follow_the_lock_clock(reel, tmp_path):
    """Every language's voice track is cut to the lock's editorial length and its lines start at the scripted times."""
    out = tmp_path / "vo"
    report, problems = bvt.build(str(reel.pack), str(reel.raw), str(out), list(LANGS), lock=str(reel.lock_path))
    assert problems == []
    assert len(report) == 9
    for row in report:
        assert row["editorial"] == EDIT[row["shot"]] / FPS, row
        assert row["tempo"] == 1.0
        assert (out / row["lang"] / (row["shot"] + ".wav")).is_file()
        starts = [line["start"] for line in row["lines"]]
        assert starts == [0.5], row


def test_voice_file_length_is_editorial_minus_tail(reel, tmp_path):
    """Regression guard. Found failing at the first run (atempo -> adelay -> apad -> atrim wrote files 0.45-0.6 s
    short under ffmpeg 8.1.1). build_vo_tracks.py changed at 22:07 (no atempo, lock verified first) and passes now."""
    out = tmp_path / "vo_len"
    bvt.build(str(reel.pack), str(reel.raw), str(out), list(LANGS), lock=str(reel.lock_path))
    for lang in LANGS:
        for sid in IDS:
            ed = EDIT[sid] / FPS
            with wave.open(str(out / lang / (sid + ".wav")), "rb") as w:
                length = w.getnframes() / w.getframerate()
            # build_vo_tracks ends each VO file TAIL (0.10 s) before the cut; Gate D pads it to the cut itself
            assert abs(length - (ed - bvt.TAIL)) < 0.002, (lang, sid, length)


def test_three_consumers_same_offsets(reel, monkeypatch, tmp_path):
    """build_final_reel offsets, render_controller Gate D seconds and the cue sheet shot starts are 0.0, 7.0, 12.0
    for all three languages, and the lock is the only source of them."""
    rows = bfr.lock_rows_for_pack(str(reel.lock_path), reel.pack)
    final_offsets = [r["offset_sec"] for r in rows]
    seen = {}

    def spy(reel_id, languages, vo_dir, bgm, *, shots, **kw):
        seen["shots"] = shots
        return {"ok": True, "reports": {lg: {"ok": True, "errors": [], "warnings": []} for lg in languages},
                "languages": {}}

    monkeypatch.setattr(rc, "plan_language_outputs", spy)
    story = _story(reel)["story"]
    story["registry"]["story_gate_checks"] = {"closing_gate": "present"}
    ep = story["episodes"][0]
    res = rc._gate_d_result(story, [{"episode": ep, "shots": ep["shots"]}], str(tmp_path / "o"), list(LANGS),
                            str(reel.lock_path))
    assert res["reasons"] == [], res
    # the seconds Gate D really received (the shots passed to plan_language_outputs) must be the lock's
    assert "shots" in seen, "Gate D never planned the languages"
    assert [s["editorial_duration_sec"] for s in seen["shots"]] == [7.0, 5.0, 8.0]
    gate_d_offsets, t = [], 0.0
    for s in seen["shots"]:
        gate_d_offsets.append(t)
        t += s["editorial_duration_sec"]
    report, _problems = bvt.build(str(reel.pack), str(reel.raw), str(tmp_path / "vo3"), list(LANGS),
                                  lock=str(reel.lock_path))
    shots = json.loads((reel.pack / "shots.json").read_text(encoding="utf-8"))
    vo_reports = {lg: [r for r in report if r["lang"] == lg] for lg in LANGS}
    sheet, cue_report = cs.build_locked_cue_sheet(shots, reel.lock, vo_reports)
    assert sheet is not None, cue_report
    cue_starts = [s["start_s"] for s in sheet["shots"]]
    assert final_offsets == gate_d_offsets == cue_starts == [0.0, 7.0, 12.0]


def test_cue_sheet_shot_starts_match_the_lock(reel, tmp_path):
    vo_reports = {}
    report, problems = bvt.build(str(reel.pack), str(reel.raw), str(tmp_path / "vo"), list(LANGS),
                                 lock=str(reel.lock_path))
    for row in report:
        vo_reports.setdefault(row["lang"], []).append(row)
    shots = json.loads((reel.pack / "shots.json").read_text(encoding="utf-8"))
    sheet, cue_report = cs.build_locked_cue_sheet(shots, reel.lock, vo_reports)
    assert sheet is not None, cue_report
    assert [s["start_s"] for s in sheet["shots"]] == [0.0, 7.0, 12.0]
    assert sheet["total_frames"] == reel.lock["total_frames"] == 480


def test_final_reel_offsets_match_the_lock(reel):
    rows = bfr.lock_rows_for_pack(str(reel.lock_path), reel.pack)
    assert [r["offset_sec"] for r in rows] == [0.0, 7.0, 12.0]
    assert [r["editorial_duration_sec"] for r in rows] == [7.0, 5.0, 8.0]
    for lang in LANGS:
        vo = reel.root / "vo_final" / lang
        vo.mkdir(parents=True, exist_ok=True)
        for sid in IDS:
            shutil.copy(reel.raw / lang / (sid + "-N." + lang + ".wav"), vo / (sid + ".wav"))
        argv, total = bfr.mux_argv(rows, lang, str(reel.root / "vo_final"), str(reel.root / "v.mp4"),
                                   str(reel.root / "e.mp4"), str(reel.root / "c.ass"), str(reel.root))
        assert total == pytest.approx(20.0)
        flt = " ".join(argv)
        for start, end in ((0.0, 7.0), (7.0, 12.0), (12.0, 20.0)):
            assert "atrim=start=%.3f:end=%.3f" % (start, end) in flt, (lang, start, end)


def test_h3_pixel_frames_and_trims_match_the_lock(reel):
    res = _story(reel)
    assert not [p for p in res["problems"] if "lock trims" in p or "not in the timeline lock" in p], res["problems"]
    shots = res["story"]["episodes"][0]["shots"]
    for shot in shots:
        sid = shot["shot_id"]
        t = shot["timing_and_lattice"]
        lock_shot = next(s for s in reel.lock["shots"] if s["id"] == sid)
        assert t["editorial_frames"] == lock_shot["edit_frames"]
        assert t["pixel_frames"] == lock_shot["pixel_frames"]
        assert (t["trim_in_frame"], t["trim_out_frame"]) == (lock_shot["trim_in_frame"], lock_shot["trim_out_frame"])


def test_gate_d_seconds_and_render_pixels_match_the_lock(reel, monkeypatch, tmp_path):
    seen = {}

    def spy(reel_id, languages, vo_dir, bgm, *, shots, **kw):
        seen["shots"] = shots
        seen["langs"] = list(languages)
        return {"ok": True, "reports": {lg: {"ok": True, "errors": [], "warnings": []} for lg in languages},
                "languages": {}}

    monkeypatch.setattr(rc, "plan_language_outputs", spy)
    res = _story(reel)
    story = res["story"]
    groups = [{"episode": story["episodes"][0], "shots": story["episodes"][0]["shots"]}]
    rc._gate_d_result(story, groups, str(tmp_path / "out"), list(LANGS), str(reel.lock_path))
    assert seen["langs"] == list(LANGS)
    offs, t = [], 0.0
    for s in seen["shots"]:
        offs.append(t)
        t += s["editorial_duration_sec"]
    assert offs == [0.0, 7.0, 12.0]
    assert [s["editorial_duration_sec"] for s in seen["shots"]] == [7.0, 5.0, 8.0]
    # Gate D's sheet of render pixels: legacy_rows takes the lock's pixel frames for every shot
    routes = {"routes": _routes(reel)}
    rows, post = bhb.legacy_rows(story, story["episodes"][0]["episode_id"], routes=routes, lock=reel.lock)
    assert post == []
    assert [r["render_frames"] for r in rows] == [PIXEL[s] for s in IDS]


def test_same_gate_d_verdict(reel, monkeypatch, tmp_path):
    res = _story(reel)
    story = res["story"]
    ep = story["episodes"][0]
    story["registry"]["story_gate_checks"] = {"closing_gate": "present"}
    groups = [{"episode": ep, "shots": ep["shots"]}]
    via_controller = rc._gate_d_result(story, groups, str(tmp_path / "out"), list(LANGS), str(reel.lock_path))
    lock_sec = {r["id"]: r["editorial_duration_sec"] for r in tli.lock_rows(reel.lock)}
    shots = [dict(s, editorial_duration_sec=lock_sec[s["shot_id"]]) for s in ep["shots"]]
    direct = gd.plan_language_outputs(ep["episode_id"], list(LANGS), str(tmp_path / "out" / ep["episode_id"] / "audio"
                                                                        / "vo"),
                                      None, shots=shots, video_path=str(tmp_path / "v.mp4"), video_has_audio=True,
                                      captions_dir=str(tmp_path / "c"), export_dir=str(tmp_path / "e"),
                                      story_gate_checks=story["registry"]["story_gate_checks"],
                                      voice_engines=story["registry"].get("voice_engine"))
    direct_reasons = [f"{ep['episode_id']} {lg}: {e['code']} {e['where']}: {e['message']}"
                      for lg in LANGS for e in direct["reports"][lg]["errors"]]
    assert via_controller["reasons"] == direct_reasons


# ================================================================ (a/b) one lock, every consumer refuses a stale input

def _touch_wav(reel_fx):
    _write_wav(reel_fx.raw / "hi" / "SHOT-001-N.hi.wav", LINE_SEC["hi"] + 0.25)   # one changed input byte-count


def test_stale_lock_blocks_all_three(reel, tmp_path):
    before = tli.verify_lock(str(reel.lock_path), reel.lock["inputs"], reel.lock["params"])
    assert before["lock_sha256"] == reel.lock["lock_sha256"]
    _touch_wav(reel)
    with pytest.raises(tli.StaleLockError):
        tli.verify_lock(str(reel.lock_path), reel.lock["inputs"], reel.lock["params"])
    with pytest.raises(SystemExit, match="stale timeline lock"):
        bfr.lock_rows_for_pack(str(reel.lock_path), reel.pack)
    res = rc._timeline_result(str(reel.lock_path), [{"shots": [{"shot_id": s} for s in IDS]}])
    assert res["ok"] is False and "stale timeline lock" in res["reasons"][0]
    # the cue sheet CLI verifies the lock before it reads anything else
    out = tmp_path / "cue.json"
    vo = tmp_path / "vo_report.json"
    vo.write_text("[]", encoding="utf-8")
    code = cs.main(["--shots", str(reel.pack / "shots.json"), "--lock", str(reel.lock_path),
                    "--vo-report", str(vo), "--out", str(out)])
    assert code == 2 and not out.exists()


def test_changed_blocking_sheet_byte_makes_lock_stale(reel):
    sheet_path = reel.blk / "SHOT-002.json"
    data = json.loads(sheet_path.read_text(encoding="utf-8"))
    data["light"]["palette_id"] = "PAL-cool"
    sheet_path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(tli.StaleLockError):
        tli.verify_lock(str(reel.lock_path), reel.lock["inputs"], reel.lock["params"])
    with pytest.raises(SystemExit):
        bfr.lock_rows_for_pack(str(reel.lock_path), reel.pack)


def test_vo_tracks_refuse_a_stale_lock(reel, tmp_path):
    """Regression guard. Was an xfail gap (load_lock only, no verify_lock); build_vo_tracks.py now verifies first."""
    _touch_wav(reel)
    with pytest.raises((ValueError, SystemExit)):
        bvt.build(str(reel.pack), str(reel.raw), str(tmp_path / "vo"), list(LANGS), lock=str(reel.lock_path))


def test_clip_qa_refuses_a_stale_lock(reel, tmp_path):
    """Gap fixed: clip_qa.qa_shot verifies the lock against its recorded inputs/params before any analysis."""
    _touch_wav(reel)
    clip = tmp_path / "SHOT-001.mp4"
    _make_clip(clip)
    rng = np.random.default_rng(3)
    key_a, key_b = rng.random((336, 192)), rng.random((336, 192))
    review = tmp_path / "review.json"
    review.write_text(json.dumps({"0": {"person": 2}}), encoding="utf-8")
    with pytest.raises((ValueError, tli.StaleLockError)):
        clip_qa.qa_shot("SHOT-001", str(clip), str(reel.lock_path), key_a, key_b, str(review),
                        reel.sheets["SHOT-001"], str(reel.raw / "en" / "SHOT-001-N.en.wav"), str(tmp_path / "root"))


# ================================================================ (b) one sheet drives router, prompt, gate, clip, B

def test_one_sheet_drives_router_prompt_gate_clip(reel, monkeypatch, tmp_path):
    base = copy.deepcopy(reel.sheets)
    base["SHOT-002"] = _sheet("SHOT-002", [_member("CHAR-RAJ", "Raj", 0.3, 0.4), _member("CHAR-SATI", "Sati", 0.7)],
                              arc=1.0)
    lock_ids = {s["id"]: s for s in reel.lock["shots"]}
    routes_full = _routes(reel, base)
    assert routes_full["SHOT-002"]["route"] == "SOFT_SE"
    args_full = blocking.prompt_args(base["SHOT-002"])
    assert args_full["cast"] == ["Raj", "Sati"]
    assert blocking.image_expect(base["SHOT-002"], EDIT["SHOT-002"])["required_cast_count"] == 2
    # the V4 prompt input (cast_lock.cast) is read from the same sheet
    assert _cast_lock_cast(reel, base, tmp_path / "cl_base", "SHOT-002") == ["Raj", "Sati"]
    # remove Raj (the moving member) from the same sheet: router, prompt, cast_lock, gate count and keyframe jobs move
    less = copy.deepcopy(base)
    less["SHOT-002"]["cast"] = [m for m in less["SHOT-002"]["cast"] if m["id"] != "CHAR-RAJ"]
    routes_less = _routes(reel, less)
    assert routes_less["SHOT-002"]["route"] == "SE"
    assert blocking.prompt_args(less["SHOT-002"])["cast"] == ["Sati"]
    assert _cast_lock_cast(reel, less, tmp_path / "cl_less", "SHOT-002") == ["Sati"]
    assert blocking.image_expect(less["SHOT-002"], EDIT["SHOT-002"])["required_cast_count"] == 1
    # clip QA: a reviewer's 'person' is still allowed while one cast member remains
    review = tmp_path / "person_review.json"
    review.write_text(json.dumps({"0": {"person": 2, "throne": 1}}), encoding="utf-8")
    assert clip_qa.new_classes(str(review), less["SHOT-002"]) == []
    monkeypatch.setattr(kj, "FLOW_ROOT", str(tmp_path / "flow"))
    flow = tmp_path / "flow" / "plates"
    flow.mkdir(parents=True)
    write_minimal_valid_png(str(flow / "hall.png"), 64, 64)
    (flow / "plates.json").write_text(json.dumps({"PLATE-hall": {"path": "hall.png"}}), encoding="utf-8")
    job_a, job_b = kj.jobs_for_shot(less["SHOT-002"], "PLATE-hall", [])
    assert job_a["people_count"] == 1 and job_b["base_edit_id"] == "SHOT-002-A"
    assert job_b["edit_instruction"].startswith("same picture, make these exact changes only")
    # the clip QA known classes come from the sheet's props (and 'person'), not from the cast names
    assert blocking.known_classes(less["SHOT-002"]) == blocking.known_classes(base["SHOT-002"]) == {"person", "throne"}
    # removing the last cast member removes 'person' from the allowed clip classes: clip QA then flags it
    empty = copy.deepcopy(less)
    empty["SHOT-002"]["cast"] = []
    assert _cast_lock_cast(reel, empty, tmp_path / "cl_empty", "SHOT-002") == []
    assert blocking.image_expect(empty["SHOT-002"], EDIT["SHOT-002"])["required_cast_count"] == 0
    assert blocking.known_classes(empty["SHOT-002"]) == {"throne"}
    assert clip_qa.new_classes(str(review), empty["SHOT-002"]) == ["person"]
    assert lock_ids["SHOT-002"]["edit_frames"] == 120


def test_cast_mismatch_anywhere_fails(reel, tmp_path):
    # V4 anchors say Raj and Sati; the sheet says Sati only
    bad = copy.deepcopy(reel.sheets)
    bad["SHOT-001"]["cast"] = [_member("CHAR-SATI", "Sati", 0.7)]
    shots = json.loads((reel.pack / "shots.json").read_text(encoding="utf-8"))
    alt = tmp_path / "alt_blocking"
    alt.mkdir()
    for sid, sh in bad.items():
        (alt / (sid + ".json")).write_text(json.dumps(sh), encoding="utf-8")
    res = v4.convert_pack({"shots": shots, "bible": copy.deepcopy(BIBLE), "stage": copy.deepcopy(STAGE),
                           "asset_root": str(reel.root)}, languages=list(LANGS), lock=reel.lock,
                          blocking_dir=str(alt))
    assert any("SHOT-001: cast" in p and "!= blocking" in p for p in res["problems"]), res["problems"]
    # a keyframe review with one person too many fails cast parity at the gate
    ok, record = _run_gate(reel, "SHOT-001")
    assert ok is True
    plate, img_a, img_b = _pictures()
    review = _review("SHOT-001", ["CHAR-RAJ", "CHAR-SATI"])
    review["A"]["cast_count"] = 3
    review["B"]["cast_count"] = 3
    lock = {"seconds": 7.0, "input_sha256": reel.lock["input_sha256"], "flow_root": str(tmp_path / "flow2")}
    assert kg.gate(plate, img_a, img_b, _gate_sheet(reel.sheets["SHOT-001"], "SHOT-001"), review, lock) is False
    # a clip review that counts a class the sheet does not know
    rv = tmp_path / "clip_review.json"
    rv.write_text(json.dumps({"0": {"person": 2, "dog": 1}}), encoding="utf-8")
    assert clip_qa.new_classes(str(rv), reel.sheets["SHOT-001"]) == ["dog"]


# ================================================================ (c) defects caught at their own stage

def test_defect_bad_blocking_sheet_caught_by_validate_and_lint(reel):
    bad = copy.deepcopy(reel.sheets["SHOT-002"])
    bad["cast"][0]["start"]["facing"] = "up"                       # BLK-S04 bad facing
    assert any("bad facing" in p for p in blocking.validate(bad))
    # a pose change in 0.25 s (lock says 6 frames) is a lint error at the blocking stage
    moved = copy.deepcopy(reel.sheets["SHOT-002"])
    moved["cast"][0]["end"]["pose"] = "seated"
    short_lock = {"fps": FPS, "shots": [{"id": "SHOT-002", "edit_frames": 6}]}
    problems = blocking_lint.lint([moved], lock=short_lock)
    assert any("L02" in p or "L03" in p for p in problems), problems


def test_convert_pack_refuses_a_sheet_that_lint_rejects(reel, tmp_path):
    """haiku-gap2: convert_pack lints each sheet with the row's seconds. SHOT-002 is 5 s in the lock, so this test
    gives its row 0.25 s and passes no lock (the seconds come from the row); the pose change then gives L02."""
    moved = copy.deepcopy(reel.sheets["SHOT-002"])
    moved["cast"][0]["end"]["pose"] = "seated"
    alt = tmp_path / "alt"
    alt.mkdir()
    (alt / "SHOT-002.json").write_text(json.dumps(moved), encoding="utf-8")
    shots = json.loads((reel.pack / "shots.json").read_text(encoding="utf-8"))
    for row in shots:
        if row["id"] == "SHOT-002":
            row["editorial_duration_sec"] = 0.25
    res = v4.convert_pack({"shots": shots, "bible": copy.deepcopy(BIBLE), "stage": copy.deepcopy(STAGE),
                           "asset_root": str(reel.root)}, languages=list(LANGS), blocking_dir=str(alt))
    assert "SHOT-002: L02 pose change too fast" in res["problems"], res["problems"]


def test_defect_background_moved_keyframe_fails_gate_and_refuses_approval(reel, tmp_path):
    plate, img_a, img_b = _pictures()
    moved_b = np.roll(plate, 9, axis=1)
    moved_b[60:80, 60:80] = 255                                    # the set itself slid 9 px between A and B
    ok, _ = _run_gate(reel, "SHOT-001", img_b=moved_b)
    assert ok is False
    gate_file = kg.keyframe_dir(reel.root / "flow") / "SHOT-001.json"
    assert json.loads(gate_file.read_text())["checks"]["background_lock"] is False
    # gate_b.json sits in the flow root the gate wrote to: approve() reads the gate from the same folder
    with pytest.raises(ValueError, match="keyframe gate did not pass"):
        approval_sheet.approve("SHOT-001", "owner", str(reel.root / "flow" / "gate_b.json"))


def test_defect_missing_gate_b_approval_blocks_stage(reel, tmp_path):
    ok, _ = _run_gate(reel, "SHOT-001")
    assert ok is True
    kdir = kg.keyframe_dir(reel.root / "flow")
    gate_b = reel.root / "flow" / "gate_b.json"
    problems = approval_sheet.gate_b_ok(str(gate_b), str(kdir), list(IDS))
    assert "SHOT-001: no owner approval in gate_b.json" in problems
    assert any(p.startswith("SHOT-002: no owner approval") for p in problems)
    res = rc._keyframe_result(str(gate_b), str(kdir), [{"shots": [{"shot_id": s} for s in IDS]}])
    assert res["ok"] is False


def test_gate_b_record_becomes_stale_if_the_gate_changes(reel, tmp_path):
    ok, _ = _run_gate(reel, "SHOT-001")
    assert ok is True
    kdir = kg.keyframe_dir(reel.root / "flow")
    gfile = kdir / "SHOT-001.json"
    gate_b = reel.root / "flow" / "gate_b.json"
    approval_sheet.approve("SHOT-001", "owner", str(gate_b))
    assert approval_sheet.gate_b_ok(str(gate_b), str(kdir), ["SHOT-001"]) == []
    gfile.write_text(gfile.read_text().replace('"pass": true', '"pass": true, "note": "x"'), encoding="utf-8")
    assert approval_sheet.gate_b_ok(str(gate_b), str(kdir), ["SHOT-001"]) == [
        "SHOT-001: keyframe gate changed after approval (stale), re-approve"]


def test_image_expect_posture_matches_the_gate(reel, tmp_path):
    """Gap 3 (fixed): image_expect's (start, end) posture goes to the gate unchanged and a real run passes."""
    plate, img_a, img_b = _pictures()
    chars = [c["id"] for c in reel.sheets["SHOT-001"]["cast"]]
    lock = {"seconds": 7.0, "input_sha256": reel.lock["input_sha256"], "flow_root": str(tmp_path / "flow3")}
    sheet = {"shot_id": "SHOT-001", "expect": blocking.image_expect(reel.sheets["SHOT-001"], EDIT["SHOT-001"])}
    assert kg.gate(plate, img_a, img_b, sheet, _review("SHOT-001", chars), lock) is True


def test_approval_finds_the_gate_the_gate_wrote(reel, tmp_path):
    """Gap 4 (fixed): the gate and approve() share keyframe_dir, so approve() finds the record the gate wrote."""
    ok, _ = _run_gate(reel, "SHOT-001")
    assert ok is True
    gate_b = reel.root / "flow" / "gate_b.json"
    record = approval_sheet.approve("SHOT-001", "owner", str(gate_b))
    assert record["shot"] == "SHOT-001"
    assert approval_sheet.gate_b_ok(str(gate_b), str(kg.keyframe_dir(reel.root / "flow")), ["SHOT-001"]) == []


def test_defect_new_object_in_clip_blocks_clip_and_owner_accept_is_recorded(reel, tmp_path):
    clip = tmp_path / "SHOT-001.mp4"
    _make_clip(clip)
    rng = np.random.default_rng(5)
    key_a, key_b = rng.random((336, 192)), rng.random((336, 192))
    review = tmp_path / "review.json"
    review.write_text(json.dumps({"0": {"person": 2, "dog": 1}}), encoding="utf-8")
    root = tmp_path / "clips"
    doc = clip_qa.qa_shot("SHOT-001", str(clip), str(reel.lock_path), key_a, key_b, str(review),
                          reel.sheets["SHOT-001"], str(reel.raw / "en" / "SHOT-001-N.en.wav"), str(root))
    assert doc["window"] == [0, 168]
    assert doc["verdict"]["pass"] is False
    assert "NEW_CLASS" in [r["code"] for r in doc["verdict"]["reasons"]]
    qa = root / "results" / "SHOT-001" / "clip_qa.json"
    problems = clip_qa.clip_ok(str(qa), str(clip))
    assert problems and "verdict failed without owner accept" in problems[0]
    # the clip also fails END_MISMATCH and SCENE_CUT (synthetic keyframes): each code needs its own accept
    for code in ("NEW_OBJECT", "END_MISMATCH", "SCENE_CUT"):
        clip_qa.accept("SHOT-001", code, "owner accepts " + code, str(root))
    assert clip_qa.clip_ok(str(qa), str(clip)) == []


def test_accept_of_one_code_does_not_unblock_another(reel, tmp_path):
    """Gap fixed: clip_ok clears a failure only with an owner accept of its own code (FLICKER != NEW_CLASS)."""
    clip = tmp_path / "SHOT-001.mp4"
    _make_clip(clip)
    rng = np.random.default_rng(5)
    key_a, key_b = rng.random((336, 192)), rng.random((336, 192))
    review = tmp_path / "review.json"
    review.write_text(json.dumps({"0": {"person": 2, "dog": 1}}), encoding="utf-8")
    root = tmp_path / "clips2"
    clip_qa.qa_shot("SHOT-001", str(clip), str(reel.lock_path), key_a, key_b, str(review),
                    reel.sheets["SHOT-001"], str(reel.raw / "en" / "SHOT-001-N.en.wav"), str(root))
    clip_qa.accept("SHOT-001", "FLICKER", "unrelated accept", str(root))
    problems = clip_qa.clip_ok(str(root / "results" / "SHOT-001" / "clip_qa.json"), str(clip))
    assert problems, "a FLICKER accept must not clear a NEW_CLASS failure"


def test_defect_loudness_off_core_target_is_caught(reel):
    target = load_core()["delivery"]["audio"]["lufs"]
    assert gd.LOUDNESS["target_lufs"] == target == -14
    good = ("[Parsed_ebur128_0 @ 0x1] Summary:\n  Integrated loudness:\n    I:         -14.0 LUFS\n"
            "    LRA:        4.0 LU\n  True peak:\n    Peak:       -1.5 dBFS\n")
    assert gd.check_post_aac_loudness(good)["errors"] == []
    loud = good.replace("I:         -14.0", "I:         -10.0")
    assert [e["code"] for e in gd.check_post_aac_loudness(loud)["errors"]] == ["LOUDNESS_OUT_OF_TARGET"]
    edge = good.replace("I:         -14.0", "I:         -14.6")
    assert [e["code"] for e in gd.check_post_aac_loudness(edge)["errors"]] == ["LOUDNESS_OUT_OF_TARGET"]
    hot_tp = good.replace("Peak:       -1.5", "Peak:       -0.4")
    assert [e["code"] for e in gd.check_post_aac_loudness(hot_tp)["errors"]] == ["TRUE_PEAK_OVER"]


def _waiver(**kw):
    rec = {"waiver_id": "W-1", "scope": "language_render", "story_id": "kalika_puran", "reel_id": "kalika_reel2",
           "language": "hindi", "codes": ["CAPTION_SCRIPT"], "status": "approved", "owner": "satvik",
           "approved_by": "reviewer-two", "approved_at": "2026-11-11T10:00:00+05:30", "render_version": "v5"}
    rec.update(kw)
    return rec


def _write_waivers(tmp_path, entries):
    path = tmp_path / "waivers.json"
    path.write_text(json.dumps({"waivers": entries}), encoding="utf-8")
    return str(path)


def test_waiver_self_approval_and_critical_codes_are_refused(tmp_path):
    records, problems = wv.read_waivers(_write_waivers(tmp_path, [_waiver(approved_by="satvik")]))
    assert records == [] and any("self-approval refused" in why for _id, why in problems)
    records, problems = wv.read_waivers(_write_waivers(tmp_path, [_waiver(codes=["VO_MISSING"])]))
    assert records == [] and any("can never be waived" in why for _id, why in problems)
    records, problems = wv.read_waivers(_write_waivers(tmp_path, [_waiver(codes=["CAPTION_SCRIPT", "VO_MISSING"])]))
    assert len(records) == 1 and records[0]["codes"] == frozenset({"CAPTION_SCRIPT"})
    assert any("VO_MISSING" in why for _id, why in problems)


def test_self_approval_is_case_insensitive(tmp_path):
    """Gap 6 closed: 'Satvik' approving for owner 'satvik' is refused (waivers._person_key)."""
    records, _problems = wv.read_waivers(_write_waivers(tmp_path, [_waiver(approved_by="Satvik")]))
    assert records == []


def test_language_scope_hindi_waiver_does_not_cover_english(tmp_path):
    records, problems = wv.read_waivers(_write_waivers(tmp_path, [_waiver()]))
    assert problems == [] and len(records) == 1
    assert bfr.LANG_NAME["hi"] == "hindi" and bfr.LANG_NAME["en"] == "english"
    waived, blocking_codes = wv.split_waived(["CAPTION_SCRIPT"], records, "kalika_puran", "kalika_reel2",
                                             bfr.LANG_NAME["hi"], "v5")
    assert waived == {"CAPTION_SCRIPT": ["W-1"]} and blocking_codes == []
    waived, blocking_codes = wv.split_waived(["CAPTION_SCRIPT"], records, "kalika_puran", "kalika_reel2",
                                             bfr.LANG_NAME["en"], "v5")
    assert waived == {} and blocking_codes == ["CAPTION_SCRIPT"]
    waived, blocking_codes = wv.split_waived(["CAPTION_SCRIPT"], records, "kalika_puran", "kalika_reel2",
                                             "hindi", "v6")
    assert waived == {} and blocking_codes == ["CAPTION_SCRIPT"], "another render version is not covered"


def test_soft_end_route_is_refused_before_any_render_batch(reel):
    base = copy.deepcopy(reel.sheets)
    base["SHOT-002"] = _sheet("SHOT-002", [_member("CHAR-RAJ", "Raj", 0.3, 0.4)], arc=1.0)
    routes = {"routes": _routes(reel, base)}
    assert routes["routes"]["SHOT-002"]["route"] == "SOFT_SE"
    story = _story(reel)["story"]
    with pytest.raises(ValueError, match="Wan2GP bd1ff59"):
        bhb.legacy_rows(story, story["episodes"][0]["episode_id"], routes=routes, lock=reel.lock)


def test_positive_reel_routes_and_rows_pass_the_batch(reel):
    routes = {"routes": _routes(reel)}
    assert {sid: r["route"] for sid, r in routes["routes"].items()} == {"SHOT-001": "SE", "SHOT-002": "SE",
                                                                         "SHOT-003": "SE"}
    story = _story(reel)["story"]
    rows, post = bhb.legacy_rows(story, story["episodes"][0]["episode_id"], routes=routes, lock=reel.lock)
    assert post == [] and len(rows) == 3
    assert all("\n\n" not in r["prompt_override"] for r in rows)


# ================================================================ stale lock and plan

def test_write_timeline_lock_plan_and_versions(reel, tmp_path):
    """plan_lock reads the WAV seconds of every language: the lock holds every line in each language."""
    rows = json.loads((reel.pack / "shots.json").read_text(encoding="utf-8"))
    secs = {lang: LINE_SEC[lang] for lang in LANGS}

    def wav_fn(lang, line_id):
        return secs[lang]

    plan = wtl.plan_lock(rows, wav_fn, list(LANGS), None, {sid: EDIT[sid] / FPS for sid in IDS})
    assert [p["id"] for p in plan] == list(IDS)
    start = 0
    for p in plan:
        assert p["start_frame"] == start
        start += p["edit_frames"]
        assert p["trim_out_frame"] - p["trim_in_frame"] == p["edit_frames"]
        assert p["end_frame_position"] == p["trim_out_frame"] - 1
        assert p["pixel_frames"] >= p["trim_out_frame"]
        for lang in LANGS:
            assert p["edit_frames"] / FPS >= 0.5 + secs[lang]
    out = tmp_path / "lockdir"
    inputs = [reel.pack / "shots.json"]
    first = wtl.write_version(str(out), plan, inputs, PARAMS)
    assert first.name == "timeline_lock_v1.json"
    lock = tli.load_lock(first)
    assert lock["total_frames"] == sum(p["edit_frames"] for p in plan)
    v1_bytes = first.read_bytes()
    second = wtl.write_version(str(out), plan, inputs, dict(PARAMS, tempo=1.0))
    assert second.name == "timeline_lock_v2.json"
    assert first.read_bytes() == v1_bytes, "write_version must never touch an existing version"


def test_retime_is_kept_out_of_the_one_clock_when_absent(reel):
    lock = copy.deepcopy(reel.lock)
    assert all(tli.retime_for(lock, sid, lang) == 1.0 for sid in IDS for lang in LANGS)


def test_retimed_voice_track_matches_the_final_reel_clock(reel):
    """Regression guard. Was an xfail gap (two clocks: retime applied to VO only); editorial_from_lock now uses the lock
    frames for every language, as the picture and build_final_reel do."""
    lock = copy.deepcopy(reel.lock)
    for s in lock["shots"]:
        if s["id"] == "SHOT-001":
            s["retime"] = {"hi": 0.97}
    final_ed = {r["id"]: r["editorial_duration_sec"] for r in tli.lock_rows(lock)}
    vo_ed = bvt.editorial_from_lock(lock, "SHOT-001", "hi")
    assert vo_ed == pytest.approx(final_ed["SHOT-001"])


def test_sheet_folder_is_wired_through_the_lock_cli(reel, tmp_path):
    """Gap 7 closed: write_timeline_lock.main reads the blocking/1 sheet folder (no blocking.json). The reel's real
    sheets are read by the CLI, so a corrupted one is refused there with its BLK code."""
    blk = tmp_path / "blocking"
    shutil.copytree(reel.blk, blk)
    bad = dict(reel.sheets["SHOT-002"], writer_seconds=0)
    (blk / "SHOT-002.json").write_text(json.dumps(bad), encoding="utf-8")
    with pytest.raises(SystemExit, match="BLK-S13"):
        wtl.main(["--pack", str(reel.pack), "--wav-root", str(reel.raw), "--manifest", str(reel.pack / "bible.json"),
                  "--out-dir", str(tmp_path / "lock_cli"), "--langs", ",".join(LANGS), "--blocking-dir", str(blk)])
    assert not (blk / "blocking.json").exists()
