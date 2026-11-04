"""Run a batch of shots on Kaggle (T4, Wan2GP headless, the setup proven 2026-11-04) and download only the outputs.
  python run_kaggle.py shots.json keyframes_root batch_name [--ids SHOT-01,SHOT-02] [--push] [--fetch]
Without --push it only builds kaggle_batches/<batch>/ (script + kernel-metadata.json) so it can be read first.
Images (start, end, refs; paths relative to keyframes_root) are embedded as JPEG (long side 1376). One worker, one T4; models live on
/kaggle/tmp and re-download each session (about 7 min, 49 GB)."""
import argparse
import base64
import io
import json
import subprocess
import time
from pathlib import Path

from PIL import Image

from h3_director import settings_for

HERE = Path(__file__).resolve().parent
WAN2GP_COMMIT = "bd1ff5903cbc18b46c3cce3b75bd140870b536a2"
MAX_EMBED_MB = 20
KAGGLE_USER = "satviksangamkar54321"
RUNNER = r'''
import base64, json, os, shutil, subprocess, time
from pathlib import Path
OUT = Path("/kaggle/working/out"); OUT.mkdir(parents=True, exist_ok=True)
TMP = Path("/kaggle/tmp"); TMP.mkdir(parents=True, exist_ok=True)
APP = Path("/kaggle/working/Wan2GP"); T0 = time.time()
LOG = open(OUT / "timeline.txt", "a", buffering=1)
def note(m):
    line = f"[{time.time() - T0:8.1f}s] {m}"; print(line, flush=True); LOG.write(line + "\n")
def sh(cmd, log="shell.log"):
    note("$ " + cmd); t = time.time()
    with open(OUT / log, "a") as f: rc = subprocess.run(cmd, shell=True, stdout=f, stderr=subprocess.STDOUT).returncode
    note(f"  exit {rc} in {time.time() - t:.1f}s"); return rc
subprocess.Popen(f"nvidia-smi --query-gpu=timestamp,index,memory.used,memory.total,utilization.gpu --format=csv -l 5 > {OUT}/gpu.csv", shell=True)
if sh(f"git clone https://github.com/deepbeepmeep/Wan2GP.git {APP} && git -C {APP} checkout __COMMIT__", "setup.log") or \
        sh(f"cd {APP} && pip install -r requirements.txt", "setup.log"):
    note("SETUP FAILED: see setup.log"); raise SystemExit(1)
(TMP / "ckpts").mkdir(exist_ok=True)
if (APP / "ckpts").is_dir() and not (APP / "ckpts").is_symlink():
    for p in (APP / "ckpts").iterdir(): shutil.move(str(p), TMP / "ckpts" / p.name)
    shutil.rmtree(APP / "ckpts")
if not (APP / "ckpts").exists(): os.symlink(TMP / "ckpts", APP / "ckpts")
os.environ["HF_HOME"] = str(TMP / "hf")
inputs = APP / "inputs"; inputs.mkdir(exist_ok=True)
for name, b64 in json.loads(base64.b64decode("__IMAGES__")).items(): (inputs / name).write_bytes(base64.b64decode(b64))
for sid, settings in json.loads(base64.b64decode("__SETTINGS__")).items():
    f = APP / f"settings_{sid}.json"; f.write_text(json.dumps(settings, indent=1)); shutil.copy(f, OUT / f.name)
    od = OUT / sid; od.mkdir(exist_ok=True); note(f"START {sid}")
    rc = sh(f"cd {APP} && python wgp.py --process {f} --output-dir {od} --profile 5 --verbose 2", f"wgp_{sid}.log")
    note(f"END {sid} rc={rc} files={[p.name for p in od.iterdir()]}")
note("ALL DONE")
'''


def jpeg_b64(path):
    im = Image.open(path).convert("RGB")
    im.thumbnail((1376, 1376), Image.LANCZOS)
    buf = io.BytesIO(); im.save(buf, "JPEG", quality=95)
    return base64.b64encode(buf.getvalue()).decode("ascii")


def build(shots, root, batch, ids=None):
    """Returns (script_text, kernel_metadata). Image paths are rewritten to /kaggle/working/Wan2GP/inputs/<flat name>."""
    chosen = [s for s in shots if not ids or s["id"] in ids]
    if not chosen:
        raise ValueError("no shots selected")
    images, settings = {}, {}

    def embed(rel):
        """The full relative path names the file on Kaggle, so same-named files from different folders never collide."""
        flat = Path(rel).with_suffix(".jpg").as_posix().replace("/", "__")
        if flat not in images:
            images[flat] = jpeg_b64(Path(root) / rel)
        return f"/kaggle/working/Wan2GP/inputs/{flat}"

    for shot in chosen:
        shot = dict(shot)
        for key in ("start", "end"):
            if shot.get(key):
                shot[key] = embed(shot[key])
        if shot.get("refs"):
            shot["refs"] = [embed(ref) for ref in shot["refs"]]
        settings[shot["id"]] = settings_for(shot)
    blob = base64.b64encode(json.dumps(images).encode()).decode()
    if len(blob) > MAX_EMBED_MB * 1024 * 1024:
        raise ValueError(f"embedded images are {len(blob) / 2**20:.1f} MB (limit {MAX_EMBED_MB}): run fewer shots per batch")
    script = (RUNNER.replace("__COMMIT__", WAN2GP_COMMIT).replace("__IMAGES__", blob)
              .replace("__SETTINGS__", base64.b64encode(json.dumps(settings).encode()).decode()))
    slug = f"anime-{batch}".lower().replace("_", "-")
    meta = {"id": f"{KAGGLE_USER}/{slug}", "title": slug, "code_file": "run.py", "language": "python", "kernel_type": "script",
            "is_private": "true", "enable_gpu": "true", "enable_tpu": "false", "enable_internet": "true", "machine_shape": "NvidiaTeslaT4",
            "dataset_sources": [], "competition_sources": [], "kernel_sources": [], "model_sources": []}
    return script, meta


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("shots"); ap.add_argument("root"); ap.add_argument("batch")
    ap.add_argument("--ids", default=""); ap.add_argument("--push", action="store_true"); ap.add_argument("--fetch", action="store_true")
    ap.add_argument("--timeout", type=int, default=4 * 3600)
    a = ap.parse_args(argv)
    folder = HERE / "kaggle_batches" / a.batch; folder.mkdir(parents=True, exist_ok=True)
    script, meta = build(json.loads(Path(a.shots).read_text(encoding="utf-8")), a.root, a.batch, set(filter(None, a.ids.split(","))))
    (folder / "run.py").write_text(script, encoding="utf-8")
    (folder / "kernel-metadata.json").write_text(json.dumps(meta, indent=1), encoding="utf-8")
    print("built", folder)
    if a.push:
        subprocess.run(["kaggle", "kernels", "push", "-p", str(folder), "-t", str(a.timeout)], check=True)
    if a.fetch:
        while "RUNNING" in (s := subprocess.run(["kaggle", "kernels", "status", meta["id"]], capture_output=True, text=True).stdout) or "QUEUED" in s:
            time.sleep(120)
        print(s.strip())
        # owner rule 2026-11-04: download only the videos, never the whole kernel output (it holds the Wan2GP repo and LoRA files)
        subprocess.run(["kaggle", "kernels", "output", meta["id"], "-p", str(folder / "results"), "--file-pattern", r"\.mp4$"], check=True)


if __name__ == "__main__":
    main()
