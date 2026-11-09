"""Offline tests for voice_cast (copy of the GranthStudio runner): plan from shots.json, job keys, reuse = no second charge, cap, bad audio. No network."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import voice_cast as v  # noqa: E402

PACK = Path(__file__).resolve().parents[1] / 'stories' / 'kalika_puran_bhag1' / 'pack_opus_high_20261108_v4_deva'


def test_paths_are_per_story_and_pack():
    cast, out = v.paths(Path('/r/stories/other_story/pack_x'))
    assert cast.as_posix().endswith('stories/other_story/voices_cast.json') and out.as_posix().endswith('anime_other_story/voices/pack_x')


def vmap(plan):
    who = {l["voice"] for l in plan["lines"]}
    return {lg: {w: f"vid-{lg}-{w}" for w in who} for lg in v.LANGS}


def test_plan_has_18_lines_three_languages():
    plan = v.load_plan(PACK)
    assert len(plan["lines"]) == 18 and all(all(l[lg] for lg in v.LANGS) for l in plan["lines"])
    jobs = v.build_jobs(plan, [l["id"] for l in plan["lines"]], vmap(plan), "eleven_v4")
    assert len(jobs) == 54 and len({j["key"] for j in jobs}) == 54


def test_missing_voice_stops_before_any_call():
    plan = v.load_plan(PACK)
    with pytest.raises(SystemExit):
        v.build_jobs(plan, [plan["lines"][0]["id"]], {"en": {}, "hi": {}, "mr": {}}, "eleven_v4")


def fake(calls):
    def post(method, path, key, body=None):
        calls.append(path)
        return b"audio", {"character-cost": str(len(body["text"]))}
    return post


def test_rerun_reuses_and_cap_blocks(tmp_path):
    plan = v.load_plan(PACK)
    jobs = v.build_jobs(plan, [plan["lines"][0]["id"]], vmap(plan), "eleven_v4")
    calls = []
    led = v.Ledger(tmp_path / "l.jsonl", 10_000)
    m1 = v.run(jobs, tmp_path, 10_000, "k" * 20, post=fake(calls), ledger=led, probe=lambda p: 2.0)
    assert m1["ok"] == 3 and len(calls) == 3
    m2 = v.run(jobs, tmp_path, 10_000, "k" * 20, post=fake(calls), ledger=led, probe=lambda p: 2.0)
    assert m2["reused"] == 3 and len(calls) == 3                      # nothing bought twice
    with pytest.raises(SystemExit):                                   # a new text key would exceed a tiny cap
        j2 = [dict(j, key=j["key"] + "x", id=j["id"] + "b") for j in jobs]
        v.run(j2, tmp_path, 10, "k" * 20, post=fake(calls), ledger=v.Ledger(tmp_path / "l2.jsonl", 10), probe=lambda p: 2.0)


def test_undecodable_audio_is_not_accepted(tmp_path):
    plan = v.load_plan(PACK)
    jobs = v.build_jobs(plan, [plan["lines"][0]["id"]], vmap(plan), "eleven_v4")

    def bad(p):
        raise RuntimeError("does not decode")
    m = v.run(jobs, tmp_path, 10_000, "k" * 20, post=fake([]), ledger=v.Ledger(tmp_path / "l.jsonl", 10_000), probe=bad)
    assert m["ok"] == 0 and m["lines"][-1]["ok"] is False


def test_per_voice_model_and_batches():
    import voice_add as va
    plan = v.load_plan(PACK)
    cast = vmap(plan)
    cast["_models"] = {"hi": {"BRAHMA": "eleven_multilingual_v2"}}
    jobs = v.build_jobs(plan, [l["id"] for l in plan["lines"]], cast, "eleven_v4", cast["_models"])
    assert {j["model"] for j in jobs if j["lang"] == "hi" and j["voice"] == "BRAHMA"} == {"eleven_multilingual_v2"}
    assert {j["model"] for j in jobs if j["lang"] == "hi" and j["voice"] != "BRAHMA"} == {"eleven_v4"}
    ids = va.missing(cast, {"vid-en-SHIVA"})
    assert "vid-en-SHIVA" not in ids and [len(b) for b in va.batches(ids)] == [10, 7]


def test_apostrophe_kept_in_english_dropped_as_quote():
    assert v.voices.prep_text("Kamadeva's hands began to shake.") == "Kamadeva's hands began to shake."
    assert v.voices.prep_text("He said 'go' now") == "He said go now."


def test_fit_report_and_post_sends_job_model(tmp_path):
    plan = v.load_plan(PACK)
    jobs = v.build_jobs(plan, [plan["lines"][0]["id"]], vmap(plan), "eleven_v4", {"hi": {"NARRATOR": "eleven_multilingual_v2"}})
    bodies = []

    def post(method, path, key, body=None):
        bodies.append(body)
        return b"audio", {"character-cost": str(len(body["text"]))}
    m = v.run(jobs, tmp_path, 10_000, "k" * 20, post=post, ledger=v.Ledger(tmp_path / "l.jsonl", 10_000), probe=lambda p: 6.0)
    assert {b["model_id"] for b in bodies} == {"eleven_v4", "eleven_multilingual_v2"}
    rep = v.fit_report(m, {plan["lines"][0]["id"]: 5.0})
    assert rep[0]["tempo"] == 1.2 and rep[0]["verdict"].startswith("TOO LONG")
    assert v.fit_report(m, {plan["lines"][0]["id"]: 5.8})[0]["verdict"] == "fit by atempo"


def test_speed_is_in_the_key_and_the_newest_clip_wins(tmp_path):
    plan = v.load_plan(PACK)
    lid = plan["lines"][0]["id"]
    j0 = v.build_jobs(plan, [lid], vmap(plan), "eleven_v4")
    j1 = v.build_jobs(plan, [lid], vmap(plan), "eleven_v4", None, {lid + ".en": 1.15})
    assert j0[0]["key"] != j1[0]["key"] and j0[1]["key"] == j1[1]["key"] and j1[0]["settings"] == {"speed": 1.15}
    bodies = []

    def post(method, path, key, body=None):
        bodies.append(body)
        return b"audio", {"character-cost": "10"}
    led = v.Ledger(tmp_path / "l.jsonl", 10_000)
    v.run(j0, tmp_path, 10_000, "k" * 20, post=post, ledger=led, probe=lambda p: 5.0)
    m = v.run(j1, tmp_path, 10_000, "k" * 20, post=post, ledger=led, probe=lambda p: 4.0)
    assert len(bodies) == 4 and bodies[-1]["voice_settings"] == {"speed": 1.15}       # only the changed line was bought again
    newest = {r["id"]: r for r in v.latest_ok(m)}
    assert newest[lid + ".en"]["seconds"] == 4.0 and len(v.latest_ok(m)) == 3


def test_export_trims_edge_silence_and_fits_by_atempo(tmp_path):
    import shutil
    import subprocess
    if not shutil.which("ffmpeg"):
        pytest.skip("no ffmpeg")
    src = tmp_path / "mp3" / "en" / "L.en.mp3"
    src.parent.mkdir(parents=True)
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "sine=frequency=440:duration=1", "-af", "adelay=300|300,apad=pad_dur=0.3", str(src)], check=True)
    man = {"lines": [{"id": "L.en", "line": "L", "lang": "en", "file": "mp3/en/L.en.mp3", "ok": True}]}
    rep = []
    assert v.export_wavs(man, tmp_path, tmp_path / "w", "m", slots={"L": 0.9}, report=rep) == 1
    wav = tmp_path / "w" / "wav" / "en" / "L.en.wav"
    assert 0.95 < rep[0]["seconds"] < 1.1 and rep[0]["verdict"] == "fit by atempo"       # silence cut: 1.6 s file -> about 1.0 s speech
    assert 0.8 < v.probe_seconds(wav) < 0.98                                             # sped up by about 1.1 to the 0.9 s slot
    rep2 = []
    v.export_wavs(man, tmp_path, tmp_path / "w2", "m", slots={"L": 0.6}, report=rep2)
    assert rep2[0]["verdict"].startswith("TOO LONG")                                     # beyond MAX_TEMPO: reported, the wav is not sped up
    assert v.load_slots(PACK, tmp_path / "none.json")["SHOT-001-N"] > 0
