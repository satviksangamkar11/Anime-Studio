"""Offline tests for the Anime Studio control UI (ui/PLAN.md section 7, groups 1-14).
Fake tools only: every script the UI can run is a small Python fake written into pytest's tmp folder. No network, no Colab,
no NVIDIA, no Claude, no Flow. The only real-data reads are the optional smoke test (group 14), which writes nothing."""
import ast
import http.client
import json
import os
import re
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import server  # noqa: E402
from server import ApiError  # noqa: E402

WRITER = "nvidia/nemotron-3-ultra-550b-a55b"
VISION = "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning"
EDIT = "34ba531b-b5c7-43fa-82a5-7b7746b57016"
PACK = "stories/kaliya_mardan/pack_x"

FAKE_TOOL = 'import json, sys, time\nprint("ARGV " + json.dumps(sys.argv[1:]))\nif any("slow" in a for a in sys.argv[1:]):\n    time.sleep(30)\n'
# like the real bridge: --json prints the JSON list and nothing else, and exits 1 when a record is REFUSED
FAKE_BRIDGE = ('import json, sys\nargv = sys.argv[1:]\n'
               'if "--json" not in argv:\n    print("ARGV " + json.dumps(argv))\n    sys.exit(0)\n'
               'recs = [{"label": "LEAP-03A", "status": "DRY" if "--dry-run" in argv else "OK", "box": [0, 0, 1, 1]},\n'
               '        {"label": "LEAP-04A", "status": "REFUSED", "reason": "aspect off"}]\n'
               'print(json.dumps(recs))\nsys.exit(1)\n')
FAKE_COLAB = '''import json, sys
from pathlib import Path
state_p = Path(__file__).with_name("colab_state.json")
st = json.loads(state_p.read_text(encoding="utf-8")) if state_p.exists() else {"sessions": [], "balance": 120.5, "stuck": False}
args = sys.argv[1:]
verb = args[0] if args else ""
if verb == "usage":
    print("Balance: %s units" % st["balance"] if st.get("balance") is not None else "usage: no figure here")
elif verb == "sessions":
    print("\\n".join("%s  G4  running" % n for n in st["sessions"]) or "no sessions")
elif verb == "new":
    st["sessions"].append(args[args.index("-s") + 1])
elif verb == "stop":
    name = args[args.index("-s") + 1]
    if not st.get("stuck"):
        st["sessions"] = [n for n in st["sessions"] if n != name]
    print("stopped " + name)
state_p.write_text(json.dumps(st), encoding="utf-8")
'''
SHOTS = [
    {"id": "SHOT-01", "episode": 1, "mode": "fl2va", "seconds": 8.0, "cut_in": "cold open", "cut_out": "cut to SHOT-02"},
    {"id": "SHOT-02", "episode": 1, "mode": "fl2va", "seconds": 8.5, "cut_in": "match", "cut_out": "cut to SHOT-03"},
    {"id": "SHOT-03", "episode": 2, "mode": "fl2va", "seconds": 9.0, "cut_in": "match", "cut_out": "cut to SHOT-04"},
    {"id": "SHOT-04", "episode": 2, "mode": "fl2va", "seconds": 7.0, "cut_in": "match", "cut_out": "end"},
]
PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 64
GOOD_PACK = "stories/kaliya_mardan/pack_good"   # a pack pack_to_spec accepts (group 15)
GOOD_SHOTS = [{"id": "SHOT-G1", "scene": "SCENE-G", "episode": 1, "mode": "fl2va", "seconds": 8.0, "aspect": "9:16",
               "set": "ENV-DAH", "cast": [{"id": "CHAR-KRISHNA", "screen": "left", "facing": "right"}],
               "props": [{"id": "PROP-FLUTE", "where": "in hand"}],
               "camera": {"start_framing": "medium", "end_framing": "close", "height": "eye level"},
               "start_state": "Krishna stands at the water's edge with the flute raised",
               "end_state": "Krishna lowers the flute toward the river",
               "light": {"key": "low sun from screen left", "mood": "soft haze", "rim": "none"},
               "keyframes": {"start": "keyframes/SHOT-G1_start.png", "end": "keyframes/SHOT-G1_end.png"}}]
GOOD_BIBLE = {"characters": {"CHAR-KRISHNA": {"name": "Krishna", "age": "young adult", "heads": 7.5, "attributes": ["blue skin"]}},
              "environments": {"ENV-DAH": {"name": "Dah", "layers": ["FG_reeds", "BG_hills"], "light": "low sun"}},
              "props": {"PROP-FLUTE": {"material": "bamboo"}},
              "line": {"taper": True}, "shading": {"method": "cel"},
              "rim_light": {"requires_visible_source": True, "no_default_halo": True}}


class Clock:
    t = 1000.0

    def __call__(self):
        return self.t


