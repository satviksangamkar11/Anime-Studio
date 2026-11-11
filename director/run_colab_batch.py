"""Run any built Colab batch (director/colab_batches/<batch>/run.py) with the official `colab` CLI. DRY RUN unless --go (a real run spends units).
  python run_colab_batch.py BATCH --results OUT_DIR                  -> prints the commands only
  python run_colab_batch.py BATCH --results OUT_DIR --go --gpu G4    -> runs them (spends units)
Sequence (render pre-flight review 2026-11-09, blot RULE 28): usage, new, `exec -f run.py` as a background process, PROOF within 180 s that the
script started on the VM (`ls /content` shows out/), else kill the exec and stop the session at once; wait for the run; list + download every
file; stop. The session is stopped on EVERY exit path except one: once the script has started and the clips are still on the VM, a failed
download keeps the session (stopping it would delete the clips) and prints the stop command. Never --logtostderr."""
import argparse
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "t0_pack"))
import run_t0_colab as t0  # noqa: E402
import runner_safety as rs  # noqa: E402

ENV = {**os.environ, "MSYS_NO_PATHCONV": "1"}     # Git Bash would turn /content into C:/Program Files/Git/content
EXEC_TIMEOUT = 6 * 3600    # exec --timeout is an IDLE limit (seconds)
PROOF_SECONDS = 180
HF_TOKEN_FILE = "D:/aai work/secrets/huggingface/hf_token.txt"    # one line, never printed or logged; a missing file means no token (429 retries only)
CLI_TIMEOUT = 600               # seconds for any single colab command except the long exec of run.py
CLIP_POLL_SECONDS = 60         # how often finished clips are copied to this PC while the render runs
MIN_CLIP_BYTES = 50_000         # a smaller mp4 is not a finished clip
MAX_PART_MB = 3.0               # owner decision D6 (2026-11-11): no script size cap; every upload part <= 3 MiB
WAN2GP_GIT = "https://github.com/deepbeepmeep/Wan2GP.git"
FRAME_SECONDS_ESTIMATE = 0.75   # dead-man estimate in seconds per frame (W-11)
MAX_BATCH_SECONDS = 3 * 3600    # hard wall-clock cap of the whole run (about 2090 frames is expected to take 1 h): then the clips so far are fetched and the session stopped


class RunError(Exception):
    pass


def run_cli(args, stdin=None, capture=False, check=True, timeout=CLI_TIMEOUT):
    """One colab command. Returns stdout when capture=True. Every command has a time limit (render review R4: a hung CLI call must not
    block the runner and leave a billable session running)."""
    print("$ colab " + " ".join(args), flush=True)
    try:
        r = subprocess.run(["colab", *args], text=True, env=ENV, input=stdin, stdin=None if stdin is not None else subprocess.DEVNULL,
                           capture_output=capture, timeout=timeout)
    except subprocess.TimeoutExpired:
        raise RunError(f"colab {args[0]} did not finish in {timeout} s")
    if check and r.returncode:
        raise RunError(f"colab {args[0]} failed (exit {r.returncode})")
    return r.stdout if capture else r.returncode


def started(name):
    """True once the script has created /content/out on the VM."""
    out = run_cli(["ls", "-s", name, "/content"], capture=True, check=False) or ""
    return "out/" in out


def fetch(name, results):
    results.mkdir(parents=True, exist_ok=True)
    run_cli(["download", "-s", name, f"{t0.OUT}/FILES.txt", str(results / "FILES.txt")])
    failed = []
    for rel in [x.strip() for x in (results / "FILES.txt").read_text(encoding="utf-8").splitlines() if x.strip()]:   # one path per line: clip names contain spaces
        dst = results / rel
        if dst.exists() and dst.stat().st_size > MIN_CLIP_BYTES and dst.suffix == ".mp4":
            continue            # already home (fetch_ready got it as soon as its shot finished)
        dst.parent.mkdir(parents=True, exist_ok=True)
        try:
            run_cli(["download", "-s", name, f"{t0.OUT}/{rel}", str(dst)])
        except RunError as e:   # one bad file must not strand the rest: go on, report at the end
            print("download failed:", rel, e, flush=True)
            failed.append(rel)
    if failed:
        raise RunError(f"{len(failed)} file(s) did not come home: {failed}")


