"""W-02 offline tests for voice_cast: preflight.json, pilot.json, the run gate before any paid call, hard names, WAV export without atempo.
No network: GET and POST are fakes, urlopen is replaced by a counter, ffmpeg is faked except in the one skip-if-no-ffmpeg trim test."""
import hashlib
import math
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import voice_cast as v  # noqa: E402

HI_NAME = "मन्मथ"


def shot(sid, narration, dialogue):
    nb = {lg: {"text": (narration or {}).get(lg, ""), "time_range": [0.0, 2.0]} for lg in v.LANGS}
    db = {lg: [] for lg in v.LANGS}
    if dialogue:
        speaker, texts = dialogue
        for lg in v.LANGS:
            db[lg].append({"speaker": "CHAR-" + speaker, "text": texts[lg], "time_range": [0.0, 2.0]})
    return {"id": sid, "audio_and_dialogue_track": {"narration_by_lang": nb, "dialogue_by_lang": db}}


def write_pack(tmp_path):
    """Reel-2 style pack: SHOT-001 narration; SHOT-002 narration + dialogue D1 (BRAHMA, Hindi text holds the hard name)."""
    pack = tmp_path / "pack"
    pack.mkdir()
    shots = [
        shot("SHOT-001", {"en": "Dawn breaks.", "hi": "सुबह होती है।", "mr": "पहाट होते."}, None),
        shot("SHOT-002", {"en": "Night falls.", "hi": "रात होती है।", "mr": "रात्र होते."},
             ("BRAHMA", {"en": "My name is Manmatha.", "hi": "मेरा नाम " + HI_NAME + " है।", "mr": "माझे नाव मन्मथ आहे."})),
    ]
    (pack / "shots.json").write_text(json.dumps(shots, ensure_ascii=False), encoding="utf-8")
    cast = {lg: {"NARRATOR": f"vid-{lg}-N", "BRAHMA": f"vid-{lg}-B"} for lg in v.LANGS}
    cast_path = tmp_path / "voices_cast.json"
    cast_path.write_text(json.dumps(cast), encoding="utf-8")
    return pack, cast_path, cast


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def fake_get(missing=(), hi_models=("eleven_v4",), rate=1.0, empty_en=False):
    def get(method, path, key, body=None):
        vid = path.rsplit("/", 1)[1]
        if vid in missing:
            raise RuntimeError("HTTP 404: voice not found")
        lang = vid.split("-")[1]
        if lang == "hi":
            langs = [{"language": "hi", "model_id": m} for m in hi_models]
        elif lang == "en" and empty_en:
            langs = []
        else:
            langs = [{"language": lg, "model_id": "eleven_v4"} for lg in v.LANGS]
        info = {"voice_id": vid, "verified_languages": langs, "sharing": {"rate": rate}}
        return json.dumps(info).encode(), {}
    return get


def fake_post(calls):
    def post(method, path, key, body=None):
        calls.append(path)
        return b"audio", {"character-cost": str(len(body["text"]))}
    return post


def write_pf(out, pf):
    out.mkdir(parents=True, exist_ok=True)
    (out / "preflight.json").write_text(json.dumps(pf, ensure_ascii=False), encoding="utf-8")


def jobs_for(pack, cast, ids):
    plan = v.load_plan(pack)
    return v.build_jobs(plan, ids, cast, "eleven_v4", cast.get("_models"))