def write(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(data, bytes):
        path.write_bytes(data)
    else:
        path.write_text(data if isinstance(data, str) else json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    return path


def blob_run_py(ids):
    import base64
    b = base64.b64encode(json.dumps({sid: {"prompt": "x"} for sid in ids}).encode()).decode()
    return f'images = b64decode("{b}")\n'


def make_world(root: Path):
    S, F, fakes = root / "anime_studio", root / "flow_outputs" / "anime_kaliya", root / "fakes"
    for name in ("director/write_pack.py", "director/check_pack.py", "director/clip_tools.py", "director/visual_qa.py",
                 "director/run_kaggle.py", "director/t0_pack/run_t0_parallel.py", "flow/scripts/download_queue.py",
                 "flow/scripts/neighbour_sheet.py", "flow/scripts/review_shot.py", "flow/scripts/tidy_final.py"):
        write(S / name, FAKE_TOOL)
    write(S / "flow/scripts/bridge_flow_to_h3.py", FAKE_BRIDGE)
    write(fakes / "colab_fake.py", FAKE_COLAB)
    write(S / "flow/A_KM_flow_jobs_phase1a.json", [{"shot_id": "KRISHNA_TURNAROUND", "flow_title": "KRISHNA_TURNAROUND__v01",
                                                    "chips": ["CHAR-KRISHNA"], "prompt": "Portrait 9:16 test prompt", "prompt_sha256": "abc123"}])
    write(S / "stories/kaliya_mardan/SOURCE.md", "Kaliya story text.\n")
    pack = S / PACK
    write(pack / "shots.json", SHOTS)
    write(pack / "PACK.md", "# Pack\n\n## Scene List\n- scene one\n\n## Gate 2\nart bible\n")
    write(pack / "bible.json", {"characters": [{"id": "CHAR-KRISHNA", "name": "Krishna"}, {"id": "CHAR-KALIYA", "name": "Kaliya"}],
                                "environments": [{"id": "ENV-KALIYA-DAH", "name": "Dah"}]})
    write(pack / "stage_1_raw.json", {"ok": True})
    write(S / GOOD_PACK / "shots.json", GOOD_SHOTS)     # group 15: the real converters run on this pack in the temp studio
    write(S / GOOD_PACK / "bible.json", GOOD_BIBLE)
    for name in ("pack_to_spec.py", "build_jobs.py"):
        write(S / "flow/scripts" / name, (HERE.parent / "flow/scripts" / name).read_text(encoding="utf-8"))
    write(S / "flow/generated/argv_only/argv_only_image_spec.json", "{}")   # placeholders so the argv preview can see them
    write(S / "flow/generated/argv_only/argv_only_flow_series.json", "{}")
    write(S / "director/t0_pack/t0_shots.json", [])
    write(S / "director/t0_pack/results/SHOT-T0-C-S42/clip.mp4", b"x" * 1000)
    write(S / "director/t0_pack/direction.json", {"clip": "x"})
    write(S / "ui/static/index.html", "<!DOCTYPE html><html><body>studio</body></html>")
    for name, n in (("t0", 15), ("slow", 15), ("big", 40)):
        d = S / "director/colab_batches" / name
        write(d / "run.py", blob_run_py(["SHOT-T0-A-S42"]))
        write(d / "render_manifest.json", {"batch": name, "shots": [{"id": f"SHOT-{i:02d}"} for i in range(n)], "embed_mb_total": 1.0})
    write(root / "secrets/nvidia/nvidia_api_key.txt", "nvapi-SECRETVALUE0000000000000000")
    write(root / "secrets/nvidia/nvidia_api_key_2.txt", "nvapi-SECRETVALUE0000000000000001")
    a1 = F / "adhyay_01"
    for name in ("KRISHNA_TURNAROUND__v01__candA.png", "KRISHNA_TURNAROUND__v01__candB.png", "LEAP-03A__candidate_v01__clean.png"):
        write(a1 / "shots" / name, PNG)
    write(a1 / "final/KRISHNA_TURNAROUND__v01__final.png", PNG)
    write(a1 / "keyframes_h3/LEAP-01A_864x1536.png", PNG)
    return S, F, fakes


@pytest.fixture
def world(tmp_path):
    root = Path(os.path.realpath(tmp_path))
    S, F, fakes = make_world(root)
    clk = Clock()
    cfg = server.Config(studio=S, flow=F, downloads=root / "Downloads", python=sys.executable,
                        colab=[sys.executable, str(fakes / "colab_fake.py")], spend=False, clock=clk)
    return cfg, clk, fakes


def set_colab(fakes: Path, **state):
    base = {"sessions": [], "balance": 120.5, "stuck": False}
    base.update(state)
    (fakes / "colab_state.json").write_text(json.dumps(base), encoding="utf-8")


def wait_for(pred, timeout=15.0):
    end = time.time() + timeout
    while time.time() < end:
        if pred():
            return True
        time.sleep(0.05)
    raise AssertionError("timed out waiting")


def stop_all(api):
    for j in list(api.jobs.values()):
        if j.proc is not None and j.proc.poll() is None:
            j.proc.kill()
            j.proc.wait(5)


@pytest.fixture
def api(world):
    cfg, clk, fakes = world
    set_colab(fakes)
    a = server.Api(cfg)
    yield a
    stop_all(a)


@pytest.fixture
def http_srv(world):
    cfg, clk, fakes = world
    set_colab(fakes)
    srv = server.make_server(cfg, 0)
    port = srv.server_address[1]
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield srv, port
    stop_all(srv.api)
    srv.shutdown()
    srv.server_close()


def call(port, method, path, body=None, host=None, ui=True, origin=None):
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=30)
    headers = {"Host": host or f"127.0.0.1:{port}"}
    if origin:
        headers["Origin"] = origin
    data = None
    if method == "POST":
        headers["Content-Type"] = "application/json"
        if ui:
            headers["X-UI"] = "1"
        data = json.dumps(body if body is not None else {}).encode("utf-8")
    conn.request(method, path, body=data, headers=headers)
    r = conn.getresponse()
    raw = r.read()
    ctype = r.getheader("Content-Type", "")
    conn.close()
    return r.status, raw, ctype


def jget(port, path):
    status, raw, _ = call(port, "GET", path)
    return status, json.loads(raw)


# ----------------------------------------------------------------- group 1: argv builders (one per command id)
def cases(cfg):
    S, F, P = cfg.studio, cfg.flow, cfg.python
    A1 = F / "adhyay_01"
    dq = [P, str(S / "flow/scripts/download_queue.py")]
    jobs = str(S / "flow/A_KM_flow_jobs_phase1a.json")
    cands = [str(A1 / "shots/KRISHNA_TURNAROUND__v01__candA.png"), str(A1 / "shots/KRISHNA_TURNAROUND__v01__candB.png")]
    colab = [str(x) for x in cfg.colab]
    batch = S / "director/colab_batches/t0"
    run_dry = [P, str(S / "director/t0_pack/run_t0_parallel.py"), "--batch", str(batch), "--results", str(batch / "results"),
               "--gpu", "G4", "--name", "t0-kaliya"]
    return {
        "write_pack": ({"slug": "kaliya_mardan", "pack": "pack_new", "model": WRITER},
                       [P, str(S / "director/write_pack.py"), str(S / "stories/kaliya_mardan/SOURCE.md"), str(S / "stories/kaliya_mardan/pack_new"),
                        "--staged", "--via", "nvidia", "--model", WRITER]),
        "check_pack": ({"pack": PACK}, [P, str(S / "director/check_pack.py"), str(S / PACK)]),
        "bridge_dry": ({"size": "768x1344"}, [P, str(S / "flow/scripts/bridge_flow_to_h3.py"), "--final-dir", str(A1 / "final"),
                                             "--out-dir", str(A1 / "keyframes_h3"), "--size", "768x1344", "--json", "--dry-run"]),
        "bridge_write": ({"size": "864x1536"}, [P, str(S / "flow/scripts/bridge_flow_to_h3.py"), "--final-dir", str(A1 / "final"),
                                               "--out-dir", str(A1 / "keyframes_h3"), "--size", "864x1536", "--json"]),
        "neighbour_sheet": ({"jobs": "flow/A_KM_flow_jobs_phase1a.json", "shot": "KRISHNA_TURNAROUND", "candidates": cands},
                            [P, str(S / "flow/scripts/neighbour_sheet.py"), "--jobs", jobs, "--shot", "KRISHNA_TURNAROUND", "--candidate", *cands,
                             "--out", str(A1 / "shots/KRISHNA_TURNAROUND__neighbours.jpg")]),
        "review_shot": ({"jobs": "flow/A_KM_flow_jobs_phase1a.json", "shot": "KRISHNA_TURNAROUND", "candidates": cands},
                        [P, str(S / "flow/scripts/review_shot.py"), "--jobs", jobs, "--shot", "KRISHNA_TURNAROUND", "--candidate", *cands]),
        "queue_add": ({"shot": "KRISHNA_TURNAROUND", "version": "v01", "edit": EDIT, "jobs": "flow/A_KM_flow_jobs_phase1a.json", "note": "ok"},
                      [*dq, "add", "--root", str(F), "--adhyay", "1", "--shot", "KRISHNA_TURNAROUND", "--version", "v01", "--edit-id", EDIT,
                       "--jobs", jobs, "--model", "Nano Banana 2.1 x2", "--decided-by", "owner", "--note", "ok"]),
        "queue_status": ({"adhyay": 1}, [*dq, "status", "--root", str(F), "--adhyay", "1", "--json"]),
        "queue_collect": ({}, [*dq, "collect", "--root", str(F), "--adhyay", "1", "--downloads", str(cfg.downloads)]),
        "queue_accept": ({"shot": "KRISHNA_TURNAROUND", "version": "v01", "note": "looked at full size"},
                         [*dq, "accept", "--root", str(F), "--adhyay", "1", "--shot", "KRISHNA_TURNAROUND", "--version", "v01", "--by", "owner",
                          "--note", "looked at full size"]),
        "tidy_plan": ({}, [P, str(S / "flow/scripts/tidy_final.py"), "--root", str(F), "--adhyay", "1"]),
        "tidy_apply": ({}, [P, str(S / "flow/scripts/tidy_final.py"), "--root", str(F), "--adhyay", "1", "--apply"]),
        "clip_qa": ({"clip": "director/t0_pack/results/SHOT-T0-C-S42/clip.mp4", "out_dir": "director/t0_pack/qa"},
                    [P, str(S / "director/clip_tools.py"), "qa", str(S / "director/t0_pack/results/SHOT-T0-C-S42/clip.mp4"),
                     str(S / "director/t0_pack/qa")]),
        "visual_qa": ({"clip": "director/t0_pack/results/SHOT-T0-C-S42/clip.mp4", "direction": "director/t0_pack/direction.json",
                       "out_dir": "director/t0_pack/qa", "model": VISION},
                      [P, str(S / "director/visual_qa.py"), str(S / "director/t0_pack/results/SHOT-T0-C-S42/clip.mp4"),
                       str(S / "director/t0_pack/direction.json"), str(S / "director/t0_pack/qa"), "--via", "nvidia", "--model", VISION]),
        "run_kaggle_prepare": ({"shots": PACK + "/shots.json", "scope": "shots", "ids": ["SHOT-01"], "batch": "newb"},
                               [P, str(S / "director/run_kaggle.py"), str(S / PACK / "shots.json"), str(F / "adhyay_01/keyframes_h3"), "newb",
                                "--ids", "SHOT-01", "--style", "kaliya_mardan", "--target", "colab", "--profile", "5"]),
        "colab_sessions": ({}, [*colab, "sessions"]),
        "colab_usage": ({}, [*colab, "usage"]),
        "colab_stop": ({"session": "t0-kaliya"}, [*colab, "stop", "-s", "t0-kaliya"]),
        "colab_run_dry": ({"batch": "t0"}, run_dry),
        "colab_run": ({"batch": "t0"}, [*run_dry, "--go"]),
        "h3_prepare": ({"story": PACK + "/shots.json", "scope": "reel", "reel": 1},
                       [P, "-m", "h3.render_controller", "--story-file", str(S / PACK / "shots.json"), "--scope", "reel", "1",
                        "--mode", "prepare-only"]),
        "build_spec": ({"pack": GOOD_PACK, "adhyay": 1},
                       [P, str(S / "flow/scripts/pack_to_spec.py"), "--pack", str(S / GOOD_PACK), "--adhyay", "1",
                        "--out-dir", str(S / "flow/generated/kaliya_mardan")]),
        "build_jobs_cmd": ({"spec": "flow/generated/argv_only/argv_only_image_spec.json",
                            "series": "flow/generated/argv_only/argv_only_flow_series.json", "adhyay": 1, "out": "argv_only_flow_jobs_adhyay01.json"},
                           [P, str(S / "flow/scripts/build_jobs.py"), "--adhyay", "1",
                            "--spec", str(S / "flow/generated/argv_only/argv_only_image_spec.json"),
                            "--series", str(S / "flow/generated/argv_only/argv_only_flow_series.json"),
                            "--out", str(S / "flow/generated/argv_only/argv_only_flow_jobs_adhyay01.json")]),
    }


@pytest.mark.parametrize("cmd", sorted(cases(server.Config(studio=Path("x"), flow=Path("y"))).keys()))
def test_1_argv_builders_one_per_command_id(world, api, cmd):
    cfg, clk, fakes = world
    args, expected = cases(cfg)[cmd]
    if cmd == "h3_prepare":
        write(cfg.studio / "h3/render_controller.py", "# built\n")
    got = api.preview({"command": cmd, "args": args})
    assert got["argv"] == [str(x) for x in expected]


def test_1_every_command_id_has_a_case(world):
    cfg, _, _ = world
    assert set(cases(cfg)) == set(server.COMMANDS)


# ----------------------------------------------------------------- group 2: refusals
def refuse(api, command, args, code=400):
    with pytest.raises(ApiError) as e:
        api.preview({"command": command, "args": args})
    assert e.value.code == code, e.value.msg
    return e.value.msg


def test_2_unknown_command_refused(api):
    refuse(api, "shell", {})
    refuse(api, "os.system", {})


def test_2_shell_characters_in_slug_refused(api):
    refuse(api, "write_pack", {"slug": "kaliya;rm", "pack": "p", "model": WRITER})


def test_2_dotdot_in_path_refused(api):
    refuse(api, "visual_qa", {"clip": "director/../director/t0_pack/results/SHOT-T0-C-S42/clip.mp4", "direction": "director/t0_pack/direction.json",
                              "out_dir": "x", "model": VISION})


def test_2_granthstudio_path_refused(world, api):
    cfg, _, _ = world
    write(cfg.studio / "director/granthstudio/clip.mp4", b"x")
    refuse(api, "clip_qa", {"clip": "director/granthstudio/clip.mp4", "out_dir": "q"})


def test_2_secrets_and_env_files_refused(world, api):
    cfg, _, _ = world
    write(cfg.studio / "director/secrets/k.json", "{}")
    write(cfg.studio / "stories/kaliya_mardan/.env", "X=1")
    refuse(api, "run_kaggle_prepare", {"shots": "director/secrets/k.json", "scope": "all", "batch": "zz"})
    refuse(api, "run_kaggle_prepare", {"shots": "stories/kaliya_mardan/.env", "scope": "all", "batch": "zz"})


def test_2_path_outside_the_roots_refused(api):
    assert "outside" in refuse(api, "clip_qa", {"clip": "C:/Windows/win.ini", "out_dir": "q"})


def test_2_symlink_out_of_root_refused(world, api, tmp_path):
    cfg, _, _ = world
    outside = Path(os.path.realpath(tmp_path)) / "outside_dir"
    outside.mkdir()
    write(outside / "clip.mp4", b"x")
    link = cfg.studio / "director" / "link_out"
    try:
        os.symlink(outside, link, target_is_directory=True)
    except (OSError, NotImplementedError):
        # Windows without developer mode refuses symlinks; a directory junction needs no privilege and is the same escape
        r = subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(outside)], capture_output=True, text=True)
        if r.returncode != 0 or not link.exists():
            pytest.skip("this OS refuses both symlinks and junctions here")
    assert "outside" in refuse(api, "clip_qa", {"clip": "director/link_out/clip.mp4", "out_dir": "q"})