def hardware(name):
    """The Hardware: field of this session in `colab sessions`, e.g. G4 (None when the session is not listed)."""
    out = run_cli(["sessions"], capture=True, check=False) or ""
    for line in out.splitlines():
        if line.startswith(f"[{name}]"):
            m = re.search(r"Hardware: (\S+)", line)
            return m.group(1) if m else None
    return None


def script_finished(timeline):
    """0 when the on-VM timeline says ALL DONE, 1 when it says FAILED / SETUP FAILED, None while the script is still running."""
    try:
        text = Path(timeline).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    if re.search(r"\] ALL DONE\s*$", text, re.M):
        return 0
    if re.search(r"\] (SETUP FAILED|FAILED:)", text):
        return 1
    return None


def fetch_ready(name, results, got, expected, probe_frames=None):
    """Owner rule 2026-11-09: every clip is saved to this PC as soon as its shot is done (a lost session must not lose clips).
    Reads timeline.txt, and for every `END SHOT-nnn rc=0` not in `got` downloads that shot's mp4 files; the shot id joins `got` only when every
    file came home with a plausible size. Returns the number of shots that came home now."""
    results.mkdir(parents=True, exist_ok=True)
    tl = results / "timeline.txt"
    if run_cli(["download", "-s", name, f"{t0.OUT}/timeline.txt", str(tl)], check=False) or not tl.exists():
        return 0
    n = 0
    for line in tl.read_text(encoding="utf-8", errors="replace").splitlines():
        m = re.search(r"END (SHOT-[0-9A-Za-z]+) rc=0", line)
        if not m or m.group(1) in got:
            continue
        sid = m.group(1)
        if sid not in expected:
            print(f"NOT IN THIS BATCH (not marked home): {sid}", flush=True)
            continue
        listing = run_cli(["ls", "-s", name, f"{t0.OUT}/{sid}"], capture=True, check=False) or ""
        files = [x.strip() for x in listing.splitlines() if x.strip().lower().endswith(".mp4")]
        ok = bool(files)
        for f in files:
            dst = results / sid / f
            dst.parent.mkdir(parents=True, exist_ok=True)
            if run_cli(["download", "-s", name, f"{t0.OUT}/{sid}/{f}", str(dst)], check=False) or not dst.exists() or dst.stat().st_size < MIN_CLIP_BYTES:
                ok = False
        if ok and rs.clip_verified(results, sid, expected[sid], probe_frames=probe_frames):
            got.add(sid)
            n += 1
            print(f"CLIP HOME: {sid} -> {results / sid}", flush=True)
        elif ok:
            print(f"CLIP NOT VERIFIED ({expected[sid]} frames expected), not marked home: {sid}", flush=True)
    return n


