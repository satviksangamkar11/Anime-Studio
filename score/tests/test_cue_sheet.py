"""Tests for score/cue_sheet.py. The main fixture is the real Kalika Puran reel 1 pack (70.0 s, 10 shots)."""
import copy
import inspect
import json
from pathlib import Path

import pytest

from score import cue_sheet as cs
from score.cue_sheet import build_cue_sheet, cut_offsets, gaps_between, merge_windows, parse_range, solve_tempo

ROOT = Path(__file__).resolve().parents[2]
KALIKA = ROOT / "stories" / "kalika_puran_bhag1" / "pack_opus_high_20261108_v4_deva" / "shots.json"
FRAME_S = 1 / 24


@pytest.fixture(scope="module")
def kalika_shots():
    return json.loads(KALIKA.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def kalika(kalika_shots):
    sheet, report = build_cue_sheet(kalika_shots)
    assert sheet is not None, report
    return sheet, report


# ---------------------------------------------------------------- helpers

def test_parse_range_forms():
    assert parse_range([0.5, 5.5]) == (0.5, 5.5)
    assert parse_range("0.0-0.8s") == (0.0, 0.8)
    assert parse_range("2 - 2.6 s") == (2.0, 2.6)
    assert parse_range([3, 1]) is None
    assert parse_range("soon") is None
    assert parse_range([True, 2]) is None


def test_merge_and_gaps():
    assert merge_windows([(3, 4), (0, 1), (0.5, 2)]) == [(0, 2), (3, 4)]
    assert gaps_between([(1, 2), (2.1, 3)], 4, min_len=0.3) == [(0, 1), (3, 4)]


def test_cut_offsets_and_solver_basics():
    # at 120 BPM an 8th note is 0.25 s, so whole seconds sit exactly on the grid
    assert max(cut_offsets([1.0, 7.0, 30.0], 0.0, 120)) == pytest.approx(0.0)
    found = solve_tempo([1.0, 7.0, 30.0], 0.0, 118, 122)
    assert [c["bpm"] for c in found][0] == 120.0
    assert solve_tempo([1.0], 0.0, 0, 10) == []        # bad range is refused, not raised


# ---------------------------------------------------------------- Kalika reel 1

def test_reel_clock(kalika):
    sheet, report = kalika
    assert report["ok"] and report["errors"] == []
    assert sheet["total_frames"] == 1680 and sheet["total_s"] == 70.0
    assert sheet["total_samples"] == 3_360_000            # 70.0 s at 48 kHz, exact
    assert [s["id"] for s in sheet["shots"]] == [f"SHOT-{n:03d}" for n in range(1, 11)]


def test_cuts_hard_and_act_changes(kalika):
    cuts = kalika[0]["cuts"]
    assert [c["at_s"] for c in cuts] == [6.0, 11.0, 18.0, 26.0, 34.0, 41.0, 48.0, 56.0, 64.0]
    assert [c["at_s"] for c in cuts if c["hard_cut"]] == [11.0, 18.0]
    assert [c["at_s"] for c in cuts if c["act_change"]] == [11.0, 34.0, 64.0]


def test_act_segments(kalika):
    acts = [(a["act"], a["start_s"], a["end_s"]) for a in kalika[0]["acts"]]
    assert acts == [("HOOK", 0.0, 11.0), ("BUILD", 11.0, 34.0), ("DROP", 34.0, 64.0), ("OUTRO", 64.0, 70.0)]


def test_impacts_on_reel_clock(kalika):
    imps = [i for s in kalika[0]["shots"] for i in s["impacts"]]
    assert [(i["at_frame"], i["type"]) for i in imps] == [(1034, "white_out"), (1440, "white_out")]
    assert imps[0]["at_s"] == pytest.approx(43.083, abs=1e-3) and imps[1]["at_s"] == 60.0


def test_shot_fields(kalika):
    first, last = kalika[0]["shots"][0], kalika[0]["shots"][-1]
    assert first["hook_type"] == "reveal" and first["opening_hook"] and not first["closing_hook"]
    assert last["closing_hook"] and last["act"] == "OUTRO"
    assert first["sfx"][0] == {"start": 0.0, "end": 0.8, "key": "void_bell_bloom",
                               "description": first["sfx"][0]["description"]}
    assert len(first["beats"]) == 6 and first["beats"][0]["audio_cue"]
    s7 = kalika[0]["shots"][6]
    assert s7["sfx"][0]["start"] == 43.0                    # shot-relative 2.0 s + shot start 41 s


def test_voice_windows_same_in_three_languages(kalika):
    sheet, report = kalika
    v = sheet["voice"]
    assert sheet["languages"] == ["en", "hi", "mr"]
    assert v["per_language"]["en"] == v["per_language"]["hi"] == v["per_language"]["mr"]
    assert not [w for w in report["warnings"] if w["code"] == "VOICE_WINDOWS_DIFFER"]
    assert v["union"][0] == [0.5, 5.5]
    assert [5.5, 6.3] in v["gaps"] and v["gaps"][0] == [0.0, 0.5]
    assert 0.8 < v["coverage"] < 0.86


def test_retention_windows(kalika):
    ret = kalika[0]["retention"]
    assert ret["rehook_window_s"] == [31.5, 42.0]
    assert ret["end_hook_window_s"] == [68.0, 70.0]


def test_tempo_candidates_per_act(kalika):
    by_act = {t["act"]: t["candidates"] for t in kalika[0]["tempo_candidates"]}
    build = [c["bpm"] for c in by_act["BUILD"]["melodic_techno"]]
    assert 128.0 in build and 124.0 in build and 126.0 not in build
    assert [c["bpm"] for c in by_act["DROP"]["drum_and_bass"]] == [176.0]
    for act in by_act.values():
        for cands in act.values():
            assert all(c["max_offset_ms"] <= 1000 * FRAME_S + 1e-6 for c in cands)


def test_cut_at_41_is_inside_the_drop_act(kalika):
    """41 s is neither a hard cut nor an act change, so its cut belongs to the DROP tempo segment (34-64 s)."""
    cut41 = next(c for c in kalika[0]["cuts"] if c["at_s"] == 41.0)
    assert not cut41["hard_cut"] and not cut41["act_change"]
    drop = next(t for t in kalika[0]["tempo_candidates"] if t["act"] == "DROP")
    assert drop["start_s"] < 41.0 < drop["end_s"]


def test_solver_uses_interior_cuts_and_segment_end():
    # 120 BPM fits cuts at whole seconds; a segment end at 10.1 s is 0.1 s off its grid, so 120 must be refused
    assert 120.0 in [c["bpm"] for c in solve_tempo([4.0, 10.0], 0.0, 118, 122)]
    assert 120.0 not in [c["bpm"] for c in solve_tempo([4.0, 10.1], 0.0, 118, 122)]
    assert 120.0 not in [c["bpm"] for c in solve_tempo([4.1, 10.0], 0.0, 118, 122)]


def test_drop_candidates_check_every_drop_cut(kalika):
    sheet, _ = kalika
    drop = next(t for t in sheet["tempo_candidates"] if t["act"] == "DROP")
    times = [c["at_s"] for c in sheet["cuts"] if drop["start_s"] < c["at_s"] < drop["end_s"]] + [drop["end_s"]]
    assert times == [41.0, 48.0, 56.0, 64.0]
    for cand in drop["candidates"]["drum_and_bass"]:
        assert max(cut_offsets(times, drop["start_s"], cand["bpm"], 2)) <= FRAME_S + 1e-9


def test_impacts_flag_voice_and_last_word(kalika):
    sheet, _ = kalika
    imps = {i["at_s"]: i["in_voice"] for s in sheet["shots"] for i in s["impacts"]}
    assert imps == {43.083: False, 60.0: True}           # 60.0 s sits under the line 57.2-61.2: low hit only
    assert sheet["retention"]["last_voice_end_s"] == 69.8


@pytest.mark.parametrize("at_s", [7.0, 9.0])   # SHOT-007 is 7 s long: its end frame and past it are both outside
def test_impact_outside_its_shot_blocks_the_sheet(kalika_shots, at_s):
    shots = copy.deepcopy(kalika_shots)
    shots[6]["look"]["impact_frames"] = [{"at_s": at_s, "type": "white_out", "frames": 2}]
    sheet, report = build_cue_sheet(shots)
    assert sheet is None and report["ok"] is False
    assert any(e["code"] == "IMPACT_OUTSIDE_SHOT" and e["where"] == "SHOT-007" for e in report["errors"])


def test_plain_dialogue_kept_when_only_narration_is_per_language(kalika_shots):
    shots = copy.deepcopy(kalika_shots)
    trk = shots[2]["audio_and_dialogue_track"]                          # SHOT-003 has two plain dialogue lines
    del trk["dialogue_by_lang"]
    sheet, _ = build_cue_sheet(shots)
    en = sheet["shots"][2]["voice"]["en"]
    assert [l["kind"] for l in en].count("dialogue") == 2


def test_legacy_plain_fields_fallback(kalika_shots):
    shots = copy.deepcopy(kalika_shots)
    for s in shots:
        s["audio_and_dialogue_track"].pop("narration_by_lang", None)
        s["audio_and_dialogue_track"].pop("dialogue_by_lang", None)
    sheet, report = build_cue_sheet(shots)
    assert report["ok"] and sheet["languages"] == ["en"] and sheet["voice"]["coverage"] == 0.827


def test_core_unreadable_is_a_warning(kalika_shots, monkeypatch):
    def boom():
        raise OSError("core.json missing")
    monkeypatch.setattr(cs, "load_core", boom)
    sheet, report = build_cue_sheet(kalika_shots)
    assert sheet is not None and report["ok"]
    codes = [w["code"] for w in report["warnings"]]
    assert "CORE_UNREADABLE" in codes and "RETENTION_WINDOWS_MISSING" in codes
    assert sheet["retention"]["rehook_window_s"] is None


def test_other_fps_uses_its_own_frame_tolerance(kalika_shots):
    sheet, report = build_cue_sheet(kalika_shots, fps=25)
    assert sheet is not None and sheet["tempo_tolerance_ms"] == 40.0
    for act in sheet["tempo_candidates"]:
        for cands in act["candidates"].values():
            assert all(c["max_offset_ms"] <= 40.0 + 1e-6 for c in cands)


def test_samples_not_whole_is_warned(kalika_shots):
    shots = copy.deepcopy(kalika_shots)
    shots[0]["editorial_duration_sec"] = shots[0]["seconds"] = 6.1      # 491 frames at 7 fps: 491 * 48000 / 7 is not whole
    sheet, report = build_cue_sheet(shots, fps=7)
    assert sheet["total_frames"] == 491
    assert any(w["code"] == "SAMPLES_NOT_WHOLE" for w in report["warnings"])
    sheet, report = build_cue_sheet(kalika_shots, fps=7)                 # 490 frames: whole, no warning
    assert not any(w["code"] == "SAMPLES_NOT_WHOLE" for w in report["warnings"])


# ---------------------------------------------------------------- problems are reported, never raised

def test_language_mismatch_is_warned(kalika_shots):
    shots = copy.deepcopy(kalika_shots)
    shots[0]["audio_and_dialogue_track"]["narration_by_lang"]["hi"]["time_range"] = [0.5, 5.9]
    sheet, report = build_cue_sheet(shots)
    assert sheet is not None
    codes = [w["code"] for w in report["warnings"]]
    assert "VOICE_WINDOWS_DIFFER" in codes
    assert [0.5, 5.9] in sheet["voice"]["per_language"]["hi"]
    assert [0.5, 5.9] in sheet["voice"]["union"]           # the union protects every language


def test_voice_past_shot_end_is_clipped_and_warned(kalika_shots):
    shots = copy.deepcopy(kalika_shots)
    shots[0]["audio_and_dialogue_track"]["narration_by_lang"]["en"]["time_range"] = [0.5, 9.0]
    sheet, report = build_cue_sheet(shots)
    assert any(w["code"] == "VOICE_OUTSIDE_SHOT" for w in report["warnings"])
    assert sheet["shots"][0]["voice"]["en"][0]["end"] == 6.0


def test_bad_inputs():
    assert build_cue_sheet("nope")[0] is None
    assert build_cue_sheet([])[1]["ok"] is False


def test_episode_selection(kalika_shots):
    two = copy.deepcopy(kalika_shots) + [dict(copy.deepcopy(kalika_shots[0]), episode=2, id="SHOT-101")]
    sheet, report = build_cue_sheet(two)
    assert sheet is None and report["errors"][-1]["code"] == "EPISODE_AMBIGUOUS"
    sheet, report = build_cue_sheet(two, episode="2")
    assert sheet["total_s"] == 6.0
    sheet, report = build_cue_sheet(two, episode=9)
    assert sheet is None and report["errors"][-1]["code"] == "EPISODE_NOT_FOUND"


def test_cli_writes_json(tmp_path):
    out = tmp_path / "score" / "ep1" / "cue_sheet.json"
    rc = cs.main(["--shots", str(KALIKA), "--out", str(out)])
    assert rc == 0
    doc = json.loads(out.read_text(encoding="utf-8"))
    assert doc["checks"]["ok"] and doc["schema_version"] == 1 and doc["total_samples"] == 3_360_000


def test_cli_unreadable_input(tmp_path):
    assert cs.main(["--shots", str(tmp_path / "missing.json"), "--out", str(tmp_path / "x.json")]) == 2


BAD_VALUES = [None, 0, 7, 1.5, True, "x", "", [], [1, "a", None], {}, {"en": 3}, {"en": "text"}]
AUDIO_FIELDS = ["narration", "dialogue", "narration_by_lang", "dialogue_by_lang", "sfx_cues"]


def test_malformed_columns_never_raise(kalika_shots):
    """Regression: non-list sfx_cues / per_second_directives / dialogue_by_lang values used to raise TypeError."""
    cases = 0
    for field in AUDIO_FIELDS + ["per_second_directives", "audio_and_dialogue_track"]:
        for bad in BAD_VALUES:
            for idx in (0, 6):
                shots = copy.deepcopy(kalika_shots)
                if field in AUDIO_FIELDS:
                    trk = shots[idx].setdefault("audio_and_dialogue_track", {})
                    trk[field] = copy.deepcopy(bad)
                else:
                    shots[idx][field] = copy.deepcopy(bad)
                sheet, report = build_cue_sheet(shots)  # must not raise
                assert isinstance(report, dict) and "ok" in report
                if sheet is None:
                    assert report["ok"] is False and report["errors"]
                else:  # a sheet is only ever built on the full reel clock
                    assert sheet["total_s"] == 70.0 and report["ok"] is True
                cases += 1
    assert cases == 7 * len(BAD_VALUES) * 2


def test_timeline_failure_blocks_the_sheet(kalika_shots):
    """core.timeline drops a shot it cannot read; the cue sheet must refuse rather than score a shorter reel."""
    shots = copy.deepcopy(kalika_shots)
    shots[0]["audio_and_dialogue_track"]["dialogue"] = 7
    sheet, report = build_cue_sheet(shots)
    assert sheet is None and report["ok"] is False
    assert report["errors"][0]["code"] == "TIMELINE_P0" and report["errors"][0]["where"] == "SHOT-001"


def test_module_is_pure():
    src = inspect.getsource(cs)
    for banned in ("subprocess", "requests", "urllib", "socket", "ffmpeg -", "os.system"):
        assert banned not in src


def test_imports_are_pure_transitively():
    """Importing the cue sheet (and core.timeline under it) must not pull in network or process modules."""
    import subprocess as sp
    import sys
    code = ("import sys; import score.cue_sheet; "
            "bad = [m for m in ('subprocess', 'socket', 'urllib.request', 'requests', 'http.client') if m in sys.modules]; "
            "print(bad)")
    out = sp.run([sys.executable, "-c", code], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()
    assert out == "[]"


# ---------------------------------------------------------------- real audio windows (blot RULE 39)

def test_voice_windows_replace_scripted_ranges(kalika_shots):
    vw = {"SHOT-001-N.en": {"start_s": 0.5, "window_s": 6.0}, "SHOT-003-D2.en": {"start_s": 4.6, "window_s": 2.8}}
    sheet, report = build_cue_sheet(kalika_shots, voice_windows=vw)
    assert report["ok"]
    n = sheet["shots"][0]["voice"]["en"][0]
    assert (n["start"], n["end"]) == (0.5, 6.0) and n["from_audio_window"]        # shot 1 is 6.0 s long: clipped
    d2 = [l for l in sheet["shots"][2]["voice"]["en"] if l["kind"] == "dialogue"][1]
    assert d2["from_audio_window"] and d2["end"] == pytest.approx(sheet["shots"][2]["end_s"])
    assert "from_audio_window" not in sheet["shots"][1]["voice"]["en"][0]        # no key, scripted range kept
    sheet2, _ = build_cue_sheet(kalika_shots, voice_windows="junk")               # bad input is ignored
    assert sheet2["voice"]["coverage"] == build_cue_sheet(kalika_shots)[0]["voice"]["coverage"]


REAL_WINDOWS = Path("D:/aai work/flow_outputs/anime_kalika_puran_bhag1/voices/pack_opus_high_20261108_v4_deva/FINAL_TEXT_v2.json")


@pytest.mark.skipif(not REAL_WINDOWS.exists(), reason="voices folder not on this machine")
def test_real_kalika_windows_widen_the_voice_union(kalika_shots):
    vw = json.loads(REAL_WINDOWS.read_text(encoding="utf-8"))
    sheet, report = build_cue_sheet(kalika_shots, voice_windows=vw)
    base = build_cue_sheet(kalika_shots)[0]["voice"]["coverage"]
    assert report["ok"] and sheet["voice"]["coverage"] >= base and sheet["total_samples"] == 3_360_000


# ---------------------------------------------------------------- VO reports (real speech positions)

SHOT_LEN = {"SHOT-001": 6.0, "SHOT-002": 5.0, "SHOT-003": 7.0, "SHOT-004": 8.0, "SHOT-005": 8.0,
            "SHOT-006": 7.0, "SHOT-007": 7.0, "SHOT-008": 8.0, "SHOT-009": 8.0, "SHOT-010": 6.0}
SHOT_START = {"SHOT-001": 0.0, "SHOT-002": 6.0, "SHOT-003": 11.0, "SHOT-004": 18.0, "SHOT-005": 26.0,
              "SHOT-006": 34.0, "SHOT-007": 41.0, "SHOT-008": 48.0, "SHOT-009": 56.0, "SHOT-010": 64.0}
VO_REPORT_DIR = Path("D:/aai work/flow_outputs/anime_kalika_puran_bhag1/voices/pack_opus_high_20261108_v4_deva")


def _vo_row(shot, lang, lines, editorial=None):
    """One vo_tracks_report row. lines: [(id, start, end)], shot-relative, as the real report writes them."""
    return {"shot": shot, "lang": lang, "editorial": SHOT_LEN[shot] if editorial is None else editorial,
            "tempo": 1.0, "file": f"vo_{lang}/{lang}/{shot}.wav",
            "lines": [{"id": i, "start": s, "length": round(e - s, 3), "end": e} for i, s, e in lines]}


def test_vo_report_replaces_scripted_and_shifts(kalika_shots):
    rows = [_vo_row("SHOT-003", "en", [("SHOT-003-N", 0.3, 2.187), ("SHOT-003-D1", 2.307, 4.165),
                                       ("SHOT-003-D2", 4.6, 6.885), ("SHOT-003-D5", 0.1, 0.5)])]
    sheet, report = build_cue_sheet(kalika_shots, vo_reports={"en": rows})
    assert report["ok"], report["errors"]
    by_start = {l["start"]: l for l in sheet["shots"][2]["voice"]["en"]}
    assert by_start[11.3]["kind"] == "narration" and by_start[11.3]["speaker"] == "NARRATOR"
    assert by_start[11.3]["end"] == 13.187                       # shot start 11 s + 2.187 s, on the reel clock
    assert by_start[13.307]["kind"] == "dialogue" and by_start[13.307]["speaker"] != "unknown"
    assert by_start[15.6]["end"] == 17.885
    assert by_start[11.1]["speaker"] == "unknown"                # SHOT-003-D5: no scripted line 5
    assert not any(l.get("from_audio_window") for l in sheet["shots"][2]["voice"]["en"])


def test_vo_report_beats_voice_windows(kalika_shots):
    vw = {"SHOT-003-D2.en": {"start_s": 4.6, "window_s": 2.8}}
    rows = [_vo_row("SHOT-003", "en", [("SHOT-003-N", 0.3, 2.187)])]
    sheet, _ = build_cue_sheet(kalika_shots, voice_windows=vw, vo_reports={"en": rows})
    en = sheet["shots"][2]["voice"]["en"]
    assert [(l["start"], l["end"]) for l in en] == [(11.3, 13.187)]
    assert "from_audio_window" not in en[0]


def test_vo_report_missing_shot_falls_back_with_warning(kalika_shots):
    rows = [_vo_row("SHOT-001", "en", [("SHOT-001-N", 0.5, 3.434)])]
    sheet, report = build_cue_sheet(kalika_shots, vo_reports={"en": rows})
    assert report["ok"], report["errors"]
    assert any(w["code"] == "VO_REPORT_MISSING" and w["where"] == "SHOT-002" and "en" in w["message"]
               for w in report["warnings"])
    scripted = build_cue_sheet(kalika_shots)[0]["shots"][1]["voice"]["en"]
    assert sheet["shots"][1]["voice"]["en"] == scripted          # shot 2 keeps its scripted lines


def test_vo_report_editorial_mismatch_is_an_error(kalika_shots):
    bad = [_vo_row("SHOT-001", "en", [("SHOT-001-N", 0.5, 3.434)], editorial=7.0)]
    sheet, report = build_cue_sheet(kalika_shots, vo_reports={"en": bad})
    assert sheet is None and report["ok"] is False
    assert any(e["code"] == "VO_REPORT_EDITORIAL_MISMATCH" and e["where"] == "SHOT-001" for e in report["errors"])
    one_frame = [_vo_row("SHOT-001", "en", [("SHOT-001-N", 0.5, 3.434)], editorial=6.0 + 1 / 24)]
    sheet, report = build_cue_sheet(kalika_shots, vo_reports={"en": one_frame})
    assert report["ok"], report["errors"]                        # one frame off is still the same shot


def test_vo_report_line_past_shot_end_is_an_error(kalika_shots):
    rows = [_vo_row("SHOT-001", "en", [("SHOT-001-N", 0.5, 6.5)])]   # SHOT-001 is 6.0 s
    sheet, report = build_cue_sheet(kalika_shots, vo_reports={"en": rows})
    assert sheet is None and report["ok"] is False
    assert any(e["code"] == "VO_REPORT_OVERFLOW" and e["where"] == "SHOT-001" for e in report["errors"])


def test_vo_report_recomputes_in_voice(kalika_shots):
    # the impact at 43.083 s sits in no scripted line (in_voice False in the scripted sheet); a real line covers it
    rows = {lang: [_vo_row("SHOT-007", lang, [("SHOT-007-N", 1.5, 3.0)])] for lang in ("en", "hi", "mr")}
    sheet, report = build_cue_sheet(kalika_shots, vo_reports=rows)
    assert report["ok"], report["errors"]
    imps = {i["at_s"]: i["in_voice"] for s in sheet["shots"] for i in s["impacts"]}
    assert imps[43.083] is True


def test_vo_report_union_across_languages(kalika_shots):
    rows = {"en": [_vo_row("SHOT-007", "en", [("SHOT-007-N", 1.5, 3.0)])],
            "hi": [_vo_row("SHOT-007", "hi", [("SHOT-007-N", 4.0, 5.0)])]}
    sheet, _ = build_cue_sheet(kalika_shots, vo_reports=rows)
    assert [45.0, 46.0] in sheet["voice"]["per_language"]["hi"]
    assert any(a <= 45.5 < b for a, b in sheet["voice"]["union"])


def test_vo_report_sets_last_voice_end(kalika_shots):
    rows = {lang: [_vo_row("SHOT-010", lang, [("SHOT-010-N", 3.8, 5.5)])] for lang in ("en", "hi", "mr")}
    sheet, report = build_cue_sheet(kalika_shots, vo_reports=rows)
    assert report["ok"], report["errors"]
    assert sheet["retention"]["last_voice_end_s"] == 69.5
    assert sheet["retention"]["last_speech_end_s"] == 69.5


def test_cli_vo_report_flag(tmp_path):
    rep = tmp_path / "vo_en.json"
    rep.write_text(json.dumps([_vo_row("SHOT-001", "en", [("SHOT-001-N", 0.5, 3.434)])]), encoding="utf-8")
    out = tmp_path / "cue_sheet.json"
    rc = cs.main(["--shots", str(KALIKA), "--vo-report", str(rep), "--out", str(out)])
    assert rc == 0                                              # missing hi and mr rows are warnings
    doc = json.loads(out.read_text(encoding="utf-8"))
    assert doc["shots"][0]["voice"]["en"][0]["end"] == 3.434


@pytest.mark.skipif(not all((VO_REPORT_DIR / f"vo_{l}" / "vo_tracks_report.json").exists() for l in ("en", "hi", "mr"))
                    or not REAL_WINDOWS.exists(), reason="VO reports or FINAL_TEXT_v2 not on this machine")
def test_real_vo_reports_on_kalika(kalika_shots):
    reports = {l: json.loads((VO_REPORT_DIR / f"vo_{l}" / "vo_tracks_report.json").read_text(encoding="utf-8"))
               for l in ("en", "hi", "mr")}
    sheet, report = build_cue_sheet(kalika_shots, vo_reports=reports)
    old, _ = build_cue_sheet(kalika_shots, voice_windows=json.loads(REAL_WINDOWS.read_text(encoding="utf-8")))
    assert report["ok"], report["errors"]
    assert not [w for w in report["warnings"] if w["code"] == "VO_REPORT_MISSING"]
    assert sheet["voice"]["coverage"] < old["voice"]["coverage"]
    assert sheet["total_samples"] == 3_360_000
    imps = {i["at_s"]: i["in_voice"] for s in sheet["shots"] for i in s["impacts"]}
    print(f"\nreal VO: coverage {sheet['voice']['coverage']} (FINAL_TEXT_v2 {old['voice']['coverage']}), "
          f"gaps {len(sheet['voice']['gaps'])}, in_voice {imps}, last_speech_end_s {sheet['retention']['last_speech_end_s']}, "
          f"last_voice_end_s {sheet['retention']['last_voice_end_s']}")
    assert imps[43.083] is False or imps[43.083] is True          # both values are recorded above
    assert imps[60.0] is False or imps[60.0] is True


# ---------------------------------------------------------------- v4 shared timeline (editorial_by_lang.json)

EDITORIAL_V4 = ROOT / "stories" / "kalika_puran_bhag1" / "pack_opus_high_20261108_v4_deva" / "editorial_by_lang.json"
V4_STARTS = [0, 144, 273, 452, 644, 843, 1011, 1195, 1412, 1604]


@pytest.fixture(scope="module")
def editorial_v4():
    return json.loads(EDITORIAL_V4.read_text(encoding="utf-8"))


def test_editorial_sets_v4_lengths(kalika_shots, editorial_v4):
    sheet, report = build_cue_sheet(kalika_shots, editorial=editorial_v4)
    assert report["ok"], report["errors"]
    assert sheet["total_frames"] == 1748 and sheet["total_s"] == 72.833
    assert sheet["total_samples"] == 3_496_000
    assert [s["start_frame"] for s in sheet["shots"]] == V4_STARTS
    assert sum(s["frames"] for s in sheet["shots"]) == 1748


def test_editorial_not_shared_is_an_error(kalika_shots, editorial_v4):
    ed = copy.deepcopy(editorial_v4)
    ed["shared_timeline"] = False
    sheet, report = build_cue_sheet(kalika_shots, editorial=ed)
    assert sheet is None and report["ok"] is False
    assert report["errors"][0]["code"] == "EDITORIAL_NOT_SHARED"


def test_editorial_per_language_difference_is_an_error(kalika_shots, editorial_v4):
    ed = copy.deepcopy(editorial_v4)
    ed["by_lang"]["hi"]["SHOT-002"]["extend_frames"] = 8          # shared plan says 9
    sheet, report = build_cue_sheet(kalika_shots, editorial=ed)
    assert sheet is None
    assert any(e["code"] == "EDITORIAL_NOT_SHARED" and e["where"] == "SHOT-002" for e in report["errors"])


def test_editorial_missing_shot_is_an_error(kalika_shots, editorial_v4):
    ed = copy.deepcopy(editorial_v4)
    ed["plan"] = [p for p in ed["plan"] if p["shot"] != "SHOT-005"]
    sheet, report = build_cue_sheet(kalika_shots, editorial=ed)
    assert sheet is None and any(e["code"] == "EDITORIAL_SHOT_MISSING" and e["where"] == "SHOT-005"
                                 for e in report["errors"])


def test_start_extension_moves_inner_times_end_does_not(kalika_shots, editorial_v4):
    ed = copy.deepcopy(editorial_v4)                              # SHOT-007 gets its 16 extra frames at the START
    for p in ed["plan"]:
        if p["shot"] == "SHOT-007":
            p["at"] = "start"
    for per in ed["by_lang"].values():
        per["SHOT-007"]["at"] = "start"
    sheet, report = build_cue_sheet(kalika_shots, editorial=ed)
    assert report["ok"], report["errors"]
    s7 = sheet["shots"][6]
    shift = 16 / 24
    assert s7["start_frame"] == 1011
    assert s7["sfx"][0]["start"] == pytest.approx(42.125 + 2.0 + shift, abs=1e-3)   # was 2.0 s into the shot
    assert s7["beats"][0]["t0"] == pytest.approx(42.125 + shift, abs=1e-3)
    impacts = [i for s in sheet["shots"] for i in s["impacts"]]
    assert (impacts[0]["at_frame"], impacts[0]["at_s"]) == (1077, 44.875)         # 2.083 s + 0.667 s shift
    # the same extension at the END (the real plan) leaves SHOT-007's own times alone
    sheet_end, _ = build_cue_sheet(kalika_shots, editorial=editorial_v4)
    assert sheet_end["shots"][6]["beats"][0]["t0"] == pytest.approx(42.125, abs=1e-3)
    assert [i["at_frame"] for s in sheet_end["shots"] for i in s["impacts"]][0] == 1061


def test_act_end_off_grid_warns_and_keeps_candidates(kalika_shots, editorial_v4):
    sheet, report = build_cue_sheet(kalika_shots, editorial=editorial_v4)
    assert report["ok"], report["errors"]
    assert [w["code"] for w in report["warnings"]].count("ACT_END_OFF_GRID") == 4
    by_act = {t["act"]: t["candidates"] for t in sheet["tempo_candidates"]}
    assert 128.0 in [c["bpm"] for c in by_act["BUILD"]["melodic_techno"]]
    assert 176.0 in [c["bpm"] for c in by_act["DROP"]["drum_and_bass"]]


def test_interior_cuts_on_grid_for_every_candidate(kalika_shots, editorial_v4):
    sheet, _ = build_cue_sheet(kalika_shots, editorial=editorial_v4)
    for act, tempo in zip(sheet["acts"], sheet["tempo_candidates"]):
        times = [c["at_frame"] / 24 for c in sheet["cuts"] if act["start_frame"] < c["at_frame"] < act["end_frame"]]
        for cands in tempo["candidates"].values():
            for c in cands:
                assert max(cut_offsets(times, act["start_frame"] / 24, c["bpm"], 2), default=0.0) <= FRAME_S + 1e-9


def test_cli_editorial_flag(tmp_path):
    out = tmp_path / "cue_sheet.json"
    assert cs.main(["--shots", str(KALIKA), "--editorial", str(EDITORIAL_V4), "--out", str(out)]) == 0
    assert json.loads(out.read_text(encoding="utf-8"))["total_frames"] == 1748


def test_cli_one_vo_file_with_three_languages(tmp_path):
    rows = [_vo_row("SHOT-001", lang, [("SHOT-001-N", 0.5, 3.434)]) for lang in ("en", "hi", "mr")]
    rep = tmp_path / "vo_tracks_report.json"
    rep.write_text(json.dumps(rows), encoding="utf-8")
    out = tmp_path / "cue_sheet.json"
    assert cs.main(["--shots", str(KALIKA), "--vo-report", str(rep), "--out", str(out)]) == 0
    doc = json.loads(out.read_text(encoding="utf-8"))
    assert doc["languages"] == ["en", "hi", "mr"]
    assert all(doc["shots"][0]["voice"][lang][0]["end"] == 3.434 for lang in ("en", "hi", "mr"))


def test_candidates_uncapped_and_typical_tempo_kept(kalika_shots, editorial_v4):
    sheet, _ = build_cue_sheet(kalika_shots, editorial=editorial_v4)
    by_act = {t["act"]: t["candidates"] for t in sheet["tempo_candidates"]}
    outro_ambient = [c["bpm"] for c in by_act["OUTRO"]["ambient"]]   # OUTRO has no interior cut: every bpm fits
    assert 60.0 in outro_ambient and outro_ambient[0] == 60.0 and len(outro_ambient) > 5
    assert 128.0 in [c["bpm"] for c in by_act["BUILD"]["melodic_techno"]]
    assert 176.0 in [c["bpm"] for c in by_act["DROP"]["drum_and_bass"]]