def test_2_logtostderr_smuggled_in_a_note_refused(api):
    refuse(api, "queue_accept", {"shot": "KRISHNA_TURNAROUND", "version": "v01", "note": "--logtostderr"})
    refuse(api, "queue_accept", {"shot": "KRISHNA_TURNAROUND", "version": "v01", "note": "ok --logtostderr"})
    refuse(api, "queue_accept", {"shot": "KRISHNA_TURNAROUND", "version": "v01", "note": "line\nbreak"})


def test_2_bad_shot_id_version_and_edit_id(api):
    refuse(api, "queue_accept", {"shot": "shot-01", "version": "v01"})
    refuse(api, "queue_accept", {"shot": "KRISHNA_TURNAROUND", "version": "v1"})
    refuse(api, "queue_add", {"shot": "KRISHNA_TURNAROUND", "version": "v01", "edit": "a" * 35, "jobs": "flow/A_KM_flow_jobs_phase1a.json"})


def test_2_size_not_in_enum_refused(api):
    refuse(api, "bridge_dry", {"size": "1080x1920"})


def test_2_claude_as_via_refused(api):
    refuse(api, "write_pack", {"slug": "kaliya_mardan", "pack": "p", "model": WRITER, "via": "claude"})
    refuse(api, "visual_qa", {"clip": "director/t0_pack/results/SHOT-T0-C-S42/clip.mp4", "direction": "director/t0_pack/direction.json",
                              "out_dir": "q", "model": "claude-opus"})


def test_2_unknown_model_and_missing_required(api):
    refuse(api, "write_pack", {"slug": "kaliya_mardan", "pack": "p", "model": "openrouter/free"})
    refuse(api, "colab_stop", {})