def batch(name, gpu, run_py, results, proof_seconds=PROOF_SECONDS, poll=15, popen=subprocess.Popen, sleep=time.sleep, max_seconds=MAX_BATCH_SECONDS,
          clip_poll=CLIP_POLL_SECONDS, clock=time.monotonic, hf_token_file=HF_TOKEN_FILE, expected=None, probe_frames=None):
    if not expected:
        raise ValueError("batch needs the expected frame count of every shot")
    max_seconds = min(max_seconds, MAX_BATCH_SECONDS,
                      rs.deadman_seconds(FRAME_SECONDS_ESTIMATE * max(expected.values()), len(expected)))
    run_cli(["usage"])
    try:
        run_cli(["new", "-s", name, "--gpu", gpu])
    except Exception:     # 2026-11-09: a ConnectionError left an unnamed G4 billing 10 units/hour that the CLI could not stop (MISTAKES W16)
        print("colab new FAILED: a VM may have been created anyway. Sessions and usage now:", flush=True)
        for line in (run_cli(["sessions"], capture=True, check=False) or "").splitlines():
            if line.startswith("["):
                print("STRAY SESSION?: " + line, flush=True)
        run_cli(["usage"], check=False)
        print("A listed session the CLI cannot stop: Colab > Runtime > Manage sessions > its trash icon (not 'Terminate other sessions').", flush=True)
        raise
    keep = False      # True only when the clips may exist on the VM and are not home yet
    proc = None
    try:
        got_hw = hardware(name)
        if got_hw != gpu:    # review R4: a VM that is not the asked GPU is stopped at once (H3 is proven on the G4 only)
            raise RunError(f"the session is {got_hw}, not {gpu}: stopping it")
        for up in sorted(Path(run_py).parent.glob("upload_*.py")):    # the pictures go up in small parts (a big single exec hangs)
            for attempt in (1, 2, 3):      # attempt S009-6: one upload died with 'socket is already closed'; an upload only writes a file, so repeating it is safe
                try:
                    run_cli(["exec", "-s", name, "-f", str(up), "--timeout", "300"], timeout=300)
                    break
                except Exception:
                    if attempt == 3:
                        raise
                    print(f"upload {up.name} failed (attempt {attempt}/3): trying again in 20 s", flush=True)
                    sleep(20)
        if hf_token_file and Path(hf_token_file).is_file():     # owner's HF token: to the VM through stdin only (run_cli prints the arguments, never stdin)
            run_cli(["exec", "-s", name], stdin="open('/content/.hf_token', 'w').write(" + repr(Path(hf_token_file).read_text().strip()) + ")")
            print("HF token sent to the VM (not printed)", flush=True)
        print(f"$ colab exec -s {name} -f {run_py} (background)", flush=True)
        proc = popen(["colab", "exec", "-s", name, "-f", str(run_py), "--timeout", str(EXEC_TIMEOUT)], env=ENV)
        waited, ok = 0, False
        while waited < proof_seconds:
            if started(name):
                ok = True
                break
            if proc.poll() is not None:
                break
            step = min(poll, proof_seconds - waited)    # never sleep past the deadline (W-01: 195 s with the default poll)
            sleep(step)
            waited += step
        if not ok and not started(name):
            raise RunError(f"the script did not start on the VM within {proof_seconds} s (no /content/out): stopping the session")
        keep = True
        got, end = set(), clock() + max_seconds
        while True:
            try:
                rc = proc.wait(timeout=clip_poll)
                break
            except subprocess.TimeoutExpired:
                try:
                    fetch_ready(name, Path(results), got, expected, probe_frames)       # each finished clip comes home at once
                except (RunError, OSError) as e:
                    print("fetch_ready problem (the final fetch will retry):", e, flush=True)
                done = script_finished(Path(results) / "timeline.txt")
                if done is not None:       # W17: the local `colab exec` does not exit when run.py ends, and the VM kept billing for 10 minutes
                    print(f"run.py finished on the VM ({'ALL DONE' if done == 0 else 'FAILED'}): stopping the wait", flush=True)
                    proc.kill()
                    rc = done
                    break
                if clock() > end:
                    print(f"BATCH DEADLINE {max_seconds} s reached: stopping the wait, fetching what finished", flush=True)
                    proc.kill()
                    rc = 124
                    break
        fetch_ready(name, Path(results), got, expected, probe_frames)
        run_cli(["exec", "-s", name], stdin=t0.LIST_CODE)
        fetch(name, Path(results))
        keep = False
        if rc:
            raise RunError(f"run.py exited {rc}; the clips that finished are in {results}")
        d = rs.stop_decision(list(expected), Path(results), all_done=(rc == 0), expected_frames=expected, probe_frames=probe_frames)
        if not d["stop"]:       # every shot must have a verified clip (frame count) before the session may stop
            keep = True
            print(d["reason"], flush=True)
            raise RunError(d["reason"])
    finally:
        if proc is not None and proc.poll() is None:
            proc.kill()         # never leave a local colab exec behind (also on the kept-session path)
        if keep:
            print(f"SESSION KEPT (clips may still be on the VM): fix the download, then run: colab stop -s {name}", flush=True)
        else:
            run_cli(["stop", "-s", name], check=False)
        try:
            listed = run_cli(["sessions"], capture=True, check=False) or ""
        except RunError:
            listed = ""
        if not keep and any(line.startswith(f"[{name}]") for line in listed.splitlines()):
            print(f"SESSION STILL LISTED: {name} (check colab sessions by hand)", flush=True)


def _win32_only(line):
    """True only when the line's environment marker is sys_platform == "win32" (the word win32 in a name does not count)."""
    marker = line.split(";", 1)[1] if ";" in line else ""
    return bool(re.search(r"sys_platform\s*==\s*[\"']win32[\"']", marker))


