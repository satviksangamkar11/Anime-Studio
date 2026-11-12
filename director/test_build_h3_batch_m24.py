"""M-24 tests for build_h3_batch.add_settings_sha: per-shot render_version over the settings, pin, profile and A/B paths.
No GPU, no network. Hashes are only compared with each other (any change must change the version)."""
import base64
import json

import pytest

import build_h3_batch as b
import h3_director


def _script(settings):
    blob = base64.b64encode(json.dumps(settings).encode()).decode()
    return 'for sid, settings in json.loads(base64.b64decode("%s")).items():\n    pass\n' % blob


def _settings(seed=1, start="keyframes/S1-A.png"):
    return {"S1": {"seed": seed, "steps": 6, "cfg": 1, "sampler": "euler", "resolution": "768x1344", "start": start}}


def _version(settings, pin=None):
    manifest = {"shots": [{"id": "S1"}]}
    kwargs = {} if pin is None else {"pin": pin}
    b.add_settings_sha(manifest, _script(settings), **kwargs)
    return manifest["shots"][0]["render_version"], manifest["render_version"]


def test_render_version_written_per_shot_and_per_batch():
    shot_v, batch_v = _version(_settings())
    assert isinstance(shot_v, str) and len(shot_v) == 64
    assert isinstance(batch_v, str) and len(batch_v) == 64
    assert shot_v != batch_v


def test_same_settings_same_render_version():
    assert _version(_settings()) == _version(_settings())


def test_seed_change_makes_new_render_version():
    assert _version(_settings(seed=1))[0] != _version(_settings(seed=2))[0]


def test_ab_path_change_makes_new_render_version():
    assert _version(_settings(start="keyframes/S1-A.png"))[0] != _version(_settings(start="keyframes/S1-A2.png"))[0]


def test_pin_change_makes_new_render_version():
    assert _version(_settings())[0] != _version(_settings(), pin="a" * 40)[0]


def test_default_pin_is_the_wan2gp_commit():
    assert b.WAN2GP_PIN == "bd1ff5903cbc18b46c3cce3b75bd140870b536a2"
    assert _version(_settings())[0] == _version(_settings(), pin=b.WAN2GP_PIN)[0]


def test_profile_change_makes_new_render_version(monkeypatch):
    before = _version(_settings())[0]
    changed = dict(h3_director.PRESET)
    changed["fl2va"] = ("other_preset", "other.safetensors", "")
    monkeypatch.setattr(h3_director, "PRESET", changed)
    assert _version(_settings())[0] != before


def test_missing_settings_blob_still_refused():
    with pytest.raises(ValueError):
        b.add_settings_sha({"shots": [{"id": "S1"}]}, "print('no blob here')")


# ---- M-33: keyframe file bytes are hashed (S route: A only) ----
def _pack(tmp_path, a=b"A1", b_=b"B1"):
    (tmp_path / "keyframes").mkdir(exist_ok=True)
    (tmp_path / "keyframes" / "S1-A.png").write_bytes(a)
    (tmp_path / "keyframes" / "S1-B.png").write_bytes(b_)
    return tmp_path


def _kversion(tmp_path, itype):
    row = {"id": "S1", "image_prompt_type": itype, "start": "keyframes/S1-A.png", "end": "keyframes/S1-B.png"}
    m = {"shots": [{"id": "S1"}]}
    b.add_settings_sha(m, _script(_settings()), rows=[row], pack=tmp_path)
    return m["shots"][0]["render_version"], m["render_version"]


def test_same_path_new_a_bytes_new_version(tmp_path):
    v1 = _kversion(_pack(tmp_path), "S")
    v2 = _kversion(_pack(tmp_path, a=b"A2"), "S")
    assert v1[0] != v2[0] and v1[1] != v2[1]


def test_se_b_bytes_change_version_but_s_ignores_b(tmp_path):
    se1 = _kversion(_pack(tmp_path), "SE")[0]
    s1 = _kversion(tmp_path, "S")[0]
    se2 = _kversion(_pack(tmp_path, b_=b"B2"), "SE")[0]
    s2 = _kversion(tmp_path, "S")[0]
    assert se1 != se2
    assert s1 == s2


def test_missing_keyframe_file_refused(tmp_path):
    with pytest.raises(FileNotFoundError):
        _kversion(tmp_path, "S")