# ----------------------------------------------------------------- group 3: guards (HTTP)
def test_3_wrong_host_gives_403(http_srv):
    srv, port = http_srv
    status, raw, _ = call(port, "GET", "/api/status", host="evil.example:8765")
    assert status == 403
    status, _, _ = call(port, "GET", "/api/status", host="localhost:%d" % port)
    assert status == 200


def test_3_post_without_x_ui_gives_403(http_srv):
    srv, port = http_srv
    status, raw, _ = call(port, "POST", "/api/preview", {"command": "queue_status", "args": {"adhyay": 1}}, ui=False)
    assert status == 403 and b"X-UI" in raw


def test_3_foreign_origin_gives_403(http_srv):
    srv, port = http_srv
    status, _, _ = call(port, "GET", "/api/status", origin="http://evil.example")
    assert status == 403


def test_3_server_binds_only_loopback(http_srv):
    srv, port = http_srv
    assert srv.server_address[0] == "127.0.0.1"


# ----------------------------------------------------------------- group 4: preview token
def test_4_token_expires_after_60_seconds(world, api):
    cfg, clk, _ = world
    tok = api.preview({"command": "queue_status", "args": {"adhyay": 1}})["token"]
    clk.t += 61
    with pytest.raises(ApiError) as e:
        api.run({"token": tok})
    assert e.value.code == 403 and "expired" in e.value.msg


def test_4_token_is_single_use(world, api):
    tok = api.preview({"command": "queue_status", "args": {"adhyay": 1}})["token"]
    jid = api.run({"token": tok})["job_id"]
    wait_for(lambda: api.jobs[jid].state != "running")
    with pytest.raises(ApiError) as e:
        api.run({"token": tok})
    assert e.value.code == 403 and "already used" in e.value.msg


def test_4_changed_args_are_refused(api):
    tok = api.preview({"command": "queue_status", "args": {"adhyay": 1}})["token"]
    with pytest.raises(ApiError) as e:
        api.run({"token": tok, "command": "queue_status", "args": {"adhyay": 2}})
    assert e.value.code == 403 and "changed" in e.value.msg
    assert api.run({"token": tok, "command": "queue_status", "args": {"adhyay": 1}})["job_id"]


def test_4_unknown_token_refused(api):
    with pytest.raises(ApiError) as e:
        api.run({"token": "nope"})
    assert e.value.code == 403


# ----------------------------------------------------------------- group 5: spend gate
def test_5_spend_off_gives_403_even_with_a_valid_token(world, api):
    cfg, _, _ = world
    p = api.preview({"command": "colab_run", "args": {"batch": "t0"}})
    assert p["needs_confirm"] is True and p["estimate"] == 7.5 and p["confirm_text"] == "EXECUTE 7.5"
    with pytest.raises(ApiError) as e:
        api.run({"token": p["token"], "confirm": p["confirm_text"]})
    assert e.value.code == 403 and "spend is OFF" in e.value.msg


def test_5_wrong_confirm_gives_400(world):
    cfg, clk, fakes = world
    cfg.spend = True
    api = server.Api(cfg)
    p = api.preview({"command": "colab_run", "args": {"batch": "t0"}})
    with pytest.raises(ApiError) as e:
        api.run({"token": p["token"], "confirm": "EXECUTE 9.9"})
    assert e.value.code == 400
    assert api.run({"token": p["token"], "confirm": "EXECUTE 7.5"})["job_id"]
    stop_all(api)


def test_5_right_confirm_starts_the_fake_colab_job(world):
    cfg, clk, fakes = world
    cfg.spend = True
    api = server.Api(cfg)
    p = api.preview({"command": "colab_run", "args": {"batch": "t0", "session": "t0-test"}})
    assert p["balance"] == 120.5 and p["argv"][-1] == "--go"
    jid = api.run({"token": p["token"], "confirm": p["confirm_text"]})["job_id"]
    wait_for(lambda: api.jobs[jid].state != "running")
    log = (cfg.runs / "jobs" / f"{jid}.log").read_text(encoding="utf-8")
    assert "--go" in log and api.jobs[jid].spend is True and api.jobs[jid].state == "done"


def test_5_unknown_balance_refuses_spend(world):
    cfg, clk, fakes = world
    cfg.spend = True
    set_colab(fakes, balance=None)
    with pytest.raises(ApiError) as e:
        server.Api(cfg).preview({"command": "colab_run", "args": {"batch": "t0"}})
    assert e.value.code == 403 and "balance unknown" in e.value.msg


def test_5_low_balance_and_cap_refuse_spend(world):
    cfg, clk, fakes = world
    cfg.spend = True
    set_colab(fakes, balance=5.0)
    with pytest.raises(ApiError) as e:
        server.Api(cfg).preview({"command": "colab_run", "args": {"batch": "t0"}})
    assert e.value.code == 403 and "1.5 x" in e.value.msg
    set_colab(fakes, balance=500.0)
    with pytest.raises(ApiError) as e:
        server.Api(cfg).preview({"command": "colab_run", "args": {"batch": "big"}})   # 40 clips = 16.8 units, above the cap of 15
    assert e.value.code == 403 and "cap" in e.value.msg


def test_5_estimate_rule_matches_the_plan(world):
    assert server.estimate_units("G4", 15) == 7.5
    assert server.estimate_units("A100", 15) == round(6.73 * 45 / 60, 1)


# ----------------------------------------------------------------- group 6: job runner
def test_6_log_tail_and_state_change(api):
    tok = api.preview({"command": "queue_status", "args": {"adhyay": 1}})["token"]
    jid = api.run({"token": tok})["job_id"]
    assert api.jobs_list()[0]["id"] == jid
    wait_for(lambda: api.jobs[jid].state != "running")
    assert api.jobs[jid].state == "done" and api.jobs[jid].rc == 0
    log = api.job_log(jid, {"tail": "5"}).data.decode("utf-8")
    assert "ARGV" in log and '"status"' in log
    assert len(api.job_log(jid, {"tail": "1"}).data.decode("utf-8").splitlines()) == 1


def test_6_second_job_gets_409_and_stop_kills_the_process(api):
    p1 = api.preview({"command": "colab_run_dry", "args": {"batch": "slow"}})
    jid = api.run({"token": p1["token"]})["job_id"]
    p2 = api.preview({"command": "queue_status", "args": {"adhyay": 1}})
    with pytest.raises(ApiError) as e:
        api.run({"token": p2["token"]})
    assert e.value.code == 409
    proc = api.jobs[jid].proc
    res = api.job_stop(jid)
    assert res["state"] == "stopped" and res["warning"] == ""
    assert proc.wait(10) is not None and proc.poll() is not None
    assert api.jobs[jid].state == "stopped"
    wait_for(lambda: api.jobs[jid].rc is not None)
    assert api.jobs[jid].state == "stopped"


def test_6_stop_on_a_spend_job_returns_the_session_warning(world):
    cfg, clk, fakes = world
    cfg.spend = True
    api = server.Api(cfg)
    p = api.preview({"command": "colab_run", "args": {"batch": "slow", "session": "t0-kaliya"}})
    jid = api.run({"token": p["token"], "confirm": p["confirm_text"]})["job_id"]
    res = api.job_stop(jid)
    assert res["state"] == "stopped" and "colab stop -s t0-kaliya" in res["warning"]
    stop_all(api)


def test_6_stop_after_the_job_ended_says_so(api):
    tok = api.preview({"command": "queue_status", "args": {"adhyay": 1}})["token"]
    jid = api.run({"token": tok})["job_id"]
    wait_for(lambda: api.jobs[jid].state != "running")
    assert api.job_stop(jid)["warning"] == "the job had already finished"