def preflight_urls(req_text):
    """URLs the runner must reach: Wan2GP's git and every `@ https://` requirement that is not win32-only. chumpy is vendored (wheel_ok checks it)."""
    urls = [WAN2GP_GIT]
    for line in req_text.splitlines():
        s = line.strip()
        if not s or s.startswith("#") or "@ https://" not in s or _win32_only(s) or "chumpy" in s.lower():
            continue
        urls.append(s.split("@", 1)[1].split(";")[0].strip())
    return urls


def settings_failures(folder, run_py):
    """The settings in run.py must be the ones render_manifest.json was written from (W-09 settings_sha256, per shot and per batch)."""
    import build_h3_batch as bh   # lazy: its imports are heavy
    try:
        manifest = json.loads((Path(folder) / "render_manifest.json").read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        return ["manifest unreadable: " + str(e)]
    try:
        fresh = json.loads(json.dumps(manifest))
        bh.add_settings_sha(fresh, Path(run_py).read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        return ["settings check failed: " + str(e)]
    recorded = {s.get("id"): s.get("settings_sha256") for s in manifest.get("shots", [])}
    fails = [sh["id"] + ": settings_sha256 differs from the manifest (settings changed after the manifest was written)"
             for sh in fresh.get("shots", []) if recorded.get(sh["id"]) != sh["settings_sha256"]]
    if manifest.get("settings_sha256") != fresh.get("settings_sha256"):
        fails.append("batch settings_sha256 differs from the manifest")
    return fails


def free_checks(batch_dir, results, req_path, min_free_gb, head=None, disk_usage=None, wheel=None):
    """One gate for a dry run AND --go: URLs, free disk on the results drive, upload parts <= 3 MiB, the chumpy wheel, and the runner's
    settings against the manifest. Returns the failures (empty list = pass). wheel: (path, sha256) for tests; default is the verified wheel."""
    import build_h3_batch as bh   # lazy: its imports are heavy
    folder = Path(batch_dir)
    run_py = folder / "run.py"
    try:
        req_text = Path(req_path).read_text(encoding="utf-8")
    except OSError as e:
        return ["requirements unreadable: " + str(e)]
    disk = Path(results).resolve()
    while not disk.exists() and disk != disk.parent:
        disk = disk.parent
    wheel_path, wheel_sha = wheel if wheel is not None else (bh.WHEEL, bh.WHEEL_SHA256)
    fails = rs.preflight(preflight_urls(req_text), disk, min_free_gb=min_free_gb, script_path=run_py,
                         part_paths=sorted(folder.glob("upload_*.py")), max_part_mb=MAX_PART_MB, head=head, disk_usage=disk_usage)
    if not rs.wheel_ok(wheel_path, wheel_sha):
        fails.append("chumpy wheel missing or sha256 differs: " + str(wheel_path))
    return fails + settings_failures(folder, run_py)


def canary_problems(manifest, proof):
    """--go with more than one shot needs a one-shot canary proof: a shot of this batch, the same settings_sha256, a verified clip, owner_ok."""
    shots = {s["id"]: s for s in manifest.get("shots", [])}
    if len(shots) <= 1:
        return []
    if proof is None:
        return [f"{len(shots)} shots: --go needs --canary-proof (a one-shot canary, clip verified, owner_ok)"]
    problems = []
    sid = proof.get("shot")
    if sid not in shots:
        problems.append(f"canary shot {sid!r} is not in this batch")
    elif proof.get("settings_sha256") != shots[sid].get("settings_sha256"):
        problems.append(f"{sid}: canary settings_sha256 differs from this manifest")
    if proof.get("clip_verified") is not True:
        problems.append("canary clip not verified")
    if proof.get("owner_ok") is not True:
        problems.append("canary proof has no owner_ok")
    return problems


def write_canary_proof(manifest, results, out_path, owner_ok, probe_frames=None):
    """Offline: after a one-shot canary, verify its clip against the expected frames and write the proof that --go reads."""
    shots = manifest.get("shots", [])
    if len(shots) != 1:
        raise RunError("the canary proof is written from a one-shot batch only")
    if not owner_ok:
        raise RunError("--owner-ok is required: the owner has watched the clip")
    sh = shots[0]
    if not rs.clip_verified(results, sh["id"], sh["frames"], probe_frames=probe_frames):
        raise RunError(f"{sh['id']}: clip not verified ({sh['frames']} frames): no proof written")
    proof = {"shot": sh["id"], "settings_sha256": sh["settings_sha256"], "frames": sh["frames"], "clip_verified": True, "owner_ok": True}
    Path(out_path).write_text(json.dumps(proof, indent=1), encoding="utf-8")
    return proof


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("batch")
    ap.add_argument("--results", required=True, help="local folder for the clips and logs")
    ap.add_argument("--go", action="store_true"); ap.add_argument("--gpu", default="G4", choices=("G4",))
    ap.add_argument("--min-free-gb", type=float, required=True, help="free space the results drive must keep (owner decision D5: no default)")
    ap.add_argument("--requirements", required=True, help="the pinned requirements.txt of Wan2GP")
    ap.add_argument("--canary-proof", default=None, help="proof of a one-shot canary (required with --go for a batch of more than one shot)")
    ap.add_argument("--write-canary-proof", action="store_true", help="offline: write --canary-proof from a one-shot batch whose clip is verified")
    ap.add_argument("--owner-ok", action="store_true", help="with --write-canary-proof: the owner has watched the clip")
    a = ap.parse_args(argv)
    run_py = HERE / "colab_batches" / a.batch / "run.py"
    if not run_py.exists():
        print(f"missing {run_py}: build it first (build_h3_batch.py or run_kaggle.py --target colab)")
        return 1
    name = a.batch.replace("_", "-")
    folder = run_py.parent
    if a.write_canary_proof:      # offline: no free_checks (no HEAD requests), no colab call
        if not a.canary_proof:
            print("--write-canary-proof needs --canary-proof <file>")
            return 1
        try:
            manifest = json.loads((folder / "render_manifest.json").read_text(encoding="utf-8"))
            write_canary_proof(manifest, Path(a.results), a.canary_proof, owner_ok=a.owner_ok)
        except (RunError, OSError, ValueError) as e:
            print("CANARY PROOF NOT WRITTEN:", e)
            return 1
        print("canary proof written:", a.canary_proof)
        return 0
    failures = free_checks(folder, Path(a.results), a.requirements, a.min_free_gb)
    if failures:
        for f in failures:
            print("FAILED CHECK:", f)
        return 1
    manifest = json.loads((folder / "render_manifest.json").read_text(encoding="utf-8"))
    shots = manifest.get("shots", [])
    if not a.go:
        for line in (["usage"], ["new", "-s", name, "--gpu", a.gpu], ["exec", "-s", name, "-f", "upload_NN.py (each part, 300 s limit)"],
                     ["exec", "-s", name, "-f", str(run_py), "(background)"],
                     ["ls", "-s", name, "/content", f"(proof within {PROOF_SECONDS} s: out/ must appear, else stop)"],
                     ["exec", "-s", name, "(list files)"], ["download", "-s", name, f"{t0.OUT}/FILES.txt", "..."], ["stop", "-s", name]):
            print("DRY RUN: colab " + " ".join(line))
        if len(shots) > 1:
            print(f"CANARY: {len(shots)} shots; --go needs --canary-proof of one shot of this manifest (a one-shot batch of that shot, "
                  "same settings, then --write-canary-proof --owner-ok)")
        else:
            print("CANARY: none needed (one shot)")
        print("dry run printed")
        return 0
    if len(shots) > 1:
        proof = None
        if a.canary_proof:
            try:
                proof = json.loads(Path(a.canary_proof).read_text(encoding="utf-8"))
            except (OSError, ValueError) as e:
                print("CANARY PROOF UNREADABLE:", e)
                return 1
        problems = canary_problems(manifest, proof)
        if problems:
            for p in problems:
                print("REFUSED:", p)
            return 1
    try:
        expected = {s["id"]: s["frames"] for s in shots}
    except KeyError as e:
        print("REFUSED: a manifest shot has no frame count:", e)
        return 1
    print("LIVE RUN: this spends compute units", flush=True)
    try:
        batch(name, a.gpu, run_py, a.results, expected=expected)
    except (RunError, OSError) as e:
        print("STOPPED:", e)
        return 1
    print(f"done: clips and logs in {a.results}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
