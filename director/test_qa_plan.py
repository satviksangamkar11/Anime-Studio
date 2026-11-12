"""M-29 tests: qa_plan (plan builder + clip review producer) and the seed per shot in build_h3_batch.
Offline: fake frames, fake model call, no ffmpeg, no network, no Colab."""
import base64
import json
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))

import build_h3_batch as b  # noqa: E402
import clip_qa  # noqa: E402
import post_fetch_qa as pq  # noqa: E402
import qa_plan as q  # noqa: E402

SHEET = {"cast": [{"name": "Raj"}], "props": [{"class": "flute"}]}


def _tree(tmp_path, ids=("SHOT-001", "SHOT-002")):
    res, keys, audio, pack = (tmp_path / n for n in ("res", "keys", "audio", "pack"))
    for d in (keys, audio, pack):
        d.mkdir()
    for sid in ids:
        (res / sid).mkdir(parents=True)
        (res / sid / "out.mp4").write_bytes(b"x" * 10)
        (keys / f"{sid}-A.png").write_bytes(b"a")
        (keys / f"{sid}-B.png").write_bytes(b"b")
        (audio / f"{sid}.wav").write_bytes(b"w")
        (pack / f"{sid}.json").write_text(json.dumps(SHEET), encoding="utf-8")
    return res, keys, audio, pack


def _build(tmp_path, ids=("SHOT-001", "SHOT-002"), **kw):
    res, keys, audio, pack = _tree(tmp_path, ids)
    args = dict(lock="lock.json", pack=pack, results=res, keyframes=keys, audio_dir=audio, out_dir=tmp_path / "qa",
                shot_ids=list(ids), trim=lambda sid: (10, 130),
                review=lambda sid, sheet, clip, ti, to: {"10": {"person": 1}})
    args.update(kw)
    return q.build_plan(**args), args


def test_plan_has_every_field_and_loads_through_post_fetch_qa(tmp_path):
    path, _ = _build(tmp_path)
    plan = pq.load_plan(path)                      # load_plan refuses a missing field
    assert plan["lock"] == "lock.json" and sorted(plan["shots"]) == ["SHOT-001", "SHOT-002"]
    e = plan["shots"]["SHOT-001"]
    assert e["clip"] == "SHOT-001/out.mp4"          # relative to the results folder
    assert e["key_a"].endswith("SHOT-001-A.png") and e["key_b"].endswith("SHOT-001-B.png")
    assert e["sheet"].endswith("SHOT-001.json") and e["audio"].endswith("SHOT-001.wav")
    assert json.loads(Path(e["review"]).read_text(encoding="utf-8")) == {"10": {"person": 1}}


def test_missing_clip_is_refused_naming_the_shot(tmp_path):
    res, keys, audio, pack = _tree(tmp_path)
    (res / "SHOT-002" / "out.mp4").unlink()
    with pytest.raises(ValueError, match="SHOT-002.*clip"):
        q.build_plan("lock.json", pack, res, keys, audio, tmp_path / "qa", ["SHOT-001", "SHOT-002"],
                     trim=lambda s: (0, 24), review=lambda *a: {})


def test_missing_keyframe_audio_or_sheet_is_refused(tmp_path):
    cases = (("keys/SHOT-001-B.png", "key_b"), ("audio/SHOT-001.wav", "audio"), ("pack/SHOT-001.json", "sheet"))
    for victim, word in cases:
        d = tmp_path / word
        d.mkdir()
        res, keys, audio, pack = _tree(d, ("SHOT-001",))
        (d / victim).unlink()
        with pytest.raises(ValueError, match=word):
            q.build_plan("lock.json", pack, res, keys, audio, d / "qa", ["SHOT-001"],
                         trim=lambda s: (0, 24), review=lambda *a: {})