# ----------------------------------------------------------------- group 7: Colab failure path
def test_7_stop_that_leaves_the_session_listed_shows_stop_failed(world, api):
    cfg, clk, fakes = world
    set_colab(fakes, sessions=["t0-kaliya"], stuck=True)
    p = api.preview({"command": "colab_stop", "args": {"session": "t0-kaliya"}})
    jid = api.run({"token": p["token"]})["job_id"]
    wait_for(lambda: api.jobs[jid].state != "running")
    job = api.jobs[jid]
    assert job.state == "stop_failed" and "colab stop -s t0-kaliya" in job.warning
    assert "STOP FAILED" in api.job_log(jid, {}).data.decode("utf-8")


def test_7_a_clean_stop_is_verified(world, api):
    cfg, clk, fakes = world
    set_colab(fakes, sessions=["t0-kaliya"])
    p = api.preview({"command": "colab_stop", "args": {"session": "t0-kaliya"}})
    jid = api.run({"token": p["token"]})["job_id"]
    wait_for(lambda: api.jobs[jid].state != "running")
    assert api.jobs[jid].state == "done"
    assert "no longer listed" in api.job_log(jid, {}).data.decode("utf-8")


# ----------------------------------------------------------------- group 8: redaction
def test_8_redact_removes_every_key_shape():
    samples = ["ya29.A0ARrdaM-abcdef", "Bearer abc.def", "nvapi-XYZ123", "hf_ABCDEFGHIJKLMNOPQRSTUV", "sk-ABCDEFGHIJKLMNOPQRS",
               "AIza" + "B" * 32, "token=supersecret"]
    text = " | ".join(samples)
    out = server.redact(text)
    for s in ("ya29.A0", "abc.def", "nvapi-XYZ", "hf_ABCDEF", "sk-ABCDEF", "AIzaBBBB", "supersecret"):
        assert s not in out
    assert server.has_secret(text) and not server.has_secret(out)


def test_8_log_tail_is_redacted(world, api):
    cfg, clk, fakes = world
    jid = "20260101-000000-aaaaaa"
    log = cfg.runs / "jobs" / f"{jid}.log"
    write(log, "ok line\nBearer abc123secret\nnvapi-LEAKEDKEYVALUE12345\ntoken=abc999\n")
    api.jobs[jid] = server.Job(jid, "queue_status", ["x"], False, None, "", log)
    api.jobs[jid].state, api.jobs[jid].rc = "done", 0
    out = api.job_log(jid, {"tail": "20"}).data.decode("utf-8")
    assert "ok line" in out and "abc123secret" not in out and "LEAKEDKEY" not in out and "abc999" not in out


def test_8_packet_with_a_key_like_text_is_not_written(world, api):
    cfg, clk, fakes = world
    jobs = cfg.studio / "flow/A_KM_flow_jobs_leak.json"
    write(jobs, [{"shot_id": "LEAK_SHOT", "flow_title": "LEAK_SHOT__v01", "chips": [], "prompt": "hf_ABCDEFGHIJKLMNOPQRSTUVWX",
                  "prompt_sha256": "x"}])
    with pytest.raises(ApiError) as e:
        api.packet({"jobs": "flow/A_KM_flow_jobs_leak.json", "shots": ["LEAK_SHOT"]})
    assert e.value.code == 400
    assert not (cfg.runs / "packets").exists() or not any((cfg.runs / "packets").iterdir())


def test_8_packet_is_written_when_clean(world, api):
    cfg, clk, fakes = world
    res = api.packet({"jobs": "flow/A_KM_flow_jobs_phase1a.json", "shots": ["KRISHNA_TURNAROUND"]})
    assert Path(res["path"]).is_file()
    assert "Haiku, effort LOW" in res["markdown"] and "Nano Banana 2.1 x2" in res["markdown"] and "abc123" in res["markdown"]


def test_8_audit_lines_are_redacted(world, api):
    cfg, clk, fakes = world
    api.preview({"command": "queue_accept", "args": {"shot": "KRISHNA_TURNAROUND", "version": "v01", "note": "Bearer abc123secretvalue"}})
    audit = (cfg.runs / "audit.jsonl").read_text(encoding="utf-8")
    assert "preview" in audit and "abc123secretvalue" not in audit and "[REDACTED]" in audit


# ----------------------------------------------------------------- group 9: readers
def test_9_synthetic_pack_counts(world):
    cfg, clk, fakes = world
    p = server.read_pack(cfg, PACK, check=False)
    assert len(p["shots"]) == 4
    assert [(e["n"], e["shots"], e["seconds"]) for e in p["episodes"]] == [(1, 2, 16.5), (2, 2, 16.0)]
    assert [c["id"] for c in p["characters"]] == ["CHAR-KRISHNA", "CHAR-KALIYA"]
    assert p["stages"]["1"] is True and p["stages"]["2"] is False
    assert "scene one" in p["gate1"] and "art bible" not in p["gate1"]
    assert p["episodes"][0]["check"] == "not checked"


def test_9_pack_check_uses_the_check_tool(world, api, monkeypatch):
    cfg, clk, fakes = world
    write(cfg.studio / "director/check_pack.py", 'import json\nprint(json.dumps({"shots": 4, "issues": ["SHOT-03: names a film"]}))\n')
    p = server.read_pack(cfg, PACK, check=True)
    flags = {e["n"]: e["check"] for e in p["episodes"]}
    assert flags == {1: "PASS", 2: "ISSUES (1)"}


def test_9_synthetic_adhyay_matches_download_queue_status(world):
    import importlib.util
    cfg, clk, fakes = world
    root = cfg.flow
    dq = server._dq_module()
    dq.add(root, 1, "KRISHNA_TURNAROUND", "v01", EDIT)
    dq.add(root, 1, "KRISHNA_ACTING_SHEET", "v01", "34ba531b-b5c7-43fa-82a5-7b7746b57099")
    dq.add(root, 1, "LEAP-03A", "v01", "34ba531b-b5c7-43fa-82a5-7b7746b57098")
    write(root / "adhyay_01/flow_log.jsonl", '{"image_id": "KRISHNA_ACTING_SHEET", "version": "v01"}\n{"image_id": "LEAP-03A", "version": "v01"}\n')
    write(root / "adhyay_01/accepted.jsonl", '{"shot_id": "LEAP-03A", "version": "v01", "accepted_by": "owner", "note": ""}\n')
    write(root / "adhyay_01/shots_progress.jsonl", "".join(json.dumps({"shot_id": f"S{i}", "status": "DONE"}) + "\n" for i in range(3)))
    write(root / "adhyay_01/shots/KRISHNA_TURNAROUND__v01__review.json", {"shot_id": "KRISHNA_TURNAROUND",
                                                                       "results": [{"candidate": "x/KRISHNA_TURNAROUND__v01__candA.png", "verdict": "PASS"}]})
    ui = server.read_images(cfg, 1)
    real = dq.status(root, 1)
    assert ui["queue"]["counts"]["pending"] == len(real["pending"]) == 1
    assert ui["queue"]["counts"]["filed"] == len(real["filed"]) == 2
    assert [i["shot_id"] for i in ui["queue"]["pending"]] == [i["shot_id"] for i in real["pending"]] == ["KRISHNA_TURNAROUND"]
    assert ui["progress"]["total"] == 3 and ui["progress"]["legacy"] == 3
    assert ui["accepted"][0]["accepted_by"] == "owner"
    assert any(s["id"] == "KRISHNA_TURNAROUND" and s["reviews"][0]["verdict"] == "PASS" for s in ui["shots"])
    assert len(ui["finals"]) == 1 and len(ui["keyframes"]) == 1