@pytest.fixture
def no_net(monkeypatch, tmp_path):
    """Any real HTTP call fails the test; the ledger lives in tmp_path."""
    calls = []

    def fake_urlopen(*a, **k):
        calls.append(a)
        raise AssertionError("network call attempted")
    monkeypatch.setattr(v.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(v, "api_key", lambda: "k" * 20)
    monkeypatch.setattr(v, "LEDGER", tmp_path / "ledger.jsonl")
    return calls


def run_cli(monkeypatch, argv):
    monkeypatch.setattr(sys, "argv", ["voice_cast.py"] + argv)
    return v.main()


# ---- preflight -------------------------------------------------------------------------------

def test_preflight_missing_voice_blocks_run(tmp_path, monkeypatch, no_net):
    pack, cast_path, cast = write_pack(tmp_path)
    out = tmp_path / "out"
    pf = v.preflight(cast, sha(pack / "shots.json"), sha(cast_path), "k" * 20, get=fake_get(missing=("vid-hi-B",)))
    assert pf["ok"] is False
    assert any(r["voice_id"] == "vid-hi-B" and r["present"] is False for r in pf["voices"])
    write_pf(out, pf)
    with pytest.raises(SystemExit):
        run_cli(monkeypatch, ["run", "--lines", "SHOT-001-N,SHOT-002-D1", "--pack", str(pack), "--voices", str(cast_path),
                              "--out", str(out), "--allow-paid", "--pilot"])
    assert no_net == []                                  # no POST, no GET to ElevenLabs
    assert not (tmp_path / "ledger.jsonl").exists()      # nothing reserved


def test_preflight_model_not_verified(tmp_path):
    pack, cast_path, cast = write_pack(tmp_path)
    pf = v.preflight(cast, sha(pack / "shots.json"), sha(cast_path), "k" * 20, get=fake_get(hi_models=("eleven_multilingual_v2",)))
    hi = [r for r in pf["voices"] if r["lang"] == "hi"]
    assert hi and all(r["verified"] is False for r in hi)
    assert pf["ok"] is False


def test_preflight_ok_when_verified_and_warnings_do_not_block(tmp_path):
    pack, cast_path, cast = write_pack(tmp_path)
    pf = v.preflight(cast, "s", "c", "k" * 20, get=fake_get())
    assert pf["ok"] is True and all(r["warnings"] == [] for r in pf["voices"])
    pf2 = v.preflight(cast, "s", "c", "k" * 20, get=fake_get(rate=2.5, empty_en=True))
    en = [r for r in pf2["voices"] if r["lang"] == "en"]
    assert all("no verified_languages" in r["warnings"] and r["verified"] for r in en)
    assert all("rate x2.5" in r["warnings"] for r in pf2["voices"])
    assert pf2["ok"] is True


def test_preflight_skips_underscore_keys(tmp_path):
    pack, cast_path, cast = write_pack(tmp_path)
    cast["_models"] = {"hi": {"BRAHMA": "eleven_multilingual_v2"}}
    seen = []

    def get(method, path, key, body=None):
        seen.append(path)
        return fake_get()(method, path, key, body)
    v.preflight(cast, "s", "c", "k" * 20, get=get)
    assert len(seen) == 6 and not any("_models" in p for p in seen)


# ---- the gate: require_records --------------------------------------------------------------

def test_run_without_pilot_exits_before_reserve(tmp_path, monkeypatch, no_net):
    pack, cast_path, cast = write_pack(tmp_path)
    out = tmp_path / "out"
    write_pf(out, v.preflight(cast, sha(pack / "shots.json"), sha(cast_path), "k" * 20, get=fake_get()))
    with pytest.raises(SystemExit):
        run_cli(monkeypatch, ["run", "--lines", "SHOT-001-N,SHOT-002-D1", "--pack", str(pack), "--voices", str(cast_path),
                              "--out", str(out), "--allow-paid"])
    assert not (tmp_path / "ledger.jsonl").exists()
    assert no_net == []


def test_pilot_mode_one_line_per_voice(tmp_path):
    pack, cast_path, cast = write_pack(tmp_path)
    out = tmp_path / "out"
    s, c = sha(pack / "shots.json"), sha(cast_path)
    write_pf(out, v.preflight(cast, s, c, "k" * 20, get=fake_get()))
    one = jobs_for(pack, cast, ["SHOT-001-N", "SHOT-002-D1"])          # NARRATOR once, BRAHMA once
    v.require_records(out, s, c, one, True)                            # passes
    two = jobs_for(pack, cast, ["SHOT-001-N", "SHOT-002-N"])          # NARRATOR twice
    with pytest.raises(SystemExit):
        v.require_records(out, s, c, two, True)


def test_full_run_needs_every_voice_heard(tmp_path):
    pack, cast_path, cast = write_pack(tmp_path)
    out = tmp_path / "out"
    s, c = sha(pack / "shots.json"), sha(cast_path)
    write_pf(out, v.preflight(cast, s, c, "k" * 20, get=fake_get()))
    ids = ["SHOT-001-N", "SHOT-002-N", "SHOT-002-D1"]
    jobs = jobs_for(pack, cast, ids)
    heard = {f"{lg}/{vc}": {"owner_heard": True} for lg in v.LANGS for vc in ("NARRATOR", "BRAHMA")}
    (out / "pilot.json").write_text(json.dumps({"script_sha256": s, "cast_sha256": c, "voices": heard}), encoding="utf-8")
    v.require_records(out, s, c, jobs, False)                          # all heard: passes
    heard["mr/BRAHMA"]["owner_heard"] = False
    (out / "pilot.json").write_text(json.dumps({"script_sha256": s, "cast_sha256": c, "voices": heard}), encoding="utf-8")
    with pytest.raises(SystemExit):
        v.require_records(out, s, c, jobs, False)
    (out / "pilot.json").write_text(json.dumps({"script_sha256": "other", "cast_sha256": c, "voices": heard}), encoding="utf-8")
    with pytest.raises(SystemExit):
        v.require_records(out, s, c, jobs, False)                      # pilot for another script


def test_preflight_for_other_cast_is_refused(tmp_path):
    pack, cast_path, cast = write_pack(tmp_path)
    out = tmp_path / "out"
    s, c = sha(pack / "shots.json"), sha(cast_path)
    write_pf(out, v.preflight(cast, s, c, "k" * 20, get=fake_get()))
    with pytest.raises(SystemExit):
        v.require_records(out, s, "other-cast-sha", jobs_for(pack, cast, ["SHOT-001-N"]), True)


# ---- pilot record and hard names -------------------------------------------------------------

def run_all(tmp_path, pack, cast):
    jobs = jobs_for(pack, cast, ["SHOT-001-N", "SHOT-002-N", "SHOT-002-D1"])
    calls = []
    return v.run(jobs, tmp_path / "out", 10_000, "k" * 20, post=fake_post(calls),
                 ledger=v.Ledger(tmp_path / "l.jsonl", 10_000), probe=lambda p: 2.0)


def test_pilot_record_marks_heard_and_names(tmp_path):
    pack, cast_path, cast = write_pack(tmp_path)
    man = run_all(tmp_path, pack, cast)
    pl = v.pilot_record(man, "s", "c", ["en/NARRATOR"], ["hi/BRAHMA"])
    assert pl["voices"]["en/NARRATOR"]["owner_heard"] is True and pl["voices"]["en/NARRATOR"]["hard_names_ok"] is False
    assert pl["voices"]["hi/BRAHMA"]["hard_names_ok"] is True and pl["voices"]["hi/BRAHMA"]["owner_heard"] is False
    row = pl["voices"]["hi/BRAHMA"]
    assert row["seconds"] == 2.0 and row["s_per_char"] == round(2.0 / row["chars"], 4) and row["chars"] > 0
    with pytest.raises(SystemExit):
        v.pilot_record(man, "s", "c", ["xx/NOBODY"], [])               # a key that is not in the manifest


def test_hard_name_unapproved_is_a_problem(tmp_path):
    pack, cast_path, cast = write_pack(tmp_path)
    man = run_all(tmp_path, pack, cast)
    plan = v.load_plan(pack)
    res = v.measured(man, plan, "s", "eleven_v4", {"hi": [HI_NAME]}, None)
    assert any("hard name " + HI_NAME in p and p.startswith("SHOT-002-D1") for p in res["problems"])
    ok = {"voices": {"hi/BRAHMA": {"owner_heard": True, "hard_names_ok": True}}}
    res2 = v.measured(man, plan, "s", "eleven_v4", {"hi": [HI_NAME]}, ok)
    assert not any("hard name" in p for p in res2["problems"])


# ---- export: real WAV, no speed-up ------------------------------------------------------------

def test_export_rejects_mp3_bytes(tmp_path, monkeypatch):
    def fake_ffmpeg(args, **kw):
        Path(args[-1]).parent.mkdir(parents=True, exist_ok=True)
        Path(args[-1]).write_bytes(b"ID3" + b"\0" * 20)
    monkeypatch.setattr(v.subprocess, "run", fake_ffmpeg)
    man = {"lines": [{"id": "L.en", "line": "L", "lang": "en", "file": "mp3/en/L.en.mp3", "ok": True}]}
    with pytest.raises(ValueError):
        v.export_wavs(man, tmp_path, tmp_path / "w", "m")


def test_export_trims_no_atempo(tmp_path):
    if not shutil.which("ffmpeg"):
        pytest.skip("no ffmpeg")
    src = tmp_path / "mp3" / "en" / "L.en.mp3"
    src.parent.mkdir(parents=True)
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "sine=frequency=440:duration=1", "-af",
                    "adelay=300|300,apad=pad_dur=0.3", str(src)], check=True)
    man = {"lines": [{"id": "L.en", "line": "L", "lang": "en", "file": "mp3/en/L.en.mp3", "ok": True}]}
    rep = []
    assert v.export_wavs(man, tmp_path, tmp_path / "w", "m", slots={"L": 0.9}, report=rep) == 1
    r = rep[0]
    assert 0.95 < r["seconds_trimmed"] < 1.1
    assert r["seconds_final"] >= r["seconds_trimmed"]                       # no speed-up
    assert r["seconds_final"] <= r["seconds_trimmed"] + 0.17                # at most 80 ms lead + 60 ms tail + slack
    assert r["verdict"].startswith("longer than")
    pack, _, _ = write_pack(tmp_path)
    slots = v.load_slots(pack)
    assert slots["SHOT-001-N"] == 2.0 and slots["SHOT-002-D1"] == 2.0      # scripted windows, no FINAL_TEXT_v2 read here


