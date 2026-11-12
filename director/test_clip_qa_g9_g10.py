"""G9 identity check for route S, G10 scene-cut on neighbour SSIM for route S. No network, no model call."""
import sys
from pathlib import Path

import numpy as np
import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))
import clip_qa  # noqa: E402
import qa_plan  # noqa: E402
import timeline_lock_io  # noqa: E402

H, W, N = 48, 32, 60


def _blend_frames():
    """Gradual fade between two different noise images: neighbours alike, last frame far from the first."""
    rng = np.random.default_rng(1)
    a, b = rng.random((H, W)), rng.random((H, W))
    return np.stack([(1 - i / (N - 1)) * a + (i / (N - 1)) * b for i in range(N)]).astype(np.float32), a


def _rgb(frames):
    g = (np.asarray(frames) * 255).astype(np.uint8)
    return np.repeat(g[..., None], 3, axis=-1)


MASTER = np.full((H, W, 3), 128, np.uint8)


@pytest.fixture
def qa_env(tmp_path, monkeypatch):
    frames, key = _blend_frames()
    clip = tmp_path / "c.mp4"
    clip.write_bytes(b"x")
    monkeypatch.setattr(clip_qa, "_verified_lock", lambda p: None)
    monkeypatch.setattr(timeline_lock_io, "lock_rows",
                        lambda lk: [{"id": "S1", "trim_in_frame": 0, "trim_out_frame": N}])
    monkeypatch.setattr(clip_qa, "extract", lambda *a, **k: frames)
    monkeypatch.setattr(clip_qa, "extract_rgb", lambda *a, **k: _rgb(frames))
    monkeypatch.setattr(clip_qa, "audio_analysis", lambda *a, **k: ([], -40.0))
    monkeypatch.setattr(clip_qa, "new_classes", lambda *a, **k: [])

    def run(route, **kw):
        k = key.astype(np.float32)
        return clip_qa.qa_shot("S1", str(clip), "lock", k, k, "rev", {}, "a.wav", str(tmp_path), route=route, **kw)
    return run


# ---- G10 -----------------------------------------------------------------------------------------

def test_features_has_neighbour_sims():
    frames, key = _blend_frames()
    f = clip_qa.features(frames, key, None)
    assert len(f["sim_prev"]) == N and f["sim_prev"][0] == 1.0
    assert min(f["sim_prev"]) > 0.75 > min(f["sim_to_a"])       # gradual change: far from A, close to neighbour


def test_s_route_scene_cut_uses_neighbour_ssim(qa_env):
    assert qa_env("S")["results"]["cuts"] == []


def test_se_route_scene_cut_still_uses_similarity_to_a(qa_env):
    assert qa_env("SE")["results"]["cuts"] != []


def test_s_route_hard_cut_is_still_found(qa_env, monkeypatch):
    frames, key = _blend_frames()
    cut = frames.copy()
    cut[30:] = np.random.default_rng(9).random((N - 30, H, W))
    monkeypatch.setattr(clip_qa, "extract", lambda *a, **k: cut)
    monkeypatch.setattr(clip_qa, "extract_rgb", lambda *a, **k: _rgb(cut))
    assert 30 in qa_env("S")["results"]["cuts"]


# ---- G9 ------------------------------------------------------------------------------------------

def test_s_route_runs_identity_check(qa_env):
    seen = []

    def ask(frame, master):
        seen.append(frame.shape)
        return {"same": True, "reason": "ok"}
    doc = qa_env("S", identity_master=MASTER, identity_ask=ask, identity_source="test")
    ident = doc["checks"]["identity"]
    assert len(seen) == 3 and ident["status"] == "ok" and ident["source"] == "test"
    assert [s["frame"] for s in ident["samples"]] == [0, N // 2, N - 1]
    assert doc["verdict"]["pass"] is True


def test_identity_no_fails_clip(qa_env):
    doc = qa_env("S", identity_master=MASTER, identity_source="test",
                 identity_ask=lambda f, m: {"same": False, "reason": "other face"})
    assert doc["checks"]["identity"]["status"] == "fail"
    assert [r["code"] for r in doc["verdict"]["reasons"]] == ["IDENTITY"]
    assert "IDENTITY" in clip_qa.ACCEPT_CODES and "IDENTITY" not in clip_qa.CRITICAL_CODES


def test_identity_no_on_early_frame_only_does_not_fail(qa_env):
    answers = iter([False, True, True])
    doc = qa_env("S", identity_master=MASTER, identity_source="test",
                 identity_ask=lambda f, m: {"same": next(answers), "reason": ""})
    assert doc["checks"]["identity"]["status"] == "ok"      # B-04: fail on the last kept frame


def test_se_route_skips_identity(qa_env):
    def ask(f, m):
        raise AssertionError("must not ask")
    doc = qa_env("SE", identity_master=MASTER, identity_ask=ask)
    assert doc["checks"]["identity"] is None


def test_s_route_without_master_warns(qa_env):
    doc = qa_env("S")
    assert doc["checks"]["identity"] is None and any("identity" in w for w in doc["warnings"])


def test_stub_identity_is_deterministic_and_discriminates():
    red = np.zeros((H, W, 3), np.uint8)
    red[..., 0] = 200
    blue = np.zeros((H, W, 3), np.uint8)
    blue[..., 2] = 200
    assert qa_plan.stub_identity_ask(red, red)["same"] is True
    assert qa_plan.stub_identity_ask(red, blue)["same"] is False
    assert qa_plan.stub_identity_ask(red, blue) == qa_plan.stub_identity_ask(red, blue)


def test_pick_identity_ask_stub_without_keys(monkeypatch):
    for i in range(1, 15):
        monkeypatch.delenv("NVIDIA_API_KEY_%02d" % i, raising=False)
    ask, src = qa_plan.pick_identity_ask()
    assert src == "stub" and ask is qa_plan.stub_identity_ask


def test_nvidia_identity_ask_parses_reply_and_cools_on_429():
    class Pool:
        def __init__(self):
            self.cool = []

        def acquire(self):
            return 0

        def cooldown(self, idx, s):
            self.cool.append((idx, s))
    replies = [qa_plan.RateLimited(), '<think>x</think>{"same": false, "reason": "no"}']

    def post(url, key, body):
        rep = replies.pop(0)
        if isinstance(rep, Exception):
            raise rep
        return rep
    pool = Pool()
    ask = qa_plan.nvidia_identity_ask(["k"], pool, post=post)
    img = np.zeros((H, W, 3), np.uint8)
    assert ask(img, img) == {"same": False, "reason": "no"}
    assert pool.cool == [(0, 60)]


def test_add_identity_records_master_per_shot(tmp_path):
    ident = tmp_path / "ident.png"
    ident.write_bytes(b"png")
    plan = qa_plan.add_identity({"shots": {"S1": {}, "S2": {}}}, ident)
    assert all(e["identity"] == str(ident) for e in plan["shots"].values())
    with pytest.raises(ValueError):
        qa_plan.add_identity({"shots": {}}, tmp_path / "missing.png")