def test_9_images_endpoint_shape(http_srv):
    srv, port = http_srv
    status, body = jget(port, "/api/images?adhyay=1")
    assert status == 200
    for key in ("series", "sheets", "jobs", "shots", "progress", "queue", "filed", "accepted", "finals"):
        assert key in body
    assert body["progress"]["legacy"] == body["progress"]["total"] == 0


# ----------------------------------------------------------------- group 10: scope mapping
def test_10_scope_mapping(world):
    cfg, clk, fakes = world
    shots = cfg.studio / PACK / "shots.json"
    assert server.scope_ids(shots, "shots", ["SHOT-02"]) == ["SHOT-02"]
    assert server.scope_ids(shots, "reel", reel=2) == ["SHOT-03", "SHOT-04"]
    assert server.scope_ids(shots, "reel", reel=1) == ["SHOT-01", "SHOT-02"]
    assert server.scope_ids(shots, "all") is None
    with pytest.raises(ApiError):
        server.scope_ids(shots, "shots", ["SHOT-99"])
    with pytest.raises(ApiError):
        server.scope_ids(shots, "reel", reel=7)


def test_10_prepare_preview_carries_the_reel_ids(api):
    got = api.preview({"command": "run_kaggle_prepare", "args": {"shots": PACK + "/shots.json", "scope": "reel", "reel": 2, "batch": "reel2"}})
    i = got["argv"].index("--ids")
    assert got["argv"][i + 1] == "SHOT-03,SHOT-04"


def test_10_prepare_all_has_no_ids_and_existing_batch_is_409(api):
    got = api.preview({"command": "run_kaggle_prepare", "args": {"shots": PACK + "/shots.json", "scope": "all", "batch": "allb"}})
    assert "--ids" not in got["argv"]
    with pytest.raises(ApiError) as e:
        api.preview({"command": "run_kaggle_prepare", "args": {"shots": PACK + "/shots.json", "scope": "all", "batch": "t0"}})
    assert e.value.code == 409


# ----------------------------------------------------------------- group 11: Colab parsers
def test_11_empty_sessions_fixture():
    assert server.parse_sessions("no sessions\n") == []
    assert server.parse_sessions("") == []


def test_11_one_session_fixture():
    text = "NAME         GPU   STATUS\nt0-kaliya    G4    running 00:12\n"
    assert server.parse_sessions(text) == [{"name": "t0-kaliya", "gpu": "G4", "status": "running 00:12"}]


def test_11_usage_fixtures():
    assert server.parse_usage("Balance: 120.5 units\n") == 120.5
    assert server.parse_usage("Remaining units: 7") == 7.0
    assert server.parse_usage("usage: no figure here") is None


def test_11_colab_endpoint_reads_both(http_srv):
    srv, port = http_srv
    status, body = jget(port, "/api/colab")
    assert status == 200 and body["balance"] == 120.5 and body["sessions"] == []
    assert body["rate_units_per_hour"] == {"G4": 10.05, "A100": 6.73}


# ----------------------------------------------------------------- group 12: bridge output
BRIDGE_TEXT = ("OK       LEAP-03A 1536x2752 -> out box=(0.000, 10.667, 1536.000, 2741.333) removed=21.333px\n"
               "SKIP     LEAP-01A -> out (already 864x1536)\n"
               "DRY-RUN  LEAP-02A 1536x2752 -> out box=(0, 1, 2, 3) removed=4px\n"
               "REFUSED  LEAP-04A: source 2752x1536 aspect is 65.00% off 864x1536 (limit 3.0%)\n")


def test_12_bridge_text_lines_are_parsed():
    recs = server.parse_bridge_text(BRIDGE_TEXT)
    assert [r["status"] for r in recs] == ["OK", "SKIP", "DRY", "REFUSED"]
    assert [r["label"] for r in recs] == ["LEAP-03A", "LEAP-01A", "LEAP-02A", "LEAP-04A"]


def test_12_bridge_json_is_parsed_and_non_json_is_none():
    assert server.parse_bridge_json('[{"label": "A", "status": "OK"}]') == [{"label": "A", "status": "OK"}]
    assert server.parse_bridge_json(BRIDGE_TEXT) is None


def test_12_bridge_job_result_counts(world, api):
    tok = api.preview({"command": "bridge_write", "args": {"size": "864x1536"}})["token"]
    jid = api.run({"token": tok})["job_id"]
    wait_for(lambda: api.jobs[jid].state != "running")
    res = api.job_result(jid)
    assert res["counts"] == {"OK": 1, "REFUSED": 1} and res["records"][1]["reason"] == "aspect off"


def test_12_dry_run_argv_has_dry_run_flag(api):
    got = api.preview({"command": "bridge_dry", "args": {"size": "864x1536"}})
    assert "--dry-run" in got["argv"] and got["risk"] == "R"


# ----------------------------------------------------------------- group 13: static checks
def test_13_index_and_static_files_have_no_outside_links():
    static = HERE / "static"
    if not static.is_dir():
        pytest.skip("ui/static is written by the other agent; nothing to check yet")
    for name in ("index.html", "app.js", "style.css"):
        f = static / name
        if f.is_file():
            assert not re.search(r"https?://", f.read_text(encoding="utf-8")), name


def test_13_server_has_no_shell_and_only_stdlib_or_pillow():
    src = (HERE / "server.py").read_text(encoding="utf-8")
    assert "shell=True" not in src and "os.system" not in src
    tree = ast.parse(src)
    mods = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            mods |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.level == 0:
            mods.add(node.module.split(".")[0])
    # download_queue is the flow script's own queue reader, loaded by _dq_module() so UI and script never disagree
    assert mods <= set(sys.stdlib_module_names) | {"PIL", "download_queue", "pipeline"}, mods - set(sys.stdlib_module_names)


# ----------------------------------------------------------------- group 14: optional read-only smoke on real data
REAL_PACK_REL = "stories/kaliya_mardan/pack_dots_full_v22"
REAL_PACK = Path("D:/aai work/anime_studio") / REAL_PACK_REL
REAL_ADHYAY = Path("D:/aai work/flow_outputs/anime_kaliya/adhyay_01")


def snapshot(d: Path):
    return sorted((str(p.relative_to(d)), p.stat().st_size, p.stat().st_mtime_ns) for p in d.rglob("*") if p.is_file())


@pytest.mark.skipif(not (REAL_PACK / "shots.json").is_file(), reason="real pack folder not present")
def test_14_real_pack_reads_45_shots_and_episodes(tmp_path):
    cfg = server.Config()
    before = snapshot(REAL_PACK)
    p = server.read_pack(cfg, REAL_PACK_REL, check=False)
    assert len(p["shots"]) == 45
    assert [e["shots"] for e in p["episodes"]] == [7, 9, 9, 8, 12]
    assert snapshot(REAL_PACK) == before


@pytest.mark.skipif(not REAL_ADHYAY.is_dir(), reason="real adhyay_01 folder not present")
def test_14_real_adhyay_reads_18_finals_and_legacy_progress():
    cfg = server.Config()
    before = snapshot(REAL_ADHYAY)
    img = server.read_images(cfg, 1)
    assert len(img["finals"]) == 18
    assert img["progress"]["total"] == 48 and img["progress"]["legacy"] == 48
    assert len(img["shots"]) >= 18
    assert snapshot(REAL_ADHYAY) == before


def test_14_real_studio_status_has_no_secret_values():
    st = server.Api(server.Config()).status()
    assert isinstance(st["nvidia_key_files"], int) and st["spend_allowed"] is False
    assert "nvapi-" not in json.dumps(st)


