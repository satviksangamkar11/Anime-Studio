import hashlib
import os
import math
import shutil
import subprocess
import urllib.error
from pathlib import Path
import pytest
import runner_safety

FRAMES = 192


def _probe(path):
    return FRAMES


def _script(tmp_path):
    s = tmp_path / "run.py"
    s.write_bytes(b"print(1)\n")
    return s


def _make_junction(link, target):
    # Windows directory junction; needs no admin. Returns False only if creation fails.
    try:
        subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(target)],
                       check=True, capture_output=True)
    except (OSError, subprocess.CalledProcessError):
        return False
    return link.exists()


def test_clip_verified_real_file(tmp_path):
    shot_dir = tmp_path / "shot1"
    shot_dir.mkdir()
    clip = shot_dir / "shot1.mp4"
    clip.write_bytes(b"x" * 50_001)
    assert runner_safety.clip_verified(tmp_path, "shot1", FRAMES, probe_frames=_probe) is True


def test_clip_verified_too_small(tmp_path):
    shot_dir = tmp_path / "shot2"
    shot_dir.mkdir()
    clip = shot_dir / "shot2.mp4"
    clip.write_bytes(b"x" * 49_999)
    assert runner_safety.clip_verified(tmp_path, "shot2", FRAMES, probe_frames=_probe) is False


def test_clip_verified_missing(tmp_path):
    assert runner_safety.clip_verified(tmp_path, "shot3", FRAMES, probe_frames=_probe) is False


def test_clip_verified_injected(tmp_path):
    class FakeExists:
        def __call__(self, p):
            return True

    class FakeSize:
        def __call__(self, p):
            return 60_000

    assert runner_safety.clip_verified(tmp_path, "shot4", FRAMES, probe_frames=_probe,
                                       exists=FakeExists(), size=FakeSize()) is True


def test_can_stop_all_verified(tmp_path):
    for sid in ["a", "b"]:
        d = tmp_path / sid
        d.mkdir()
        (d / (sid + ".mp4")).write_bytes(b"x" * 50_001)
    ok, missing = runner_safety.can_stop(["a", "b"], tmp_path,
                                         expected_frames={"a": FRAMES, "b": FRAMES}, probe_frames=_probe)
    assert ok is True
    assert missing == []


def test_can_stop_one_missing(tmp_path):
    d = tmp_path / "a"
    d.mkdir()
    (d / "a.mp4").write_bytes(b"x" * 50_001)
    ok, missing = runner_safety.can_stop(["a", "b"], tmp_path,
                                         expected_frames={"a": FRAMES, "b": FRAMES}, probe_frames=_probe)
    assert ok is False
    assert missing == ["b"]


def test_can_stop_empty_raises(tmp_path):
    try:
        runner_safety.can_stop([], tmp_path, expected_frames={})
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError")


def test_stop_decision_not_finished(tmp_path):
    res = runner_safety.stop_decision(["a"], tmp_path, all_done=False, expected_frames={"a": FRAMES})
    assert res["stop"] is False
    assert res["reason"] == "not finished"
    assert res["missing"] == []


def test_stop_decision_all_done_all_verified(tmp_path):
    for sid in ["a"]:
        d = tmp_path / sid
        d.mkdir()
        (d / (sid + ".mp4")).write_bytes(b"x" * 50_001)
    res = runner_safety.stop_decision(["a"], tmp_path, all_done=True,
                                      expected_frames={"a": FRAMES}, probe_frames=_probe)
    assert res["stop"] is True
    assert res["reason"] == "all clips verified"
    assert res["missing"] == []


def test_stop_decision_all_done_missing(tmp_path):
    res = runner_safety.stop_decision(["a", "b"], tmp_path, all_done=True,
                                      expected_frames={"a": FRAMES, "b": FRAMES}, probe_frames=_probe)
    assert res["stop"] is False
    assert "a" in res["reason"]
    assert "b" in res["reason"]
    assert "kept" in res["reason"]
    assert res["missing"] == ["a", "b"]


def test_deadman_seconds():
    val = runner_safety.deadman_seconds(120.0, 10)
    expected = math.ceil((900 + 120.0 * 10) * 1.5)
    assert val == expected


def test_deadman_seconds_invalid():
    for args in [(-1.0, 1), (0.0, 1), (float("nan"), 1), (float("inf"), 1),
                 (1.0, 0), (1.0, -1), (1.0, 1, -900), (1.0, 1, 900, -1.5)]:
        try:
            runner_safety.deadman_seconds(*args)
        except ValueError:
            continue
        raise AssertionError("expected ValueError for " + str(args))


