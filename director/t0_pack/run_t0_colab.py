"""Run the T0 batch on Google Colab with the official `colab` CLI. A DRY RUN unless --go: a real run spends the owner's compute units.
  python run_t0_colab.py                 -> prints the commands only
  python run_t0_colab.py --go --gpu G4   -> runs them
Order: colab usage; colab new; colab exec -f colab_batches/t0/run.py (long timeout); a list script on stdin names the .mp4 files
and timeline.txt, RESULT.json, gpu.csv under /content/out into FILES.txt; colab download of FILES.txt, then of each file it names,
into results/; colab stop in a finally block, always. Clips that finished are downloaded even if the batch fails. No retries.
The Colab CLI README says Linux and macOS only; it installed and signed in on Windows (2026-11-05: usage, new --gpu G4, exec, stop all worked). Never run the CLI with --logtostderr: it prints the bearer token. This script never reads or prints tokens."""
import argparse
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
RUN_PY = HERE.parent / "colab_batches" / "t0" / "run.py"
RESULTS = HERE / "results"
OUT = "/content/out"
EXEC_TIMEOUT = 6 * 3600   # seconds; the CLI default is 30 s, far too short for a batch (estimate, not measured)
LIST_CODE = """
import os
out = "/content/out"
names = sorted(os.path.relpath(os.path.join(d, f), out) for d, _, fs in os.walk(out) for f in fs if f.endswith(".mp4"))
names += [n for n in sorted(os.listdir(out)) if n in ("timeline.txt", "RESULT.json", "gpu.csv") or (n.startswith("wgp_") and n.endswith(".log"))]   # wgp logs prove the LoRA load
open(os.path.join(out, "FILES.txt"), "w").write("\\n".join(names) + "\\n")
print("\\n".join(names))
"""
DRY = True


class CliError(Exception):
    pass


def cli(args, stdin=None):
    """One colab command. In a dry run it only prints the command."""
    print(("DRY RUN: " if DRY else "$ ") + "colab " + " ".join(args) + ("  (code on stdin)" if stdin else ""), flush=True)
    if DRY:
        return
    kwargs = {"input": stdin} if stdin is not None else {"stdin": subprocess.DEVNULL}
    if subprocess.run(["colab", *args], text=True, **kwargs).returncode:
        raise CliError(f"colab {args[0]} failed: stopping, no retries")


def fetch(name):
    """FILES.txt first, then each file it names (the CLI downloads one file per call)."""
    if not DRY:
        RESULTS.mkdir(parents=True, exist_ok=True)   # colab download does not create the local folder (T0 run 1 lost 6 clips to this)
    cli(["download", "-s", name, f"{OUT}/FILES.txt", str(RESULTS / "FILES.txt")])
    if DRY:
        cli(["download", "-s", name, f"{OUT}/<each file named in FILES.txt>", "results/<same path>"])
        return
    if not (RESULTS / "FILES.txt").exists():
        raise CliError("FILES.txt did not come back: nothing to fetch")
    for rel in (RESULTS / "FILES.txt").read_text(encoding="utf-8").split():
        (RESULTS / rel).parent.mkdir(parents=True, exist_ok=True)
        cli(["download", "-s", name, f"{OUT}/{rel}", str(RESULTS / rel)])


def batch(name, gpu):
    cli(["usage"])
    error = None
    try:
        cli(["new", "-s", name, "--gpu", gpu])
        try:
            cli(["exec", "-s", name, "-f", str(RUN_PY), "--timeout", str(EXEC_TIMEOUT)])
        except CliError as e:
            error = e   # the clips that finished still come home
        cli(["exec", "-s", name], stdin=LIST_CODE)
        fetch(name)
    except CliError as e:   # the clips exist only on the VM: keep it so they can be fetched by hand, then stop it
        print(f"SESSION KEPT (clips still on the VM): fix the download, then run: colab stop -s {name}")
        raise e
    cli(["stop", "-s", name])   # only after the clips are home; a running session keeps spending units
    if error:
        raise error


def main(argv=None):
    global DRY
    ap = argparse.ArgumentParser(description="Run the T0 batch on Colab (dry run unless --go).")
    ap.add_argument("--go", action="store_true", help="really run the commands (spends compute units)")
    ap.add_argument("--gpu", default="G4", choices=("G4", "A100", "L4", "T4"))
    ap.add_argument("--name", default="t0-kaliya", help="Colab session name")
    a = ap.parse_args(argv)
    DRY = not a.go
    if not RUN_PY.exists():
        print(f"missing {RUN_PY}: build it first with run_kaggle.py --target colab (see README)")
        if not DRY:
            return 1
    if sys.platform == "win32":
        print("note: the Colab CLI README says Linux and macOS only; on this Windows PC usage, new --gpu G4, exec and stop worked (2026-11-05)")
    print("DRY RUN: nothing is started" if DRY else "LIVE RUN: this spends compute units", flush=True)
    try:
        batch(a.name, a.gpu)
    except (CliError, OSError) as e:
        print("STOPPED:", e)
        return 1
    print("dry run printed" if DRY else f"done: clips and logs in {RESULTS}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