# ----------------------------------------------------------------- HTTP surface (groups 3, 4, 5 and the story and file endpoints)
def test_http_story_save_refuses_overwrite_then_allows_with_flag(http_srv):
    srv, port = http_srv
    status, body, _ = call(port, "POST", "/api/story/kaliya_mardan", {"text": "new text"})
    assert status == 409
    status, body, _ = call(port, "POST", "/api/story/kaliya_mardan", {"text": "new text", "overwrite": True})
    assert status == 200 and json.loads(body)["saved"] == "stories/kaliya_mardan/SOURCE.md"
    assert (srv.api.cfg.studio / "stories/kaliya_mardan/SOURCE.md").read_text(encoding="utf-8") == "new text"
    status, body, _ = call(port, "POST", "/api/story/newstory", {"text": "fresh"})
    assert status == 200 and (srv.api.cfg.studio / "stories/newstory/SOURCE.md").is_file()


def test_http_story_save_over_200kb_refused(http_srv):
    srv, port = http_srv
    status, _, _ = call(port, "POST", "/api/story/kaliya_mardan", {"text": "a" * (201 * 1024), "overwrite": True})
    assert status == 413


def test_http_pack_status_and_h3_missing(http_srv):
    srv, port = http_srv
    status, body = jget(port, "/api/status")
    assert status == 200 and body["h3_built"] is False and body["spend_allowed"] is False
    status, body = jget(port, "/api/h3")
    assert body["built"] is False and body["message"] == "h3 engine not built yet"
    status, body = jget(port, f"/api/pack?pack={PACK}")
    assert status == 200 and len(body["shots"]) == 4 and body["check"] is None


def test_http_h3_preview_refused_while_missing_and_allowed_when_built(world, api):
    cfg, clk, fakes = world
    with pytest.raises(ApiError) as e:
        api.preview({"command": "h3_prepare", "args": {"story": PACK + "/shots.json", "scope": "reel", "reel": 1}})
    assert e.value.code == 409 and e.value.msg == "h3 engine not built yet"
    write(cfg.studio / "h3/render_controller.py", "# built\n")
    got = api.preview({"command": "h3_prepare", "args": {"story": PACK + "/shots.json", "scope": "reel", "reel": 1}})
    assert got["argv"][:3] == [cfg.python, "-m", "h3.render_controller"]


def test_http_file_endpoint_serves_allowed_and_refuses_the_rest(http_srv, world):
    srv, port = http_srv
    cfg, _, _ = world
    png = cfg.flow / "adhyay_01/final/KRISHNA_TURNAROUND__v01__final.png"
    status, raw, ctype = call(port, "GET", f"/api/file?path={png}")
    assert status == 200 and ctype == "image/png" and raw == PNG
    status, _, _ = call(port, "GET", f"/api/file?path={cfg.studio / 'stories/kaliya_mardan/.env'}")
    assert status == 400
    status, _, _ = call(port, "GET", f"/api/file?path={cfg.studio.parent / 'secrets/nvidia/nvidia_api_key.txt'}")
    assert status == 400
    status, _, _ = call(port, "GET", "/api/file?path=C:/Windows/win.ini")
    assert status == 400


def test_http_root_serves_the_static_page(http_srv):
    srv, port = http_srv
    status, raw, ctype = call(port, "GET", "/")
    assert status == 200 and "text/html" in ctype and b"studio" in raw


def test_http_review_endpoint_reads_the_verdict(world, api):
    cfg, clk, fakes = world
    write(cfg.flow / "adhyay_01/shots/KRISHNA_TURNAROUND__v01__candA__review.json", {
        "shot_id": "KRISHNA_TURNAROUND", "results": [{"candidate": str(cfg.flow / "adhyay_01/shots/KRISHNA_TURNAROUND__v01__candA.png"),
                                                      "verdict": "BLOCK", "fix": "edit", "answers": {"Q1": {"result": "PASS"}}}]})
    got = api.review("KRISHNA_TURNAROUND", "KRISHNA_TURNAROUND__v01__candA.png", "1")
    assert got["verdict"] == "BLOCK" and got["fix"] == "edit" and got["answers"]["Q1"]["result"] == "PASS"


def test_http_video_and_export_shapes(http_srv):
    srv, port = http_srv
    status, body = jget(port, "/api/video")
    assert status == 200 and body["batches"] and {"name", "run_py_bytes", "settings", "embed_mb"} <= set(body["batches"][0])
    assert body["clips"] and body["clips"][0]["shot"] == "SHOT-T0-C-S42"
    status, body = jget(port, f"/api/export?reel=1&pack={PACK}")
    assert status == 200 and body["assembly"] == "not built" and body["shot_ids"] == ["SHOT-01", "SHOT-02"]


def test_http_preview_run_and_job_list(http_srv):
    srv, port = http_srv
    status, raw, _ = call(port, "POST", "/api/preview", {"command": "queue_status", "args": {"adhyay": 1}})
    assert status == 200
    tok = json.loads(raw)["token"]
    status, raw, _ = call(port, "POST", "/api/run", {"token": tok})
    assert status == 200
    jid = json.loads(raw)["job_id"]
    wait_for(lambda: srv.api.jobs[jid].state != "running")
    status, jobs = jget(port, "/api/jobs")
    assert status == 200 and jobs[0]["id"] == jid
    status, res = jget(port, f"/api/jobs/{jid}/result")
    assert status == 200 and "lines" in res


def test_http_unknown_path_is_404(http_srv):
    srv, port = http_srv
    status, _, _ = call(port, "GET", "/api/nothing")
    assert status == 404


def test_6_job_started_during_the_spend_gate_blocks_the_second_run(api, monkeypatch):
    """Race found by the Dots review: both runs pass the first 'no active job' check; the second start must be refused."""
    first = api.preview({"command": "colab_run_dry", "args": {"batch": "slow"}})
    second = api.preview({"command": "colab_run_dry", "args": {"batch": "slow"}})
    started = {}

    def gate_that_lets_the_other_run_start(est):
        started["jid"] = api.run({"token": first["token"]})["job_id"]
        return None

    monkeypatch.setattr(api, "_spend_gate", gate_that_lets_the_other_run_start)
    api.cfg.spend = True
    monkeypatch.setitem(api.tokens[second["token"]], "spend", True)
    monkeypatch.setitem(api.tokens[second["token"]], "est", 1.0)
    monkeypatch.setitem(api.tokens[second["token"]], "confirm", "")
    with pytest.raises(ApiError) as e:
        api.run({"token": second["token"], "confirm": ""})
    assert e.value.code == 409 and len([j for j in api.jobs.values() if j.state == "running"]) == 1
    api.job_stop(started["jid"])


# ----------------------------------------------------------------- group 15: image jobs (build_spec, build_jobs_cmd, generated listing)
GEN = "flow/generated/kaliya_mardan"
SPEC_REL = GEN + "/kaliya_mardan_image_spec.json"
SERIES_REL = GEN + "/kaliya_mardan_flow_series.json"
JOBS_OUT = "kaliya_mardan_flow_jobs_adhyay01.json"
JOBS_REL = GEN + "/" + JOBS_OUT
BUILD_SPEC = {"pack": GOOD_PACK, "adhyay": 1}
BUILD_JOBS = {"spec": SPEC_REL, "series": SERIES_REL, "adhyay": 1, "out": JOBS_OUT}


def run_to_end(api, command, args):
    """preview, run, then wait for the job to finish (the page does the same, one job at a time)."""
    tok = api.preview({"command": command, "args": args})["token"]
    jid = api.run({"token": tok})["job_id"]
    wait_for(lambda: api.jobs[jid].state != "running")
    return api.jobs[jid]


def lines_of(api, job):
    return api.job_result(job.id)["lines"]