def test_wheel_ok_true(tmp_path):
    p = tmp_path / "chumpy.whl"
    p.write_bytes(b"data")
    digest = hashlib.sha256(b"data").hexdigest()
    assert runner_safety.wheel_ok(p, digest) is True


def test_wheel_ok_false(tmp_path):
    p = tmp_path / "chumpy.whl"
    p.write_bytes(b"data")
    assert runner_safety.wheel_ok(p, "deadbeef") is False


def test_wheel_ok_case_insensitive(tmp_path):
    p = tmp_path / "chumpy.whl"
    p.write_bytes(b"data")
    digest = hashlib.sha256(b"data").hexdigest().upper()
    assert runner_safety.wheel_ok(p, digest) is True


def test_wheel_ok_missing(tmp_path):
    assert runner_safety.wheel_ok(tmp_path / "nope.whl", "abc") is False


def test_preflight_all_pass(tmp_path, monkeypatch):
    def head(url):
        return 200

    monkeypatch.setattr(runner_safety, "_default_head", head)
    monkeypatch.setattr(shutil, "disk_usage", lambda p: type("U", (), {"free": 100 * 1024 ** 3})())
    res = runner_safety.preflight(["http://example.com"], tmp_path, min_free_gb=5, script_path=_script(tmp_path))
    assert res == []


def test_preflight_504(tmp_path, monkeypatch):
    def head(url):
        return 504

    monkeypatch.setattr(runner_safety, "_default_head", head)
    monkeypatch.setattr(shutil, "disk_usage", lambda p: type("U", (), {"free": 100 * 1024 ** 3})())
    res = runner_safety.preflight(["http://bad.com"], tmp_path, min_free_gb=5, script_path=_script(tmp_path))
    assert len(res) == 1
    assert "504" in res[0]


def test_preflight_url_exception(tmp_path, monkeypatch):
    def head(url):
        raise OSError("boom")

    monkeypatch.setattr(runner_safety, "_default_head", head)
    monkeypatch.setattr(shutil, "disk_usage", lambda p: type("U", (), {"free": 100 * 1024 ** 3})())
    res = runner_safety.preflight(["http://bad.com"], tmp_path, min_free_gb=5, script_path=_script(tmp_path))
    assert len(res) == 1
    assert "OSError" in res[0]


def test_preflight_disk_low(tmp_path, monkeypatch):
    def head(url):
        return 200

    monkeypatch.setattr(runner_safety, "_default_head", head)
    monkeypatch.setattr(shutil, "disk_usage", lambda p: type("U", (), {"free": 1024 ** 3})())
    res = runner_safety.preflight(["http://example.com"], tmp_path, min_free_gb=5, script_path=_script(tmp_path))
    assert any("disk" in r.lower() for r in res)


def test_preflight_key_check_raise(tmp_path, monkeypatch):
    def head(url):
        return 200

    monkeypatch.setattr(runner_safety, "_default_head", head)
    monkeypatch.setattr(shutil, "disk_usage", lambda p: type("U", (), {"free": 100 * 1024 ** 3})())

    def bad_check():
        raise RuntimeError("secret leak")

    res = runner_safety.preflight(["http://example.com"], tmp_path, min_free_gb=5,
                                  script_path=_script(tmp_path), key_checks={"api_key": bad_check})
    assert any("api_key" in r for r in res)
    assert all("secret leak" not in r for r in res)


def test_11_3mb_script_ok_in_parts(tmp_path):
    # owner decision 6: no whole-script cap; the 11.3 MB script goes up in parts of <= 3 MB
    script = tmp_path / "run.py"
    script.write_bytes(b"x" * int(11.3 * 1024 * 1024))
    parts = []
    for i in range(4):
        p = tmp_path / ("part" + str(i) + ".txt")
        p.write_bytes(b"x" * (3 * 1024 * 1024))
        parts.append(p)
    res = runner_safety.preflight(["http://example.com"], tmp_path, min_free_gb=5,
                                  script_path=script, part_paths=parts,
                                  head=lambda url: 200, disk_usage=lambda p: type("U", (), {"free": 100 * 1024 ** 3})())
    assert res == []


def test_part_over_3mb_fails(tmp_path):
    script = _script(tmp_path)
    part = tmp_path / "part0.txt"
    part.write_bytes(b"x" * (3 * 1024 * 1024 + 1))
    res = runner_safety.preflight(["http://example.com"], tmp_path, min_free_gb=5,
                                  script_path=script, part_paths=[part],
                                  head=lambda url: 200, disk_usage=lambda p: type("U", (), {"free": 100 * 1024 ** 3})())
    assert any("part too large" in r for r in res)


