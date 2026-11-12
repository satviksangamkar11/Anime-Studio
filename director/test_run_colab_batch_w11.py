"""W-11 offline tests for run_colab_batch: GPU G4 only, requirement URLs, upload part limit, free disk,
settings_sha256 against the W-09 manifest, clip_verified with expected frames, stop_decision, stray and
stuck sessions, dead-man limit, canary proof, and the default dry run. No colab call, no network, no --go.
Fakes only (run_cli, popen, head, disk_usage, probe_frames)."""
import base64
import hashlib
import itertools
import json
import math
import subprocess
import sys
import urllib.error
from pathlib import Path
from types import SimpleNamespace

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "t0_pack"))
sys.path.insert(0, str(HERE.parent))
import build_h3_batch as bh  # noqa: E402
import run_colab_batch as r  # noqa: E402
import run_t0_colab as t0  # noqa: E402

PF = 175
HEAD_OK = lambda url: 200  # noqa: E731
DISK_OK = lambda p: SimpleNamespace(free=500 * 1024 ** 3)  # noqa: E731
REQ = "\n".join([
    "numpy==1.26.4",
    "chumpy @ https://example.com/chumpy-0.71.tar.gz",
    "smplfitter @ https://example.com/smplfitter-0.1.tar.gz",
    "pywin32 @ https://example.com/pywin.whl ; sys_platform == \"win32\"",
    "# note @ https://example.com/commented.whl",
]) + "\n"


class FakeProc:
    def __init__(self, rc=0):
        self.rc = rc
        self.killed = False

    def poll(self):
        return None if not self.killed else -9

    def wait(self, timeout=None):
        return self.rc

    def kill(self):
        self.killed = True