def test_export_writes_tmp_then_replaces(tmp_path, monkeypatch):
    """The edged audio goes to a temp WAV in the same folder, then replaces dst (old code wrote dst directly)."""
    real_write = v.audio_edge.write_wav_mono
    targets = []

    def fake_ffmpeg(args, **kw):
        Path(args[-1]).parent.mkdir(parents=True, exist_ok=True)
        tone = [0.5 * math.sin(2 * math.pi * 440 * i / 44100) for i in range(4410)]
        real_write(args[-1], tone, 44100)                         # a real 0.1 s mono WAV as ffmpeg output

    def recording_write(path, samples, sr):
        targets.append(Path(path))
        real_write(path, samples, sr)
    monkeypatch.setattr(v.subprocess, "run", fake_ffmpeg)
    monkeypatch.setattr(v.audio_edge, "write_wav_mono", recording_write)
    man = {"lines": [{"id": "L.en", "line": "L", "lang": "en", "file": "mp3/en/L.en.mp3", "ok": True}]}
    wav_dir = tmp_path / "w"
    assert v.export_wavs(man, tmp_path, wav_dir, "m") == 1
    dst = wav_dir / "wav" / "en" / v.wav_name("L", "en")
    assert len(targets) == 1 and targets[0] != dst and targets[0].parent == dst.parent
    assert not targets[0].exists()                                # replaced away, nothing left behind
    assert v.require_wav(dst) == dst


def test_check_disk_floor(tmp_path):
    v.check_disk(tmp_path, min_free=1)                                      # passes
    with pytest.raises(SystemExit):
        v.check_disk(tmp_path, min_free=1 << 62)                            # more than any disk has


def test_no_atempo_in_source():
    text = Path(v.__file__).read_text(encoding="utf-8")
    assert "atempo" not in text and "MAX_TEMPO" not in text
