"""Offline tests for run_colab_batch.batch: stop on every exit path, the 180 s start proof, and the kept-session case. No colab calls."""
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import run_colab_batch as r  # noqa: E402


class FakeProc:
    def __init__(self, rc=0):
        self.rc = rc
        self.killed = False

    def poll(self):
        return None if not self.killed else -9

    def wait(self, timeout=None):
        if self.rc == "hang":
            raise subprocess.TimeoutExpired("colab", timeout)
        return self.rc

    def kill(self):
        self.killed = True


def setup(monkeypatch, started_answers, fetch_ok=True, rc=0):
    calls = []
    proc = FakeProc(rc)
    answers = iter(started_answers)

    def fake_cli(args, stdin=None, capture=False, check=True, timeout=None):
        calls.append(args[0])
        if args[0] == "sessions":
            return "[n] gpu-g4-s-x | Hardware: G4 | Shape: Standard | Variant: GPU\n"
        if args[0] == "ls":
            return "out/\n" if next(answers, True) else ".config/\n"
        if args[0] == "download" and not fetch_ok:
            raise r.RunError("download failed")
        return ""
    monkeypatch.setattr(r, "run_cli", fake_cli)
    monkeypatch.setattr(r, "fetch", (lambda n, p: None) if fetch_ok else (lambda n, p: (_ for _ in ()).throw(r.RunError("download failed"))))
    return calls, proc


def test_script_never_starts_stops_the_session(monkeypatch):
    calls, proc = setup(monkeypatch, [False] * 50)
    with pytest.raises(r.RunError, match="did not start"):
        r.batch("n", "G4", Path("x.py"), "res", proof_seconds=30, poll=15, popen=lambda *a, **k: proc, sleep=lambda s: None)
    assert proc.killed and calls[-1] == "stop"


def test_normal_run_stops_after_fetch(monkeypatch):
    calls, proc = setup(monkeypatch, [True])
    r.batch("n", "G4", Path("x.py"), "res", popen=lambda *a, **k: proc, sleep=lambda s: None)
    assert calls[0] == "usage" and "new" in calls and calls[-1] == "stop"


def test_failed_download_keeps_the_session(monkeypatch, capsys):
    calls, proc = setup(monkeypatch, [True], fetch_ok=False)
    with pytest.raises(r.RunError):
        r.batch("n", "G4", Path("x.py"), "res", popen=lambda *a, **k: proc, sleep=lambda s: None)
    assert "stop" not in calls and "SESSION KEPT" in capsys.readouterr().out


def test_run_error_after_fetch_still_stops(monkeypatch):
    calls, proc = setup(monkeypatch, [True], rc=1)
    with pytest.raises(r.RunError, match="exited 1"):
        r.batch("n", "G4", Path("x.py"), "res", popen=lambda *a, **k: proc, sleep=lambda s: None)
    assert calls[-1] == "stop"


def test_hard_deadline_fetches_then_stops(monkeypatch):
    calls, proc = setup(monkeypatch, [True], rc="hang")
    with pytest.raises(r.RunError, match="exited 124"):
        r.batch("n", "G4", Path("x.py"), "res", popen=lambda *a, **k: proc, sleep=lambda s: None, max_seconds=5,
                clock=iter(range(0, 1000, 100)).__next__)
    assert proc.killed and calls[-1] == "stop"


def test_clip_is_saved_as_soon_as_its_shot_ends(monkeypatch, tmp_path):
    state = {"timeline": "START SHOT-001\nEND SHOT-001 rc=0 files=['a.mp4']\nSTART SHOT-002\n"}
    downloads = []

    def fake_cli(args, stdin=None, capture=False, check=True, timeout=None):
        if args[0] == "download" and args[3].endswith("timeline.txt"):
            Path(args[4]).write_text(state["timeline"], encoding="utf-8")
            return 0
        if args[0] == "ls":
            return "a.mp4\nnotes.txt\n"
        if args[0] == "download":
            Path(args[4]).write_bytes(b"x" * 60_000)
            downloads.append(args[3])
            return 0
        return 0
    monkeypatch.setattr(r, "run_cli", fake_cli)
    got = set()
    assert r.fetch_ready("n", tmp_path, got) == 1 and got == {"SHOT-001"}
    assert (tmp_path / "SHOT-001" / "a.mp4").stat().st_size == 60_000
    assert r.fetch_ready("n", tmp_path, got) == 0 and len(downloads) == 1     # not fetched twice
    state["timeline"] += "END SHOT-002 rc=0 files=['b.mp4']\n"
    assert r.fetch_ready("n", tmp_path, got) == 1 and got == {"SHOT-001", "SHOT-002"}


def test_a_failed_shot_is_not_marked_home(monkeypatch, tmp_path):
    def fake_cli(args, stdin=None, capture=False, check=True, timeout=None):
        if args[0] == "download" and args[3].endswith("timeline.txt"):
            Path(args[4]).write_text("END SHOT-001 rc=1 files=[]\n", encoding="utf-8")
            return 0
        return 0
    monkeypatch.setattr(r, "run_cli", fake_cli)
    got = set()
    assert r.fetch_ready("n", tmp_path, got) == 0 and not got


def test_uploads_run_before_the_script(monkeypatch, tmp_path):
    (tmp_path / "upload_00.py").write_text("x=1")
    (tmp_path / "upload_01.py").write_text("x=2")
    calls, proc = setup(monkeypatch, [True])
    r.batch("n", "G4", tmp_path / "run.py", "res", popen=lambda *a, **k: proc, sleep=lambda s: None)
    assert calls[:5] == ["usage", "new", "sessions", "exec", "exec"] and calls[-1] == "stop"


def test_wrong_gpu_is_stopped(monkeypatch):
    calls = []

    def fake_cli(args, stdin=None, capture=False, check=True, timeout=None):
        calls.append(args[0])
        return "[n] gpu-t4-s-x | Hardware: T4 | Shape: Standard\n" if args[0] == "sessions" else ""
    monkeypatch.setattr(r, "run_cli", fake_cli)
    with pytest.raises(r.RunError, match="not G4"):
        r.batch("n", "G4", Path("x.py"), "res", popen=lambda *a, **k: FakeProc(), sleep=lambda s: None)
    assert "exec" not in calls and calls[-1] == "stop"


def test_one_failed_download_does_not_strand_the_rest(monkeypatch, tmp_path):
    got = []

    def fake_cli(args, stdin=None, capture=False, check=True, timeout=None):
        if args[0] == "download" and args[3].endswith("FILES.txt"):
            Path(args[4]).write_text("a/a.mp4\nb/b clip with spaces.mp4\n", encoding="utf-8")
        elif args[0] == "download" and args[3].endswith("a.mp4"):
            raise r.RunError("boom")
        elif args[0] == "download":
            Path(args[4]).write_bytes(b"x" * 60_000)
            got.append(args[3])
        return ""
    monkeypatch.setattr(r, "run_cli", fake_cli)
    with pytest.raises(r.RunError, match="did not come home"):
        r.fetch("n", tmp_path)
    assert any(g.endswith("b clip with spaces.mp4") for g in got)      # a name with spaces stays ONE path