def test_script_path_required(tmp_path):
    try:
        runner_safety.preflight(["http://example.com"], tmp_path, min_free_gb=5)
    except TypeError:
        pass
    else:
        raise AssertionError("expected TypeError: script_path has no default")


def test_empty_urls_refused(tmp_path):
    try:
        runner_safety.preflight([], tmp_path, min_free_gb=5, script_path=_script(tmp_path))
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError for empty urls")


def test_head_405_get_206_ok(tmp_path, monkeypatch):
    import urllib.request

    class FakeResp:
        def __init__(self, status):
            self.status = status

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def fake_urlopen(req, timeout=10):
        if req.get_method() == "HEAD":
            raise urllib.error.HTTPError(req.full_url, 405, "Method Not Allowed", {}, None)
        assert req.get_method() == "GET"
        assert req.get_header("Range") == "bytes=0-0"
        return FakeResp(206)

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    res = runner_safety.preflight(["http://example.com"], tmp_path, min_free_gb=5,
                                  script_path=_script(tmp_path),
                                  disk_usage=lambda p: type("U", (), {"free": 100 * 1024 ** 3})())
    assert res == []


def test_can_stop_empty_list_raises_flat(tmp_path):
    try:
        runner_safety.can_stop([], tmp_path, expected_frames={})
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError for empty expected list")


def test_can_stop_and_stop_decision_refuse_49999_byte_clip(tmp_path):
    d = tmp_path / "a"
    d.mkdir()
    (d / "a.mp4").write_bytes(b"x" * 49_999)
    ok, missing = runner_safety.can_stop(["a"], tmp_path, expected_frames={"a": FRAMES}, probe_frames=_probe)
    assert ok is False
    assert missing == ["a"]
    res = runner_safety.stop_decision(["a"], tmp_path, all_done=True,
                                      expected_frames={"a": FRAMES}, probe_frames=_probe)
    assert res["stop"] is False
    assert res["missing"] == ["a"]


def test_deadman_non_finite_inputs_refused():
    for bad in (math.inf, math.nan):
        for args in ((bad, 10), (120.0, bad), (120.0, 10, bad), (120.0, 10, 900, bad)):
            try:
                runner_safety.deadman_seconds(*args)
            except ValueError:
                pass
            else:
                raise AssertionError(f"expected ValueError for {args!r}")


def test_clip_verified_traversal_ids_refused(tmp_path):
    results = tmp_path / "res"
    results.mkdir()
    outside = tmp_path / "x"
    outside.mkdir()
    (outside / "x.mp4").write_bytes(b"x" * 50_001)
    assert runner_safety.clip_verified(results, "../x", FRAMES, probe_frames=_probe) is False
    for bad in (".", "..", "a/b", "a\\b", ""):
        assert runner_safety.clip_verified(results, bad, FRAMES, probe_frames=_probe) is False


def test_clip_verified_exact_50000_bytes_not_verified(tmp_path):
    shot_dir = tmp_path / "shot5"
    shot_dir.mkdir()
    (shot_dir / "shot5.mp4").write_bytes(b"x" * 50_000)
    assert runner_safety.clip_verified(tmp_path, "shot5", FRAMES, probe_frames=_probe) is False


def test_clip_verified_directory_named_mp4_not_a_clip(tmp_path):
    shot_dir = tmp_path / "shot6"
    shot_dir.mkdir()
    (shot_dir / "shot6.mp4").mkdir()
    assert runner_safety.clip_verified(tmp_path, "shot6", FRAMES, probe_frames=_probe) is False


def test_stop_decision_non_bool_all_done_does_not_stop(tmp_path):
    d = tmp_path / "a"
    d.mkdir()
    (d / "a.mp4").write_bytes(b"x" * 50_001)
    for value in ("no", 1, None):
        res = runner_safety.stop_decision(["a"], tmp_path, all_done=value,
                                          expected_frames={"a": FRAMES}, probe_frames=_probe)
        assert res["stop"] is False, f"stopped for all_done={value!r}"


def test_can_stop_string_expected_ids_raises(tmp_path):
    try:
        runner_safety.can_stop("abc", tmp_path, expected_frames={})
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError for plain str expected_ids")


def test_wheel_ok_directory_returns_false(tmp_path):
    d = tmp_path / "chumpy.whl"
    d.mkdir()
    assert runner_safety.wheel_ok(d, hashlib.sha256(b"").hexdigest()) is False


