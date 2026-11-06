"""Run a built Colab batch (<batch>/run.py) and download every clip THE MOMENT it finishes, in parallel with the next render.
  python run_t0_parallel.py [--batch DIR] [--results DIR] [--gpu G4] [--name NAME]        (no --go = dry run, no Colab call)
  python run_t0_parallel.py ... --go                                                      (starts a Colab session: spends units)
Defaults: --batch colab_batches/t0 and --results t0_pack/results (the T0 run as before).
Polls `colab ls` (the Jupyter files API works while the kernel is busy). The session is stopped ONLY after every expected clip is home;
if a clip is missing the session is kept and the script says so loudly. A real run writes RESULTS/status.json (G2): clips home and
missing, session, rc, usage before and after, stop verified. Never prints tokens; never use --logtostderr."""
import argparse, json, os, re, subprocess, sys, time
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
BATCH = HERE.parent / "colab_batches" / "t0"
RESULTS = HERE / "results"
CLI = os.path.expanduser("~/.local/bin/colab.exe")
OUT = "/content/out"


def cli(args, timeout=600, **kw):
    return subprocess.run([CLI, *args], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout, **kw)


def ls(name, path):
    r = cli(["ls", "-s", name, path], timeout=120)
    if r.returncode != 0 and "not found" not in (r.stdout + r.stderr).lower():
        print(f"ls {path} failed: {(r.stdout + r.stderr).strip()[-160:]}", flush=True)   # a real error, not an empty folder
    return [l.rstrip("\r") for l in r.stdout.splitlines() if l.strip()] if r.returncode == 0 else []


def playable(path):
    """A half-written mp4 has no index: ffprobe fails. A good T0 clip is about 5.17 s."""
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)], capture_output=True, text=True)
    try:
        return r.returncode == 0 and 4.5 <= float(r.stdout.strip()) <= 6.5
    except ValueError:
        return False


def expected_ids(run_py):
    import base64, json   # the shot settings are embedded in run.py as a base64 JSON blob (image blob has no SHOT keys)
    s = Path(run_py).read_text(encoding="utf-8")
    ids = set()
    for blob in re.findall(r'b64decode\("([A-Za-z0-9+/=]+)"\)', s):
        d = json.loads(base64.b64decode(blob))
        ids |= {k for k in d if k.startswith("SHOT-")}
    return sorted(ids)


def sweep(name, ids, got, results):
    """Download every finished mp4 not yet home; True when something new arrived."""
    new = False
    for d in ls(name, OUT):
        if not d.endswith("/") or d[:-1] in got and got[d[:-1]]:
            continue
        sid = d[:-1]
        for f in ls(name, f"{OUT}/{sid}"):
            if f.endswith(".mp4"):
                dest = results / sid / f
                dest.parent.mkdir(parents=True, exist_ok=True)
                r = cli(["download", "-s", name, f"{OUT}/{sid}/{f}", str(dest)])
                if r.returncode == 0 and dest.exists() and dest.stat().st_size > 100_000 and playable(dest):
                    got[sid] = str(dest); new = True
                    print(f"HOME {sid} ({dest.stat().st_size // 1024} KB)", flush=True)
                else:
                    print(f"download failed for {sid}: {(r.stdout + r.stderr).strip()[-200:]}", flush=True)
    return new


def write_status(results, **fields):
    results.mkdir(parents=True, exist_ok=True)
    fields["time"] = datetime.now().astimezone().isoformat(timespec="seconds")
    (results / "status.json").write_text(json.dumps(fields, indent=1, ensure_ascii=False), encoding="utf-8")


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--go", action="store_true"); ap.add_argument("--gpu", default="G4"); ap.add_argument("--name", default="t0-kaliya")
    ap.add_argument("--batch", type=Path, default=BATCH, help="batch folder that holds run.py")
    ap.add_argument("--results", type=Path, default=RESULTS, help="folder for the clips, timeline and status.json")
    a = ap.parse_args(argv)
    run_py, results = a.batch / "run.py", a.results
    ids = expected_ids(run_py)
    print(f"clips expected: {ids}")
    if not a.go:
        print("DRY RUN: colab new / colab exec (background) / poll colab ls + colab download per clip / verify all home / colab stop / colab sessions")
        return 0
    results.mkdir(parents=True, exist_ok=True)
    before = cli(["usage"]).stdout.strip()
    print(before, flush=True)
    r = cli(["new", "-s", a.name, "--gpu", a.gpu]); print(r.stdout.strip(), flush=True)
    if r.returncode:
        print("could not start the session:", (r.stdout + r.stderr).strip()[-400:])
        write_status(results, session=a.name, gpu=a.gpu, rc=1, started=False, expected=ids, home=[], missing=ids, usage_before=before)
        return 1
    log = open(results.parent / "run_t0_parallel.log", "w", encoding="utf-8")
    env = ["--env", f"HF_TOKEN={os.environ['HF_TOKEN']}"] if os.environ.get("HF_TOKEN") else []   # optional: lifts the Hugging Face rate limit; never printed
    p = subprocess.Popen([CLI, "exec", "-s", a.name, "-f", str(run_py), "--timeout", "7200", *env], stdout=log, stderr=subprocess.STDOUT)
    got = {}
    while p.poll() is None:
        sweep(a.name, ids, got, results); time.sleep(15)
    sweep(a.name, ids, got, results)
    for extra in ("timeline.txt", "RESULT.json", "gpu.csv"):
        cli(["download", "-s", a.name, f"{OUT}/{extra}", str(results / extra)])
    for sid in ids:
        for f in ls(a.name, OUT):
            if f.startswith(f"wgp_{sid}") and f.endswith(".log"):
                cli(["download", "-s", a.name, f"{OUT}/{f}", str(results / f)])
    missing = [i for i in ids if i not in got]
    base = dict(session=a.name, gpu=a.gpu, started=True, run_rc=p.returncode, expected=ids, home=sorted(got), missing=missing, usage_before=before)
    if missing:
        print(f"SESSION KEPT: clips still missing {missing}; fetch them, then run: colab stop -s {a.name}")
        write_status(results, rc=2, stop_verified=False, usage_after=None, **base)
        return 2
    for _ in range(3):   # the stop must be VERIFIED: a session left running keeps billing
        print(cli(["stop", "-s", a.name]).stdout.strip(), flush=True)
        left = cli(["sessions"]).stdout
        if a.name not in left:
            break
    print("sessions after stop:", left.strip(), flush=True)
    after = cli(["usage"]).stdout.strip()
    if a.name in left:
        print(f"STOP FAILED: run `colab stop -s {a.name}` now")
        write_status(results, rc=3, stop_verified=False, usage_after=after, **base)
        return 3
    print(after)
    write_status(results, rc=0, stop_verified=True, usage_after=after, **base)
    return 0


if __name__ == "__main__":
    sys.exit(main())
