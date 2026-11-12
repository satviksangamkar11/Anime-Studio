"""W-09 offline tests: build_h3_batch rows come from routes, shot mode and the timeline lock; a soft end is refused (D4);
settings_sha256 per manifest shot. No GPU, no network, no Colab call. Dry run only."""
import base64
import hashlib
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import build_h3_batch as b  # noqa: E402
from h3.shot_mode import ShotModeError  # noqa: E402

PF = 175                                   # 5 + 17*10: a legal lattice count
LOCK_SHA = "lockhash"


def _route(route, mode, strength=None):
    return {"route": route, "image_prompt_type": mode, "input_video_strength": strength}


ROUTES = {"lock_sha256": LOCK_SHA, "routes": {"SHOT-001": _route("SE", "SE"), "SHOT-002": _route("POST", None)}}
LOCK = {"input_sha256": LOCK_SHA, "shots": [
    {"id": "SHOT-001", "pixel_frames": PF, "end_frame_position": 170, "edit_frames": 150},
    {"id": "SHOT-002", "pixel_frames": PF, "end_frame_position": 170, "edit_frames": 150},
]}


def _story(ids=("SHOT-001", "SHOT-002")):
    return {"registry": {}, "episodes": [{"episode_id": "EP1", "shots": [
        {"shot_id": sid, "timing_and_lattice": {"pixel_frames": PF}} for sid in ids]}]}


@pytest.fixture(autouse=True)
def _prompt(monkeypatch):
    monkeypatch.setattr(b, "compile_fl2va_prompt", lambda sh, reg, **kw: {"compiled_prompt": "line one\n\nline two"})  # M-02: start_only kwarg for S rows


def test_se_route_has_end():
    rows, post_ids = b.legacy_rows(_story(), "EP1", routes=ROUTES, lock=LOCK, env={})
    assert [r["id"] for r in rows] == ["SHOT-001"]
    row = rows[0]
    assert row["image_prompt_type"] == "SE"
    assert row["start"] == "keyframes/SHOT-001-A.png"
    assert row["end"] == "keyframes/SHOT-001-B.png"
    assert row["render_frames"] == PF


def test_s_route_needs_flag():
    routes = {"routes": {"SHOT-001": _route("S", "S")}}
    with pytest.raises(ShotModeError):
        b.legacy_rows(_story(("SHOT-001",)), "EP1", routes=routes, lock=LOCK, env={"SHOT_MODE_S_ALLOW": "0"})   # M-32
    rows, post_ids = b.legacy_rows(_story(("SHOT-001",)), "EP1", routes=routes, lock=LOCK, env={})
    assert rows[0]["image_prompt_type"] == "S"
    assert "end" not in rows[0]
    assert post_ids == []


def test_post_route_skipped():
    rows, post_ids = b.legacy_rows(_story(), "EP1", routes=ROUTES, lock=LOCK, env={})
    assert post_ids == ["SHOT-002"]
    assert [r["id"] for r in rows] == ["SHOT-001"]


def test_soft_se_refused_until_d4():
    routes = {"routes": {"SHOT-001": _route("SOFT_SE", "SE", 0.6)}}
    with pytest.raises(ValueError, match="drops"):
        b.legacy_rows(_story(("SHOT-001",)), "EP1", routes=routes, lock=LOCK, env={})


def test_lock_pixel_mismatch_refused():
    bad = {"input_sha256": LOCK_SHA, "shots": [{"id": "SHOT-001", "pixel_frames": PF + 17, "end_frame_position": 170, "edit_frames": 150}]}
    with pytest.raises(ValueError, match="pixel_frames"):
        b.legacy_rows(_story(("SHOT-001",)), "EP1", routes=ROUTES, lock=bad, env={})


# negative cases beyond the card: no route, no routes at all, KFI soft route, SE without a lock end position

def test_routes_are_required():
    with pytest.raises(ValueError, match="routes are required"):
        b.legacy_rows(_story(), "EP1", lock=LOCK, env={})


def test_shot_without_route_refused():
    with pytest.raises(ValueError, match="SHOT-001"):
        b.legacy_rows(_story(("SHOT-001",)), "EP1", routes={"routes": {}}, lock=LOCK, env={})


def test_kfi_soft_route_refused():
    routes = {"routes": {"SHOT-001": _route("KFI", "SE", 0.65)}}
    with pytest.raises(ValueError, match="drops"):
        b.legacy_rows(_story(("SHOT-001",)), "EP1", routes=routes, lock=LOCK, env={})


def test_se_without_lock_end_position_refused():
    with pytest.raises(ValueError):
        b.legacy_rows(_story(("SHOT-001",)), "EP1", routes=ROUTES, env={})


# main: settings_sha256 per manifest shot, and a stale routes file is refused