def test_15_build_spec_refusals(api):
    refuse(api, "build_spec", {"pack": "stories/../stories/kaliya_mardan/pack_good", "adhyay": 1})
    refuse(api, "build_spec", {"pack": "stories/kaliya_mardan/no_such_pack", "adhyay": 1})
    refuse(api, "build_spec", {"pack": "C:/Windows", "adhyay": 1})
    refuse(api, "build_spec", {"pack": GOOD_PACK})
    for bad_adhyay in (0, 100, "x", "-1", True):
        refuse(api, "build_spec", {"pack": GOOD_PACK, "adhyay": bad_adhyay})
    refuse(api, "build_spec", {"pack": GOOD_PACK, "adhyay": 1, "overwrite": "yes"})
    refuse(api, "build_spec", {"pack": GOOD_PACK, "adhyay": 1, "out_dir": "x"})


def test_15_build_spec_refuses_a_secrets_folder(world, api):
    cfg, _, _ = world
    write(cfg.studio / "stories/kaliya_mardan/secrets/shots.json", "[]")
    refuse(api, "build_spec", {"pack": "stories/kaliya_mardan/secrets", "adhyay": 1})


def test_15_build_spec_argv_and_overwrite_flag(world, api):
    cfg, _, _ = world
    got = api.preview({"command": "build_spec", "args": BUILD_SPEC})
    assert got["risk"] == "W" and got["needs_confirm"] is False
    assert "--overwrite" not in got["argv"]
    assert api.preview({"command": "build_spec", "args": {**BUILD_SPEC, "overwrite": True}})["argv"][-1] == "--overwrite"


def test_15_build_jobs_refuses_anything_outside_the_generated_folder(world, api):
    cfg, _, _ = world
    write(cfg.studio / SPEC_REL, "{}")
    write(cfg.studio / SERIES_REL, "{}")
    write(cfg.studio / "flow/generated/other_pack/other_series.json", "{}")
    assert "flow/generated" in refuse(api, "build_jobs_cmd", {**BUILD_JOBS, "spec": "flow/A_KM_flow_jobs_phase1a.json"})
    assert "flow/generated" in refuse(api, "build_jobs_cmd", {**BUILD_JOBS, "series": "flow/A_KM_flow_jobs_phase1a.json"})
    assert "outside" in refuse(api, "build_jobs_cmd", {**BUILD_JOBS, "spec": "C:/Windows/win.ini"})
    refuse(api, "build_jobs_cmd", {**BUILD_JOBS, "spec": "stories/kaliya_mardan/SOURCE.md"})
    refuse(api, "build_jobs_cmd", {**BUILD_JOBS, "spec": GEN + "/../kaliya_mardan/kaliya_mardan_image_spec.json"})
    refuse(api, "build_jobs_cmd", {**BUILD_JOBS, "series": "flow/generated/other_pack/other_series.json"})
    refuse(api, "build_jobs_cmd", {**BUILD_JOBS, "out": "../" + JOBS_OUT})
    refuse(api, "build_jobs_cmd", {**BUILD_JOBS, "out": "evil.json"})
    refuse(api, "build_jobs_cmd", {**BUILD_JOBS, "adhyay": 0})
    refuse(api, "build_jobs_cmd", {"spec": SPEC_REL, "series": SERIES_REL, "adhyay": 1})


def test_15_build_spec_then_jobs_write_the_files_and_the_page_lists_them(world, api):
    cfg, _, _ = world
    spec_job = run_to_end(api, "build_spec", BUILD_SPEC)
    assert spec_job.state == "done" and spec_job.rc == 0, lines_of(api, spec_job)
    spec = json.loads((cfg.studio / SPEC_REL).read_text(encoding="utf-8"))
    assert [s["shot_id"] for s in spec["shots"]] == ["SHOT-G1A", "SHOT-G1B"]
    assert spec["slot_order"] == {"SCENE-G": ["SHOT-G1A", "SHOT-G1B"]}
    assert (cfg.studio / SERIES_REL).is_file()

    jobs_job = run_to_end(api, "build_jobs_cmd", BUILD_JOBS)
    assert jobs_job.state == "done" and jobs_job.rc == 0, lines_of(api, jobs_job)
    jobs = json.loads((cfg.studio / JOBS_REL).read_text(encoding="utf-8"))
    assert [j["shot_id"] for j in jobs] == ["SHOT-G1A", "SHOT-G1B"]
    assert jobs[0]["chips"] == ["CHAR-KRISHNA", "ENV_DAH__v01", "STYLE_CHIP_SHEET__v01"]
    assert "Exactly 1 person" in jobs[0]["prompt"]

    listed = api.images("1")["jobs"]
    mine = [j for j in listed if j["file"] == "generated/kaliya_mardan/" + JOBS_OUT]
    assert [j["shot_id"] for j in mine] == ["SHOT-G1A", "SHOT-G1B"]
    assert any(j["file"] == "A_KM_flow_jobs_phase1a.json" for j in listed)
    assert (cfg.studio / "flow" / mine[0]["file"]).is_file()
    pkt = api.packet({"jobs": "flow/" + mine[0]["file"], "shots": ["SHOT-G1A", "SHOT-G1B"]})
    assert "SHOT-G1A" in pkt["markdown"]


def test_15_a_pack_to_spec_refusal_is_in_the_job_result(world, api):
    cfg, _, _ = world
    bad = run_to_end(api, "build_spec", {"pack": PACK, "adhyay": 1})   # PACK has no set ids: the converter refuses it
    assert bad.state == "failed" and bad.rc == 2
    assert any(line.startswith("REFUSED: unsafe set id None") for line in lines_of(api, bad)), lines_of(api, bad)
    assert not (cfg.studio / SPEC_REL).exists()


def test_15_existing_files_are_kept_unless_overwrite_is_asked(world, api):
    cfg, _, _ = world
    assert run_to_end(api, "build_spec", BUILD_SPEC).state == "done"
    again = run_to_end(api, "build_spec", BUILD_SPEC)
    assert again.state == "failed" and any(line.startswith("REFUSED: refusing to overwrite") for line in lines_of(api, again))
    forced = run_to_end(api, "build_spec", {**BUILD_SPEC, "overwrite": True})
    assert forced.state == "done" and "--overwrite" in forced.argv
    assert run_to_end(api, "build_jobs_cmd", BUILD_JOBS).state == "done"
    twice = run_to_end(api, "build_jobs_cmd", BUILD_JOBS)
    assert twice.state == "failed" and any("Refusing to overwrite" in line for line in lines_of(api, twice))


def test_15_http_images_lists_only_the_job_files_in_generated(http_srv):
    srv, port = http_srv
    cfg = srv.api.cfg
    write(cfg.studio / JOBS_REL, [{"shot_id": "SHOT-G1A", "chips": [], "prompt": "x", "prompt_sha256": "abc"}])
    write(cfg.studio / GEN / "kaliya_mardan_image_spec.json", "[]")          # a spec, not a jobs file
    write(cfg.studio / GEN / "deep/x_flow_jobs.json", [{"shot_id": "DEEP"}])  # too deep to be listed
    status, body = jget(port, "/api/images?adhyay=1")
    assert status == 200
    assert {j["file"] for j in body["jobs"]} == {"A_KM_flow_jobs_phase1a.json", "generated/kaliya_mardan/" + JOBS_OUT}
    status, raw, _ = call(port, "POST", "/api/preview", {"command": "build_spec", "args": BUILD_SPEC})
    assert status == 200 and json.loads(raw)["risk"] == "W"
    status, _, _ = call(port, "POST", "/api/preview", {"command": "build_spec", "args": BUILD_SPEC}, ui=False)
    assert status == 403