def _batch(root, ids=("SHOT-001",), frames=PF, prompt="p"):
    """A synthetic batch folder shaped like build_h3_batch output: run.py with a settings blob,
    render_manifest.json with the sha."""
    folder = root / "colab_batches" / "synth"
    folder.mkdir(parents=True, exist_ok=True)
    settings = {sid: {"prompt": prompt, "video_length": frames} for sid in ids}
    blob = base64.b64encode(json.dumps(settings).encode("utf-8")).decode("ascii")
    script = 'for sid, settings in json.loads(base64.b64decode("' + blob + '")).items():\n    pass\n'
    (folder / "run.py").write_text(script, encoding="utf-8")
    manifest = {"batch": "synth", "shots": [{"id": sid, "frames": frames} for sid in ids]}
    bh.add_settings_sha(manifest, script)
    (folder / "render_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return folder


def _wheel(root, data=b"wheel-bytes"):
    p = root / "chumpy.whl"
    p.write_bytes(data)
    return p, hashlib.sha256(data).hexdigest()


def _req(root, text=REQ):
    p = root / "requirements.txt"
    p.write_text(text, encoding="utf-8")
    return p


def _margs(tmp_path, gb="3"):
    return ["--min-free-gb", gb, "--requirements", str(_req(tmp_path))]


def _checks(folder, results, req, wheel, **kw):
    kw.setdefault("head", HEAD_OK)
    kw.setdefault("disk_usage", DISK_OK)
    return r.free_checks(folder, results, req, 3.0, wheel=wheel, **kw)


def _make_clip(results, sid, n=60000):
    d = Path(results) / sid
    d.mkdir(parents=True, exist_ok=True)
    (d / (sid + ".mp4")).write_bytes(b"x" * n)


HW_LINE = "[n] gpu-g4-s-x | Hardware: G4 | Shape: Standard\n"


def _cli(calls, state=None, sessions_line=HW_LINE, after=""):
    state = {} if state is None else state

    def fake(args, stdin=None, capture=False, check=True, timeout=None):
        calls.append(args[0])
        if args[0] == "stop":
            state["stopped"] = True
        if args[0] == "sessions":
            return after if state.get("stopped") else sessions_line
        if args[0] == "ls":
            return "out/\n"
        return ""
    return fake


# ---- GPU and arguments ---------------------------------------------------------------------------

def test_a100_refused(tmp_path, capsys):
    with pytest.raises(SystemExit) as e:
        r.main(["synth", "--results", str(tmp_path), "--gpu", "A100", *_margs(tmp_path, "1")])
    assert e.value.code == 2


def test_t4_refused(tmp_path):
    with pytest.raises(SystemExit) as e:
        r.main(["synth", "--results", str(tmp_path), "--gpu", "T4", *_margs(tmp_path, "1")])
    assert e.value.code == 2


def test_min_free_gb_is_required(tmp_path):
    with pytest.raises(SystemExit) as e:
        r.main(["synth", "--results", str(tmp_path), "--requirements", str(tmp_path / "x")])
    assert e.value.code == 2


def test_requirements_is_required(tmp_path):
    with pytest.raises(SystemExit) as e:
        r.main(["synth", "--results", str(tmp_path), "--min-free-gb", "1"])
    assert e.value.code == 2


# ---- requirement URLs ----------------------------------------------------------------------------

def test_preflight_urls(tmp_path):
    urls = r.preflight_urls(REQ)
    assert urls == [r.WAN2GP_GIT, "https://example.com/smplfitter-0.1.tar.gz"]


def test_chumpy_is_not_a_url_check(tmp_path):
    assert all("chumpy" not in u for u in r.preflight_urls(REQ))


def test_win32_word_in_name_is_still_checked(tmp_path):
    # review (Luna): only a sys_platform == "win32" marker excludes a line; the word win32 in a name does not
    req = "winlib @ https://example.com/win32-lib.tar.gz\n"
    assert r.preflight_urls(req) == [r.WAN2GP_GIT, "https://example.com/win32-lib.tar.gz"]


# ---- free_checks: upload parts, HEAD, disk, wheel, settings --------------------------------------

def test_upload_part_limit(tmp_path):
    folder = _batch(tmp_path)
    wheel = _wheel(tmp_path)
    big = folder / "upload_00.py"
    with open(big, "wb") as f:
        f.truncate(3_145_729)
    small = folder / "upload_01.py"
    with open(small, "wb") as f:
        f.truncate(3_000_080)
    fails = _checks(folder, tmp_path / "res", _req(tmp_path), wheel)
    assert len(fails) == 1 and "upload_00.py" in fails[0] and "part too large" in fails[0]


def test_head_504_blocks_dry_run(tmp_path):
    folder = _batch(tmp_path)

    def head(url):
        raise urllib.error.HTTPError(url, 504, "Gateway Timeout", None, None)
    fails = _checks(folder, tmp_path / "res", _req(tmp_path), _wheel(tmp_path), head=head)
    assert any("HTTP 504" in f for f in fails)


def test_low_disk_blocks(tmp_path):
    folder = _batch(tmp_path)
    fails = _checks(folder, tmp_path / "res", _req(tmp_path), _wheel(tmp_path),
                    disk_usage=lambda p: SimpleNamespace(free=2 * 1024 ** 3))
    assert any("below minimum" in f for f in fails)


def test_wrong_wheel_sha_blocks(tmp_path):
    folder = _batch(tmp_path)
    wheel, _ = _wheel(tmp_path)
    fails = _checks(folder, tmp_path / "res", _req(tmp_path), (wheel, "0" * 64))
    assert any("chumpy wheel" in f for f in fails)


def test_clean_batch_passes(tmp_path):
    folder = _batch(tmp_path)
    assert _checks(folder, tmp_path / "res", _req(tmp_path), _wheel(tmp_path)) == []


def test_settings_sha_mismatch_refused(tmp_path):
    folder = _batch(tmp_path)
    other = _batch(tmp_path / "other", prompt="changed")
    (folder / "run.py").write_text((other / "run.py").read_text(encoding="utf-8"), encoding="utf-8")
    fails = _checks(folder, tmp_path / "res", _req(tmp_path), _wheel(tmp_path))
    assert any("settings_sha256 differs" in f for f in fails)


def test_missing_manifest_refused(tmp_path):
    folder = _batch(tmp_path)
    (folder / "render_manifest.json").unlink()
    fails = _checks(folder, tmp_path / "res", _req(tmp_path), _wheel(tmp_path))
    assert any("render_manifest.json" in f for f in fails)


def test_go_path_is_the_same_gate_as_dry_run(tmp_path, monkeypatch, capsys):
    """Dry run and --go run the same free_checks: a failing check returns 1 before any colab call."""
    folder = _batch(tmp_path)
    monkeypatch.setattr(r, "HERE", tmp_path)
    calls = []
    monkeypatch.setattr(r, "run_cli", _cli(calls))
    monkeypatch.setattr(r.rs, "_default_head", lambda url, timeout=10: 504)
    code = r.main(["synth", "--results", str(tmp_path / "res"), "--go", *_margs(tmp_path, "0.0001")])
    assert code == 1 and calls == [] and "HTTP 504" in capsys.readouterr().out


# ---- main: dry run is the default, canary, write proof -------------------------------------------

def test_dry_run_is_default_and_calls_nothing(tmp_path, monkeypatch, capsys):
    _batch(tmp_path)
    monkeypatch.setattr(r, "HERE", tmp_path)
    monkeypatch.setattr(r, "free_checks", lambda *a, **k: [])
    calls = []
    monkeypatch.setattr(r, "run_cli", _cli(calls))
    monkeypatch.setattr(r, "batch", lambda *a, **k: (_ for _ in ()).throw(AssertionError("batch must not run")))
    code = r.main(["synth", "--results", str(tmp_path / "res"), *_margs(tmp_path)])
    out = capsys.readouterr().out
    assert code == 0 and calls == [] and "DRY RUN" in out and "dry run printed" in out


def test_dry_run_multi_shot_describes_canary(tmp_path, monkeypatch, capsys):
    _batch(tmp_path, ids=("SHOT-001", "SHOT-002"))
    monkeypatch.setattr(r, "HERE", tmp_path)
    monkeypatch.setattr(r, "free_checks", lambda *a, **k: [])
    assert r.main(["synth", "--results", str(tmp_path / "res"), *_margs(tmp_path)]) == 0
    assert "CANARY" in capsys.readouterr().out


def test_failed_check_returns_1_without_calls(tmp_path, monkeypatch, capsys):
    _batch(tmp_path)
    monkeypatch.setattr(r, "HERE", tmp_path)
    monkeypatch.setattr(r, "free_checks", lambda *a, **k: ["url check failed for x: HTTP 504"])
    calls = []
    monkeypatch.setattr(r, "run_cli", _cli(calls))
    assert r.main(["synth", "--results", str(tmp_path / "res"), *_margs(tmp_path)]) == 1
    assert calls == [] and "HTTP 504" in capsys.readouterr().out


def test_go_without_canary_refused(tmp_path, monkeypatch):
    _batch(tmp_path, ids=("SHOT-001", "SHOT-002"))
    monkeypatch.setattr(r, "HERE", tmp_path)
    monkeypatch.setattr(r, "free_checks", lambda *a, **k: [])
    calls = []
    monkeypatch.setattr(r, "run_cli", _cli(calls))
    monkeypatch.setattr(r, "batch", lambda *a, **k: (_ for _ in ()).throw(AssertionError("batch must not run")))
    code = r.main(["synth", "--results", str(tmp_path / "res"), "--go", *_margs(tmp_path)])
    assert code == 1 and "new" not in calls and calls == []


def _proof(tmp_path, manifest_sha, **over):
    proof = {"shot": "SHOT-001", "settings_sha256": manifest_sha, "frames": PF, "clip_verified": True, "owner_ok": True}
    proof.update(over)
    p = tmp_path / "canary.json"
    p.write_text(json.dumps(proof), encoding="utf-8")
    return p


def _sha_of(folder, sid="SHOT-001"):
    m = json.loads((folder / "render_manifest.json").read_text(encoding="utf-8"))
    return next(s["settings_sha256"] for s in m["shots"] if s["id"] == sid)


def test_canary_wrong_sha_refused(tmp_path, monkeypatch):
    folder = _batch(tmp_path, ids=("SHOT-001", "SHOT-002"))
    monkeypatch.setattr(r, "HERE", tmp_path)
    monkeypatch.setattr(r, "free_checks", lambda *a, **k: [])
    monkeypatch.setattr(r, "batch", lambda *a, **k: (_ for _ in ()).throw(AssertionError("batch must not run")))
    p = _proof(tmp_path, "0" * 64)
    code = r.main(["synth", "--results", str(tmp_path / "res"), "--go", *_margs(tmp_path),
                   "--canary-proof", str(p)])
    assert code == 1


def test_canary_unverified_or_not_owner_ok_refused(tmp_path, monkeypatch):
    folder = _batch(tmp_path, ids=("SHOT-001", "SHOT-002"))
    monkeypatch.setattr(r, "HERE", tmp_path)
    monkeypatch.setattr(r, "free_checks", lambda *a, **k: [])
    monkeypatch.setattr(r, "batch", lambda *a, **k: (_ for _ in ()).throw(AssertionError("batch must not run")))
    sha = _sha_of(folder)
    for over in ({"clip_verified": False}, {"owner_ok": False}):
        p = _proof(tmp_path, sha, **over)
        assert r.main(["synth", "--results", str(tmp_path / "res"), "--go", "--min-free-gb", "3",
                       "--requirements", str(_req(tmp_path)), "--canary-proof", str(p)]) == 1


def test_canary_right_proof_reaches_batch_with_frames(tmp_path, monkeypatch):
    folder = _batch(tmp_path, ids=("SHOT-001", "SHOT-002"))
    monkeypatch.setattr(r, "HERE", tmp_path)
    monkeypatch.setattr(r, "free_checks", lambda *a, **k: [])
    seen = {}
    def fake_batch(name, gpu, run_py, results, expected=None, **k):
        seen.update(expected=expected, gpu=gpu)
    monkeypatch.setattr(r, "batch", fake_batch)
    p = _proof(tmp_path, _sha_of(folder))
    code = r.main(["synth", "--results", str(tmp_path / "res"), "--go", *_margs(tmp_path),
                   "--canary-proof", str(p), "--no-qa"])
    assert code == 0 and seen == {"expected": {"SHOT-001": PF, "SHOT-002": PF}, "gpu": "G4"}


def test_write_canary_proof_one_shot(tmp_path, monkeypatch):
    folder = _batch(tmp_path)
    manifest = json.loads((folder / "render_manifest.json").read_text(encoding="utf-8"))
    res = tmp_path / "res"
    _make_clip(res, "SHOT-001")
    out = tmp_path / "canary.json"
    r.write_canary_proof(manifest, res, out, owner_ok=True, probe_frames=lambda p: PF)
    proof = json.loads(out.read_text(encoding="utf-8"))
    assert proof["shot"] == "SHOT-001" and proof["clip_verified"] is True and proof["owner_ok"] is True
    assert proof["settings_sha256"] == _sha_of(folder)


def test_write_canary_proof_needs_owner_ok_and_one_shot(tmp_path):
    folder = _batch(tmp_path)
    manifest = json.loads((folder / "render_manifest.json").read_text(encoding="utf-8"))
    res = tmp_path / "res"
    _make_clip(res, "SHOT-001")
    with pytest.raises(r.RunError):
        r.write_canary_proof(manifest, res, tmp_path / "c.json", owner_ok=False, probe_frames=lambda p: PF)
    two = dict(manifest, shots=manifest["shots"] + [{"id": "SHOT-002", "frames": PF, "settings_sha256": "x"}])
    with pytest.raises(r.RunError):
        r.write_canary_proof(two, res, tmp_path / "c.json", owner_ok=True, probe_frames=lambda p: PF)


def test_truncated_canary_clip_refused(tmp_path):
    folder = _batch(tmp_path)
    manifest = json.loads((folder / "render_manifest.json").read_text(encoding="utf-8"))
    res = tmp_path / "res"
    _make_clip(res, "SHOT-001")
    with pytest.raises(r.RunError):
        r.write_canary_proof(manifest, res, tmp_path / "c.json", owner_ok=True, probe_frames=lambda p: 100)
    assert not (tmp_path / "c.json").exists()


# ---- fetch_ready: clip_verified with expected frames ---------------------------------------------

def test_truncated_clip_not_home(tmp_path, monkeypatch):
    state = {"timeline": "END SHOT-001 rc=0 files=[]\n"}

    def fake(args, stdin=None, capture=False, check=True, timeout=None):
        if args[0] == "download" and args[3].endswith("timeline.txt"):
            Path(args[4]).write_text(state["timeline"], encoding="utf-8")
        elif args[0] == "ls":
            return "SHOT-001.mp4\n"
        elif args[0] == "download":
            Path(args[4]).parent.mkdir(parents=True, exist_ok=True)
            Path(args[4]).write_bytes(b"x" * 60000)
        return 0
    monkeypatch.setattr(r, "run_cli", fake)
    got = set()
    assert r.fetch_ready("n", tmp_path, got, {"SHOT-001": PF}, probe_frames=lambda p: 100) == 0
    assert got == set()


def test_full_clip_is_home(tmp_path, monkeypatch):
    def fake(args, stdin=None, capture=False, check=True, timeout=None):
        if args[0] == "download" and args[3].endswith("timeline.txt"):
            Path(args[4]).write_text("END SHOT-001 rc=0 files=[]\n", encoding="utf-8")
        elif args[0] == "ls":
            return "SHOT-001.mp4\n"
        elif args[0] == "download":
            Path(args[4]).parent.mkdir(parents=True, exist_ok=True)
            Path(args[4]).write_bytes(b"x" * 60000)
        return 0
    monkeypatch.setattr(r, "run_cli", fake)
    got = set()
    assert r.fetch_ready("n", tmp_path, got, {"SHOT-001": PF}, probe_frames=lambda p: PF) == 1 and got == {"SHOT-001"}


def test_shot_not_in_batch_not_home(tmp_path, monkeypatch):
    def fake(args, stdin=None, capture=False, check=True, timeout=None):
        if args[0] == "download" and args[3].endswith("timeline.txt"):
            Path(args[4]).write_text("END SHOT-009 rc=0 files=[]\n", encoding="utf-8")
        return 0
    monkeypatch.setattr(r, "run_cli", fake)
    got = set()
    assert r.fetch_ready("n", tmp_path, got, {"SHOT-001": PF}, probe_frames=lambda p: PF) == 0 and not got


def test_name_with_spaces_one_argument(tmp_path, monkeypatch):
    sent = []

    def fake(args, stdin=None, capture=False, check=True, timeout=None):
        if args[0] == "download" and args[3].endswith("timeline.txt"):
            Path(args[4]).write_text("END SHOT-001 rc=0 files=[]\n", encoding="utf-8")
        elif args[0] == "ls":
            return "Picture 1 0.mp4\n"
        elif args[0] == "download":
            sent.append(args[3])
            Path(args[4]).parent.mkdir(parents=True, exist_ok=True)
            Path(args[4]).write_bytes(b"x" * 60000)
        return 0
    monkeypatch.setattr(r, "run_cli", fake)
    got = set()
    r.fetch_ready("n", tmp_path, got, {"SHOT-001": PF}, probe_frames=lambda p: PF)
    assert sent == [f"{t0.OUT}/SHOT-001/Picture 1 0.mp4"]


# ---- batch: stop decision, sessions, dead-man ----------------------------------------------------

def _run_batch(tmp_path, monkeypatch, fetch_ready_fn, after="", ids=("SHOT-001",)):
    calls, state = [], {}
    monkeypatch.setattr(r, "run_cli", _cli(calls, state, HW_LINE, after))
    monkeypatch.setattr(r, "fetch_ready", fetch_ready_fn)
    monkeypatch.setattr(r, "fetch", lambda *a, **k: None)
    expected = {sid: PF for sid in ids}
    err = None
    try:
        r.batch("n", "G4", tmp_path / "run.py", tmp_path / "res", expected=expected, popen=lambda *a, **k: FakeProc(0),
                sleep=lambda s: None, probe_frames=lambda p: PF, hf_token_file=tmp_path / "none.txt")
    except r.RunError as e:
        err = e
    return calls, err


def _ok_ready(name, results, got, *a, **k):
    for sid in ("SHOT-001",):
        _make_clip(results, sid)
        got.add(sid)
    return 1


def test_all_done_verified_stops_then_checks_sessions(tmp_path, monkeypatch):
    calls, err = _run_batch(tmp_path, monkeypatch, _ok_ready)
    assert err is None and "stop" in calls and calls.index("stop") < len(calls) - 1 and calls[-1] == "sessions"


def test_sessions_checked_after_stop_when_clips_verified(tmp_path, monkeypatch):
    calls, err = _run_batch(tmp_path, monkeypatch, _ok_ready)
    assert err is None and calls.index("sessions", calls.index("stop")) == len(calls) - 1


def test_session_still_listed_is_printed(tmp_path, monkeypatch, capsys):
    calls, err = _run_batch(tmp_path, monkeypatch, _ok_ready, after=HW_LINE)
    assert err is None and "SESSION STILL LISTED" in capsys.readouterr().out


def test_missing_clip_keeps_session(tmp_path, monkeypatch, capsys):
    calls, err = _run_batch(tmp_path, monkeypatch, lambda *a, **k: 0)
    out = capsys.readouterr().out
    assert err is not None and "missing clips SHOT-001" in str(err)
    assert "stop" not in calls and "SESSION KEPT" in out


def test_failed_new_reports_stray(tmp_path, monkeypatch, capsys):
    calls = []

    def fake(args, stdin=None, capture=False, check=True, timeout=None):
        calls.append(args[0])
        if args[0] == "new":
            raise r.RunError("colab new failed (exit 1)")
        if args[0] == "sessions":
            return "[n] gpu-g4-s-x | Hardware: G4\n"
        return ""
    monkeypatch.setattr(r, "run_cli", fake)
    with pytest.raises(r.RunError):
        r.batch("n", "G4", tmp_path / "run.py", tmp_path / "res", expected={"SHOT-001": PF},
                popen=lambda *a, **k: FakeProc(0),
                sleep=lambda s: None, hf_token_file=tmp_path / "none.txt")
    assert "STRAY SESSION?: [n] gpu-g4-s-x" in capsys.readouterr().out
    assert calls[-1] == "usage" and calls.index("new") < calls.index("sessions") < len(calls) - 1


def test_deadman_uses_frames_and_clip_count(tmp_path, monkeypatch):
    seen = []
    real = r.rs.deadman_seconds

    def spy(clip, n, **k):
        seen.append((clip, n))
        return real(clip, n, **k)
    monkeypatch.setattr(r.rs, "deadman_seconds", spy)

    def ready2(name, results, got, *a, **k):
        for sid in ("SHOT-001", "SHOT-002"):
            _make_clip(results, sid)
            got.add(sid)
        return 2
    calls, state = [], {}
    monkeypatch.setattr(r, "run_cli", _cli(calls, state))
    monkeypatch.setattr(r, "fetch_ready", ready2)
    monkeypatch.setattr(r, "fetch", lambda *a, **k: None)
    r.batch("n", "G4", tmp_path / "run.py", tmp_path / "res", expected={"SHOT-001": PF, "SHOT-002": PF},
            popen=lambda *a, **k: FakeProc(0), sleep=lambda s: None, probe_frames=lambda p: PF,
            hf_token_file=tmp_path / "none.txt")
    assert seen == [(0.75 * PF, 2)]
    # (900 s setup + 2 clips x 0.75 s x 175 frames) x 1.5, rounded up
    assert r.rs.deadman_seconds(0.75 * PF, 2) == math.ceil((900 + 2 * 0.75 * PF) * 1.5) == 1744


class HangProc(FakeProc):
    def wait(self, timeout=None):
        raise subprocess.TimeoutExpired("colab", timeout)


def test_deadman_limit_is_applied(tmp_path, monkeypatch, capsys):
    # review (Dots): the dead-man value must really end the wait; the clock jumps 100 s per call, the limit is 5 s
    monkeypatch.setattr(r.rs, "deadman_seconds", lambda *a, **k: 5)
    calls, state = [], {}
    monkeypatch.setattr(r, "run_cli", _cli(calls, state))
    monkeypatch.setattr(r, "fetch_ready", lambda *a, **k: 0)
    monkeypatch.setattr(r, "fetch", lambda *a, **k: None)
    ticks = itertools.count(0, 100)
    with pytest.raises(r.RunError, match="run.py exited 124"):
        r.batch("n", "G4", tmp_path / "run.py", tmp_path / "res", expected={"SHOT-001": PF},
                popen=lambda *a, **k: HangProc(0), sleep=lambda s: None, clock=lambda: next(ticks),
                probe_frames=lambda p: PF, hf_token_file=tmp_path / "none.txt")
    assert "BATCH DEADLINE 5 s reached" in capsys.readouterr().out


def test_batch_refuses_without_expected(tmp_path):
    with pytest.raises(ValueError):
        r.batch("n", "G4", tmp_path / "run.py", tmp_path / "res", expected={})


# ---- G8: post-fetch QA fails closed ---------------------------------------------------------------

def _g8(tmp_path, monkeypatch, extra=()):
    _batch(tmp_path)
    monkeypatch.setattr(r, "HERE", tmp_path)
    monkeypatch.setattr(r, "free_checks", lambda *a, **k: [])
    monkeypatch.setattr(r, "run_cli", _cli([]))
    ran = []

    def fake_batch(name, gpu, run_py, results, expected=None, **k):
        ran.append(1)
        d = Path(results) / "SHOT-001"
        d.mkdir(parents=True, exist_ok=True)
        (d / "SHOT-001.mp4").write_bytes(b"x" * 60000)
    monkeypatch.setattr(r, "batch", fake_batch)
    return r.main(["synth", "--results", str(tmp_path / "res"), "--go", *_margs(tmp_path), *extra]), ran


def test_go_without_qa_plan_refused(tmp_path, monkeypatch, capsys):
    code, ran = _g8(tmp_path, monkeypatch)
    out = capsys.readouterr().out
    assert code == 1 and ran == [] and "REFUSED" in out and "--qa-plan" in out


def test_no_qa_flag_recorded_in_history(tmp_path, monkeypatch):
    code, ran = _g8(tmp_path, monkeypatch, ["--no-qa"])
    assert code == 0 and ran == [1]
    doc = json.loads((tmp_path / "res" / "fallback_history.json").read_text(encoding="utf-8"))
    assert doc["qa_skipped"] is True and doc["shots"]["SHOT-001"][0]["qa_skipped"] is True


def test_no_qa_flag_with_plan_is_refused(tmp_path, monkeypatch):
    code, ran = _g8(tmp_path, monkeypatch, ["--no-qa", "--qa-plan", "p.json", "--routes", "r.json", "--pack", "pk"])
    assert code == 1 and ran == []


def test_dry_run_needs_no_qa_plan(tmp_path, monkeypatch):
    _batch(tmp_path)
    monkeypatch.setattr(r, "HERE", tmp_path)
    monkeypatch.setattr(r, "free_checks", lambda *a, **k: [])
    assert r.main(["synth", "--results", str(tmp_path / "res"), *_margs(tmp_path)]) == 0