def _run_main(tmp_path, monkeypatch, routes_payload):
    seen = {}

    def fake_build(shots, root, batch, ids=None, bible=None, require_bible=False, target="kaggle", profile=5, manifest=None):
        settings = {sh["id"]: {"prompt": sh["prompt_override"], "video_length": sh["render_frames"], "image_prompt_type": sh["image_prompt_type"]}
                    for sh in shots}
        seen["settings"] = settings
        manifest.update({"batch": batch, "embed_mb_total": 0.0, "shots": [{"id": sid} for sid in settings]})
        blob = base64.b64encode(json.dumps(settings).encode()).decode()
        return f'for sid, settings in json.loads(base64.b64decode("{blob}")).items():\n', {}

    story_p = tmp_path / "story.json"
    story_p.write_text(json.dumps(_story()), encoding="utf-8")
    routes_p = tmp_path / "routes.json"
    routes_p.write_text(json.dumps(routes_payload), encoding="utf-8")
    lock_p = tmp_path / "lock.json"
    lock_p.write_text(json.dumps(LOCK), encoding="utf-8")
    monkeypatch.setattr(b, "HERE", tmp_path)
    monkeypatch.setattr(b, "load_lock", lambda p: json.loads(Path(p).read_text(encoding="utf-8")))
    monkeypatch.setattr(b.run_kaggle, "build", fake_build)
    monkeypatch.setattr(b, "harden", lambda script: script)
    monkeypatch.setattr(b, "write_wheel_upload", lambda folder, **kw: None)
    monkeypatch.setattr(b.run_kaggle, "png_b64", b.run_kaggle.png_b64)
    monkeypatch.setattr(b.run_kaggle, "embedder", b.run_kaggle.embedder)
    kd = tmp_path / "pack" / "keyframes"   # M-33: render_version hashes the keyframe file bytes
    kd.mkdir(parents=True, exist_ok=True)
    for sid in ("SHOT-001", "SHOT-002", "SHOT-003"):
        (kd / f"{sid}-A.png").write_bytes(b"a")
        (kd / f"{sid}-B.png").write_bytes(b"b")
    code = b.main([str(story_p), str(tmp_path / "pack"), "B1", "--routes", str(routes_p), "--lock", str(lock_p)])
    return code, seen


def test_manifest_settings_sha(tmp_path, monkeypatch):
    code, seen = _run_main(tmp_path, monkeypatch, ROUTES)
    assert code == 0
    manifest = json.loads((tmp_path / "colab_batches" / "B1" / "render_manifest.json").read_text(encoding="utf-8"))
    sha = manifest["shots"][0]["settings_sha256"]
    expected = hashlib.sha256(json.dumps(seen["settings"]["SHOT-001"], sort_keys=True).encode("utf-8")).hexdigest()
    assert sha == expected
    assert len(sha) == 64
    assert manifest["settings_sha256"] == hashlib.sha256(json.dumps(seen["settings"], sort_keys=True).encode("utf-8")).hexdigest()


def test_stale_routes_refused_in_main(tmp_path, monkeypatch):
    stale = dict(ROUTES, lock_sha256="older-lock")
    with pytest.raises(ValueError, match="stale routes"):
        _run_main(tmp_path, monkeypatch, stale)


def test_soft_strength_read_from_built_frame(monkeypatch):
    # the card checks frame["input_video_strength"] AFTER shot_mode.frame_row: a soft value that frame_row returns is refused
    real = b.shot_mode.frame_row

    def soft_frame(shot, env=None):
        row = real(shot, env)
        row["input_video_strength"] = 0.6
        return row
    monkeypatch.setattr(b.shot_mode, "frame_row", soft_frame)
    with pytest.raises(ValueError, match="drops"):
        b.legacy_rows(_story(("SHOT-001",)), "EP1", routes=ROUTES, lock=LOCK, env={})


def test_main_refuses_routes_that_are_not_an_object(tmp_path, monkeypatch):
    with pytest.raises(ValueError, match="routes must be a JSON object"):
        _run_main(tmp_path, monkeypatch, [1, 2])


def test_settings_sha_from_real_runner_output(tmp_path, monkeypatch):
    # no fake runner: the real run_kaggle.build text is decoded by an independent regex and must give the manifest's sha
    import re
    (tmp_path / "keyframes").mkdir()
    for sid in ("SHOT-001",):
        (tmp_path / "keyframes" / f"{sid}-A.png").write_bytes(b"x")
        (tmp_path / "keyframes" / f"{sid}-B.png").write_bytes(b"y")
    monkeypatch.setattr(b.run_kaggle, "png_b64", lambda path: "QUJD")
    rows, _post = b.legacy_rows(_story(("SHOT-001",)), "EP1", routes=ROUTES, lock=LOCK, env={})
    manifest = {}
    script, _meta = b.run_kaggle.build(rows, str(tmp_path), "t", None, None, False, "colab", 5, manifest)
    b.add_settings_sha(manifest, script)
    # the real runner also holds an images blob first: only the 'for sid, settings in' loop is the settings blob
    m = re.search(r'for sid, settings in json\.loads\(base64\.b64decode\("([A-Za-z0-9+/=]+)"\)\)', script)
    assert m, "real runner text has no settings blob"
    settings = json.loads(base64.b64decode(m.group(1)))
    assert manifest["shots"][0]["settings_sha256"] == hashlib.sha256(
        json.dumps(settings["SHOT-001"], sort_keys=True).encode("utf-8")).hexdigest()
    assert manifest["settings_sha256"] == hashlib.sha256(json.dumps(settings, sort_keys=True).encode("utf-8")).hexdigest()


def _short(pf):
    story = _story(("SHOT-001",))
    story["episodes"][0]["shots"][0]["timing_and_lattice"]["pixel_frames"] = pf
    lock = {"input_sha256": LOCK_SHA, "shots": [{"id": "SHOT-001", "pixel_frames": pf, "end_frame_position": 100}]}
    return story, lock


def test_pika6_refuses_107():
    story, lock = _short(107)
    with pytest.raises(ValueError, match="124"):
        b.legacy_rows(story, "EP1", routes=ROUTES, lock=lock, env={})
    rows, _ = b.legacy_rows(story, "EP1", routes=ROUTES, lock=lock, env={}, allow_107=True)
    assert rows[0]["render_frames"] == 107
    story, lock = _short(124)
    assert b.legacy_rows(story, "EP1", routes=ROUTES, lock=lock, env={})[0][0]["render_frames"] == 124
