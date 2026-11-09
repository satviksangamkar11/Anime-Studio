"""Run any built Colab batch (director/colab_batches/<batch>/run.py) with the official `colab` CLI. DRY RUN unless --go (a real run spends units).
  python run_colab_batch.py BATCH --results OUT_DIR                  -> prints the commands only
  python run_colab_batch.py BATCH --results OUT_DIR --go --gpu G4    -> runs them (spends units)
Sequence (render pre-flight review 2026-11-09, blot RULE 28): usage, new, `exec -f run.py` as a background process, PROOF within 180 s that the
script started on the VM (`ls /content` shows out/), else kill the exec and stop the session at once; wait for the run; list + download every
file; stop. The session is stopped on EVERY exit path except one: once the script has started and the clips are still on the VM, a failed
download keeps the session (stopping it would delete the clips) and prints the stop command. Never --logtostderr."""
import argparse
import os
import re
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "t0_pack"))
import run_t0_colab as t0  # noqa: E402

ENV = {**os.environ, "MSYS_NO_PATHCONV": "1"}     # Git Bash would turn /content into C:/Program Files/Git/content
EXEC_TIMEOUT = 6 * 3600    # exec --timeout is an IDLE limit (seconds)
PROOF_SECONDS = 180
HF_TOKEN_FILE = "D:/aai work/secrets/huggingface/hf_token.txt"    # one line, never printed or logged; a missing file means no token (429 retries only)
CLI_TIMEOUT = 600               # seconds for any single colab command except the long exec of run.py
CLIP_POLL_SECONDS = 60         # how often finished clips are copied to this PC while the render runs
MIN_CLIP_BYTES = 50_000         # a smaller mp4 is not a finished clip
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


def fetch_ready(name, results, got):
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
        listing = run_cli(["ls", "-s", name, f"{t0.OUT}/{sid}"], capture=True, check=False) or ""
        files = [x.strip() for x in listing.splitlines() if x.strip().lower().endswith(".mp4")]
        ok = bool(files)
        for f in files:
            dst = results / sid / f
            dst.parent.mkdir(parents=True, exist_ok=True)
            if run_cli(["download", "-s", name, f"{t0.OUT}/{sid}/{f}", str(dst)], check=False) or not dst.exists() or dst.stat().st_size < MIN_CLIP_BYTES:
                ok = False
        if ok:
            got.add(sid)
            n += 1
            print(f"CLIP HOME: {sid} -> {results / sid}", flush=True)
    return n


def batch(name, gpu, run_py, results, proof_seconds=PROOF_SECONDS, poll=15, popen=subprocess.Popen, sleep=time.sleep, max_seconds=MAX_BATCH_SECONDS,
          clip_poll=CLIP_POLL_SECONDS, clock=time.monotonic, hf_token_file=HF_TOKEN_FILE):
    run_cli(["usage"])
    try:
        run_cli(["new", "-s", name, "--gpu", gpu])
    except Exception:     # 2026-11-09: a ConnectionError left an unnamed G4 billing 10 units/hour that the CLI could not stop (MISTAKES W16)
        print("colab new FAILED: a VM may have been created anyway. Sessions and usage now:", flush=True)
        run_cli(["sessions"], check=False)
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
        while waited <= proof_seconds:
            if started(name):
                ok = True
                break
            if proc.poll() is not None:
                break
            sleep(poll)
            waited += poll
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
                    fetch_ready(name, Path(results), got)       # each finished clip comes home at once
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
        fetch_ready(name, Path(results), got)
        run_cli(["exec", "-s", name], stdin=t0.LIST_CODE)
        fetch(name, Path(results))
        keep = False
        if rc:
            raise RunError(f"run.py exited {rc}; the clips that finished are in {results}")
    finally:
        if proc is not None and proc.poll() is None:
            proc.kill()         # never leave a local colab exec behind (also on the kept-session path)
        if keep:
            print(f"SESSION KEPT (clips may still be on the VM): fix the download, then run: colab stop -s {name}", flush=True)
        else:
            run_cli(["stop", "-s", name], check=False)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("batch")
    ap.add_argument("--results", required=True, help="local folder for the clips and logs")
    ap.add_argument("--go", action="store_true"); ap.add_argument("--gpu", default="G4", choices=("G4", "A100", "L4", "T4"))
    a = ap.parse_args(argv)
    run_py = HERE / "colab_batches" / a.batch / "run.py"
    if not run_py.exists():
        print(f"missing {run_py}: build it first (build_h3_batch.py or run_kaggle.py --target colab)")
        return 1
    name = a.batch.replace("_", "-")
    if not a.go:
        for line in (["usage"], ["new", "-s", name, "--gpu", a.gpu], ["exec", "-s", name, "-f", "upload_NN.py (each part, 300 s limit)"],
                     ["exec", "-s", name, "-f", str(run_py), "(background)"],
                     ["ls", "-s", name, "/content", f"(proof within {PROOF_SECONDS} s: out/ must appear, else stop)"],
                     ["exec", "-s", name, "(list files)"], ["download", "-s", name, f"{t0.OUT}/FILES.txt", "..."], ["stop", "-s", name]):
            print("DRY RUN: colab " + " ".join(line))
        print("dry run printed")
        return 0
    print("LIVE RUN: this spends compute units", flush=True)
    try:
        batch(name, a.gpu, run_py, a.results)
    except (RunError, OSError) as e:
        print("STOPPED:", e)
        return 1
    print(f"done: clips and logs in {a.results}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