def test_unknown_shot_in_the_pack_is_refused(tmp_path):
    res, keys, audio, pack = _tree(tmp_path, ("SHOT-001",))
    with pytest.raises(ValueError, match="SHOT-009"):
        q.build_plan("lock.json", pack, res, keys, audio, tmp_path / "qa", ["SHOT-009"],
                     trim=lambda s: (0, 24), review=lambda *a: {})


def test_review_is_produced_once_per_shot_with_the_sheet(tmp_path):
    seen = []
    _build(tmp_path, review=lambda sid, sheet, clip, ti, to: seen.append((sid, sheet, ti, to)) or {})
    assert [s[0] for s in seen] == ["SHOT-001", "SHOT-002"] and seen[0][1] == SHEET and seen[0][2:] == (10, 130)


# ---- review producer
def _jpg(i):
    return b"jpg%d" % i


def test_sample_frames_are_evenly_spread_inside_the_window():
    assert q.sample_frames(0, 100, 4) == [0, 25, 50, 75]
    assert q.sample_frames(10, 12, 4) == [10, 11]       # fewer frames than samples: every frame once


def test_review_keys_are_absolute_frames_with_class_counts_and_pass_clip_qa(tmp_path):
    asked = []

    def ask(jpeg):
        asked.append(jpeg)
        return {"person": 1, "flute": 1}
    rev = q.produce_review(SHEET, "clip.mp4", 10, 130, ask=ask, n=4,
                           load_frames=lambda c, ti, to, idx: [_jpg(i) for i in idx])
    assert sorted(rev, key=int) == ["10", "40", "70", "100"]
    assert all(v == {"person": 1, "flute": 1} for v in rev.values())
    assert len(asked) == 4
    p = tmp_path / "rev.json"
    p.write_text(json.dumps(rev), encoding="utf-8")
    assert clip_qa.new_classes(str(p), SHEET) == []      # the real reader accepts it


def test_a_new_class_in_the_model_answer_is_kept_so_clip_qa_flags_it(tmp_path):
    rev = q.produce_review(SHEET, "c", 0, 48, ask=lambda j: {"person": 1, "dog": 1},
                           load_frames=lambda c, ti, to, idx: [_jpg(i) for i in idx], n=2)
    p = tmp_path / "rev.json"
    p.write_text(json.dumps(rev), encoding="utf-8")
    assert clip_qa.new_classes(str(p), SHEET) == ["dog"]


def test_bad_model_answer_is_refused_not_guessed():
    for bad in ("text", {"person": "two"}, {"person": True}, {"person": -1}):
        with pytest.raises(ValueError):
            q.produce_review(SHEET, "c", 0, 48, ask=lambda j, bad=bad: bad,
                             load_frames=lambda c, ti, to, idx: [_jpg(i) for i in idx], n=2)


def test_stub_counts_exactly_what_the_sheet_knows(tmp_path):
    rev = q.produce_review(SHEET, "c", 0, 48, ask=q.stub_ask(SHEET),
                           load_frames=lambda c, ti, to, idx: [_jpg(i) for i in idx], n=2)
    assert all(v == {"person": 1, "flute": 1} for v in rev.values())


def test_parse_counts_reads_json_inside_text_and_think_block():
    assert q.parse_counts('<think>x</think> ```json\n{"person": 2}\n``` ') == {"person": 2}
    with pytest.raises(ValueError):
        q.parse_counts("no json here")


def test_nvidia_ask_uses_key_pool_and_cools_a_429(tmp_path):
    class Pool:
        def __init__(self):
            self.cool, self.n = [], 0

        def acquire(self):
            self.n += 1
            return self.n - 1

        def cooldown(self, idx, s):
            self.cool.append(idx)
    sent = []

    def post(url, key, body):
        sent.append((key, body))
        if key == "k0":
            raise q.RateLimited()
        return '{"person": 1}'
    pool = Pool()
    ask = q.nvidia_ask(["k0", "k1"], pool, post=post, model="m")
    assert ask(b"jpegbytes") == {"person": 1}
    assert pool.cool == [0] and [s[0] for s in sent] == ["k0", "k1"]
    img = sent[0][1]["messages"][0]["content"][1]["image_url"]["url"]
    assert img == "data:image/jpeg;base64," + base64.b64encode(b"jpegbytes").decode()


