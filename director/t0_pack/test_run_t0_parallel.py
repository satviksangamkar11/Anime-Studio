"""G2: run_t0_parallel takes --batch and --results, writes status.json, and stays a dry run without --go.
Every Colab call is faked in memory: no CLI, no network, no spend."""
import base64
import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import run_t0_parallel as g  # noqa: E402

IDS = ["SHOT-T0-A-S42", "SHOT-T0-B-S42"]


def write_batch(folder: Path, ids=IDS):
    folder.mkdir(parents=True, exist_ok=True)
    blob = base64.b64encode(json.dumps({sid: {"prompt": "x"} for sid in ids}).encode()).decode()
    (folder / "run.py").write_text(f'images = b64decode("{blob}")\n', encoding="utf-8")
    return folder


class FakeColab:
    """Remembers sessions and remote files; `stop_leaves` keeps the session listed after stop."""

    def __init__(self, clips=IDS, missing=(), stop_leaves=False, fail_new=False):
        self.sessions, self.calls, self.stop_leaves, self.fail_new = set(), [], stop_leaves, fail_new
        self.remote = {f"/content/out/{sid}/{sid}.mp4": b"x" * 200_000 for sid in clips if sid not in missing}

    def __call__(self, args, timeout=600, **kw):
        self.calls.append(list(args))
        verb, out, rc = args[0], "", 0
        if verb == "usage":
            out = "Balance: 120.5 units"
        elif verb == "new":
            rc = 1 if self.fail_new else 0
            out = "" if self.fail_new else "session started"
            if not self.fail_new:
                self.sessions.add(args[2])
        elif verb == "sessions":
            out = "\n".join(sorted(self.sessions)) or "no sessions"
        elif verb == "stop":
            if not self.stop_leaves:
                self.sessions.discard(args[-1])
            out = "stopped"
        elif verb == "ls":
            path = args[-1]
            if path == "/content/out":
                entries = sorted({p.split("/")[3] + "/" for p in self.remote})
            else:
                entries = [p.split("/")[-1] for p in self.remote if p.startswith(path + "/")]
            out = "\n".join(entries)
        elif verb == "download":
            remote, local = args[-2], args[-1]
            if remote not in self.remote:
                return subprocess.CompletedProcess(args, 1, "", "not found")
            Path(local).parent.mkdir(parents=True, exist_ok=True)
            Path(local).write_bytes(self.remote[remote])
        return subprocess.CompletedProcess(args, rc, out, "")


class FakePopen:
    """The batch 'exec' finishes at once; the clips are already in the fake remote."""

    def __init__(self, argv, stdout=None, stderr=None, **kw):
        self.argv, self.returncode = argv, 0

    def poll(self):
        return self.returncode


@pytest.fixture
def rig(tmp_path, monkeypatch):
    batch = write_batch(tmp_path / "batch")
    results = tmp_path / "batch" / "results"

    def install(colab):
        monkeypatch.setattr(g, "cli", colab)
        monkeypatch.setattr(g, "playable", lambda p: True)
        monkeypatch.setattr(g, "subprocess", SimpleNamespace(Popen=FakePopen, STDOUT=subprocess.STDOUT, run=subprocess.run))
        return colab
    return batch, results, install


def status(results: Path):
    return json.loads((results / "status.json").read_text(encoding="utf-8"))


def test_dry_run_is_the_default_and_calls_nothing(rig):
    batch, results, install = rig

    def no_call(*a, **k):
        raise AssertionError("a dry run must not call Colab")
    install(no_call)
    assert g.main(["--batch", str(batch), "--results", str(results)]) == 0
    assert not results.exists()


def test_real_run_with_every_clip_home_stops_and_writes_status(rig, capsys):
    batch, results, install = rig
    colab = install(FakeColab())
    assert g.main(["--go", "--batch", str(batch), "--results", str(results), "--name", "t0-test"]) == 0
    st = status(results)
    assert st["rc"] == 0 and st["stop_verified"] is True and st["missing"] == [] and st["home"] == sorted(IDS)
    assert st["session"] == "t0-test" and st["expected"] == sorted(IDS) and st["started"] is True
    assert "120.5" in st["usage_before"] and "120.5" in st["usage_after"]
    assert (results / "SHOT-T0-A-S42" / "SHOT-T0-A-S42.mp4").is_file()
    assert ["stop", "-s", "t0-test"] in colab.calls


def test_missing_clip_keeps_the_session_and_says_so(rig, capsys):
    batch, results, install = rig
    colab = install(FakeColab(missing=("SHOT-T0-B-S42",)))
    assert g.main(["--go", "--batch", str(batch), "--results", str(results), "--name", "t0-test"]) == 2
    st = status(results)
    assert st["rc"] == 2 and st["missing"] == ["SHOT-T0-B-S42"] and st["stop_verified"] is False
    assert not any(c[0] == "stop" for c in colab.calls)
    assert "SESSION KEPT" in capsys.readouterr().out


def test_a_stop_that_leaves_the_session_listed_is_reported(rig, capsys):
    batch, results, install = rig
    install(FakeColab(stop_leaves=True))
    assert g.main(["--go", "--batch", str(batch), "--results", str(results), "--name", "t0-test"]) == 3
    st = status(results)
    assert st["rc"] == 3 and st["stop_verified"] is False
    assert "STOP FAILED" in capsys.readouterr().out


def test_a_session_that_cannot_start_writes_status_and_no_exec(rig, capsys):
    batch, results, install = rig
    install(FakeColab(fail_new=True))
    assert g.main(["--go", "--batch", str(batch), "--results", str(results)]) == 1
    st = status(results)
    assert st["rc"] == 1 and st["started"] is False and st["missing"] == sorted(IDS)