def test_preflight_http_error_status_in_message(tmp_path, monkeypatch):
    def head(url):
        raise urllib.error.HTTPError(url, 503, "Service Unavailable", {}, None)

    monkeypatch.setattr(runner_safety, "_default_head", head)
    monkeypatch.setattr(shutil, "disk_usage", lambda p: type("U", (), {"free": 100 * 1024 ** 3})())
    res = runner_safety.preflight(["http://bad.com"], tmp_path, min_free_gb=5, script_path=_script(tmp_path))
    assert len(res) == 1
    assert "HTTP 503" in res[0]


def test_preflight_key_check_returning_false_reported(tmp_path, monkeypatch):
    def head(url):
        return 200

    monkeypatch.setattr(runner_safety, "_default_head", head)
    monkeypatch.setattr(shutil, "disk_usage", lambda p: type("U", (), {"free": 100 * 1024 ** 3})())
    res = runner_safety.preflight(["http://example.com"], tmp_path, min_free_gb=5,
                                  script_path=_script(tmp_path), key_checks={"api_key": lambda: False})
    assert any("api_key" in r for r in res)


def test_deadman_fractional_and_bool_clip_counts_refused():
    for args in ((120.0, 0.5), (120.0, True)):
        try:
            runner_safety.deadman_seconds(*args)
        except ValueError:
            pass
        else:
            raise AssertionError(f"expected ValueError for {args!r}")


def test_stop_only_when_all_done_and_all_clips_verified(tmp_path):
    d = tmp_path / "a"
    d.mkdir()
    (d / "a.mp4").write_bytes(b"x" * 50_001)
    # all_done True but clip "c" missing: refused
    fr = {"a": FRAMES, "c": FRAMES}
    assert runner_safety.stop_decision(["a", "c"], tmp_path, all_done=True,
                                       expected_frames=fr, probe_frames=_probe)["stop"] is False
    # clips present but not finished: refused
    assert runner_safety.stop_decision(["a"], tmp_path, all_done=False,
                                       expected_frames=fr, probe_frames=_probe)["stop"] is False
    # both hold: allowed
    assert runner_safety.stop_decision(["a"], tmp_path, all_done=True,
                                       expected_frames=fr, probe_frames=_probe)["stop"] is True


def test_trailing_dot_id_does_not_resolve_to_real_clip(tmp_path):
    # seventh run: Windows strips the trailing dot, so "a." must not reach the real clip of "a"
    d = tmp_path / "a"
    d.mkdir()
    (d / "a.mp4").write_bytes(b"x" * 50_001)
    assert runner_safety.clip_verified(tmp_path, "a.", FRAMES, probe_frames=_probe) is False
    assert runner_safety.stop_decision(["a."], tmp_path, all_done=True,
                                       expected_frames={"a.": FRAMES}, probe_frames=_probe)["stop"] is False


def test_drive_relative_id_is_refused(tmp_path):
    # seventh run: "C:outside" is a drive-relative escape; refused even with a real clip for "a" present
    d = tmp_path / "a"
    d.mkdir()
    (d / "a.mp4").write_bytes(b"x" * 50_001)
    assert runner_safety.clip_verified(tmp_path, "C:outside", FRAMES, probe_frames=_probe) is False
    fr = {"a": FRAMES, "C:outside": FRAMES}
    assert runner_safety.stop_decision(["a", "C:outside"], tmp_path, all_done=True,
                                       expected_frames=fr, probe_frames=_probe)["stop"] is False


def test_injected_size_exactly_50_000_is_not_verified(tmp_path):
    # seventh run: the threshold is strictly greater than 50_000
    assert runner_safety.clip_verified(
        tmp_path, "s", FRAMES, probe_frames=_probe, exists=lambda p: True, size=lambda p: 50_000
    ) is False


def test_deadman_seconds_one_clip_estimate_one_is_1352():
    # seventh run: ceil((900 + 1.0 * 1) * 1.5) = ceil(1351.5) = 1352
    assert runner_safety.deadman_seconds(1.0, 1) == 1352


def test_clip_verified_injected_checks_exact_candidate_path(tmp_path):
    # round 9 (observer 8): the injected functions must be called with <results_dir>/shot4/shot4.mp4 only
    seen_exists = []
    seen_size = []

    def fake_exists(p):
        seen_exists.append(p)
        return True

    def fake_size(p):
        seen_size.append(p)
        return 60_000

    assert runner_safety.clip_verified(tmp_path, "shot4", FRAMES, probe_frames=_probe,
                                       exists=fake_exists, size=fake_size) is True
    expected = Path(tmp_path) / "shot4" / "shot4.mp4"
    assert seen_exists == [expected]
    assert seen_size == [expected]