def test_no_keys_means_stub_and_it_is_reported(monkeypatch):
    for i in range(1, 15):
        monkeypatch.delenv("NVIDIA_API_KEY_%02d" % i, raising=False)
    ask, source = q.pick_ask(SHEET)
    assert source == "stub" and ask(b"x") == {"person": 1, "flute": 1}


def test_plan_records_the_review_source(tmp_path):
    path, _ = _build(tmp_path, review_source="stub")
    assert json.loads(Path(path).read_text(encoding="utf-8"))["review_source"] == "stub"


# ---- seed per shot
def test_shot_seed_is_stable_distinct_per_shot_and_changes_with_the_version():
    assert b.shot_seed("SHOT-001") == b.shot_seed("SHOT-001")
    assert b.shot_seed("SHOT-001") != b.shot_seed("SHOT-002")
    assert b.shot_seed("SHOT-001", "2") != b.shot_seed("SHOT-001", "1")
    assert 0 <= b.shot_seed("SHOT-001") < 2**31


def _story_inputs():
    story = {"registry": {}, "episodes": [{"episode_id": "EP1", "shots": [
        {"shot_id": "SHOT-001", "timing_and_lattice": {"pixel_frames": 175}},
        {"shot_id": "SHOT-002", "timing_and_lattice": {"pixel_frames": 175}, "seed": 777}]}]}
    routes, lock = {"routes": {}}, {"shots": []}
    for sid in ("SHOT-001", "SHOT-002"):
        routes["routes"][sid] = {"route": "SE", "image_prompt_type": "SE", "input_video_strength": None}
        lock["shots"].append({"id": sid, "pixel_frames": 175, "end_frame_position": 170})
    return story, routes, lock


def test_rows_carry_a_derived_seed_unless_the_story_gives_one(monkeypatch):
    monkeypatch.setattr(b, "compile_fl2va_prompt", lambda sh, reg, **kw: {"compiled_prompt": "p"})
    story, routes, lock = _story_inputs()
    rows = b.legacy_rows(story, "EP1", routes=routes, lock=lock)[0]
    assert rows[0]["seed"] == b.shot_seed("SHOT-001") and rows[1]["seed"] == 777
    rows2 = b.legacy_rows(story, "EP1", routes=routes, lock=lock, seed_version="2")[0]
    assert rows2[0]["seed"] == b.shot_seed("SHOT-001", "2") != rows[0]["seed"]


def test_manifest_shot_stores_the_seed_from_the_settings_and_it_feeds_render_version():
    def script(seed):
        blob = base64.b64encode(json.dumps({"S1": {"seed": seed, "steps": 6}}).encode()).decode()
        return 'for sid, settings in json.loads(base64.b64decode("%s")).items():\n    pass\n' % blob
    m1, m2 = ({"shots": [{"id": "S1"}]} for _ in range(2))
    b.add_settings_sha(m1, script(5))
    b.add_settings_sha(m2, script(6))
    assert m1["shots"][0]["seed"] == 5 and m2["shots"][0]["seed"] == 6
    assert m1["shots"][0]["render_version"] != m2["shots"][0]["render_version"]


def test_seed_reaches_the_history_record(tmp_path):
    import run_colab_batch as r
    m = {"shots": [{"id": "S1"}]}
    blob = base64.b64encode(json.dumps({"S1": {"seed": 4242}}).encode()).decode()
    b.add_settings_sha(m, 'for sid, settings in json.loads(base64.b64decode("%s")).items():\n    pass\n' % blob)
    rec = r.record_render(tmp_path / "h.json", m["shots"][0])
    assert rec["seed"] == 4242