def test_wrong_frame_count_not_verified(tmp_path):
    # ffprobe says 100 frames, the editorial cut needs 192: the clip is not verified
    shot_dir = tmp_path / "a"
    shot_dir.mkdir()
    (shot_dir / "a.mp4").write_bytes(b"x" * 50_001)
    assert runner_safety.clip_verified(tmp_path, "a", 192, probe_frames=lambda p: 100) is False
    assert runner_safety.clip_verified(tmp_path, "a", 192, probe_frames=lambda p: 192) is True


def test_part_file_ignored(tmp_path):
    # an in-progress upload (*.part.mp4 / *.tmp.mp4) never counts as a clip
    shot_dir = tmp_path / "a"
    shot_dir.mkdir()
    (shot_dir / "a.part.mp4").write_bytes(b"x" * 50_001)
    (shot_dir / "a.tmp.mp4").write_bytes(b"x" * 50_001)
    assert runner_safety.clip_verified(tmp_path, "a", FRAMES, probe_frames=_probe) is False


def test_injected_escape_refused(tmp_path):
    # E3 on the injected path: folder "b" is a junction to "a"; a clip for "a" must not verify "b"
    results = tmp_path / "results"
    a = results / "a"
    a.mkdir(parents=True)
    if not _make_junction(results / "b", a):
        pytest.skip("junction cannot be created on this system")
    assert runner_safety.clip_verified(results, "b", FRAMES, probe_frames=_probe,
                                       exists=lambda p: True, size=lambda p: 60_000) is False


def test_clip_verified_symlinked_shot_dir_outside_results_refused(tmp_path):
    # round 9 (observer 8): a shot folder that is a symlink resolving outside results_dir is not a clip
    results = tmp_path / "results"
    results.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "shot5.mp4").write_bytes(b"x" * 50_001)
    if not _make_junction(results / "shot5", outside):
        pytest.skip("junction cannot be created on this system")
    assert runner_safety.clip_verified(results, "shot5", FRAMES, probe_frames=_probe) is False
    assert runner_safety.stop_decision(["shot5"], results, all_done=True,
                                       expected_frames={"shot5": FRAMES}, probe_frames=_probe)["stop"] is False


def test_shot_id_control_characters_refused(tmp_path):
    # round 9 (observer 8): DEL (127) and C1 controls (128-159) are control characters and must be refused.
    # DEL already passes; the C1 cases FAIL until runner_safety._valid_shot_id rejects 128-159 (spec round 9).
    def yes_exists(p):
        return True

    def big(p):
        return 60_000

    for bad in ("a\x7fb", "a\x85b", "a\x9fb"):
        assert runner_safety.clip_verified(tmp_path, bad, FRAMES, probe_frames=_probe,
                                           exists=yes_exists, size=big) is False, repr(bad)


def test_sibling_junction_does_not_verify_missing_clip(tmp_path):
    # eleventh run: results/b is a junction to results/a; the clip of "a" must not verify "b".
    # FAILS until clip_verified compares clip_dir.resolve() to results.resolve() / shot_id.
    results = tmp_path / "results"
    a = results / "a"
    a.mkdir(parents=True)
    (a / "a.mp4").write_bytes(b"x" * 50_001)
    if not _make_junction(results / "b", a):
        pytest.skip("junction cannot be created on this system")
    assert runner_safety.clip_verified(results, "a", FRAMES, probe_frames=_probe) is True
    assert runner_safety.clip_verified(results, "b", FRAMES, probe_frames=_probe) is False
    assert runner_safety.stop_decision(["b"], results, all_done=True,
                                       expected_frames={"b": FRAMES}, probe_frames=_probe)["stop"] is False


def test_preflight_non_int_head_status_reported_not_raised(tmp_path, monkeypatch):
    # eleventh run: a non-int status from the injected head is a failure string, never a TypeError.
    # FAILS until preflight reports "<url>: invalid status <value>".
    monkeypatch.setattr(shutil, "disk_usage", lambda p: type("U", (), {"free": 100 * 1024 ** 3})())
    for bad in ("200", None):
        monkeypatch.setattr(runner_safety, "_default_head", lambda url, v=bad: v)
        res = runner_safety.preflight(["http://example.com"], tmp_path, min_free_gb=5, script_path=_script(tmp_path))
        assert len(res) == 1, repr(bad)
        assert isinstance(res[0], str)
        assert "invalid status" in res[0], repr(bad)
