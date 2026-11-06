"""Run a batch of shots on Kaggle (T4, Wan2GP headless, the setup proven 2026-11-04) and download only the outputs.
  python run_kaggle.py shots.json keyframes_root batch_name [--ids SHOT-01,SHOT-02] [--push] [--fetch]
  python run_kaggle.py ... --target colab [--profile N]   -> colab_batches/<batch>/run.py + run.ipynb (upload to Colab, Run all)
Without --push it only builds kaggle_batches/<batch>/ (script + kernel-metadata.json) so it can be read first.
Images (start, end, refs; paths relative to keyframes_root) are embedded losslessly as PNG (long side capped at 1376, LANCZOS).
Flow downloads are JPEG, so .jpg and .jpeg sources are accepted and re-encoded losslessly to PNG (no loss beyond the JPEG itself).
One worker, one T4; models live on /kaggle/tmp and re-download each session (about 7 min, 49 GB)."""
import argparse
import base64
import io
import json
import re
import subprocess
import time
from pathlib import Path

from PIL import Image

import style_bible
from h3_director import check_unique_ids, settings_for

HERE = Path(__file__).resolve().parent
WAN2GP_COMMIT = "bd1ff5903cbc18b46c3cce3b75bd140870b536a2"
MAX_EMBED_MB = 20
KAGGLE_USER = "satviksangamkar54321"
# where the script runs: (working dir, model cache). Colab's /content is wiped each session, so models re-download there too.
# ponytail: no Google Drive cache yet; add one ("/content/drive/MyDrive/...") if per-session downloads cost too many units
TARGETS = {"kaggle": ("/kaggle/working", "/kaggle/tmp"), "colab": ("/content", "/content/cache")}
RUNNER = r'''
import base64, json, os, shutil, subprocess, time
from pathlib import Path
OUT = Path("__BASE__/out"); OUT.mkdir(parents=True, exist_ok=True)
TMP = Path("__CACHE__"); TMP.mkdir(parents=True, exist_ok=True)
APP = Path("__BASE__/Wan2GP"); T0 = time.time()
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
def finish(results):
    (OUT / "RESULT.json").write_text(json.dumps(results, indent=1))
    failed = sorted(s for s, v in results.items() if v != "ok")
    if failed:
        note("FAILED: " + ", ".join(failed)); raise SystemExit(1)
    note("ALL DONE")
results = {}
for sid, settings in json.loads(base64.b64decode("__SETTINGS__")).items():
    f = APP / f"settings_{sid}.json"; f.write_text(json.dumps(settings, indent=1)); shutil.copy(f, OUT / f.name)
    od = OUT / sid; od.mkdir(exist_ok=True); note(f"START {sid}")
    for attempt in range(1, 5):   # Hugging Face answers 429 (Too Many Requests) at times and fails in under a minute: wait and retry, resumes partial files
        lg = OUT / f"wgp_{sid}.log"; start = lg.stat().st_size if lg.exists() else 0   # only THIS attempt's output may trigger a retry
        rc = sh(f"cd {APP} && python wgp.py --process {f} --output-dir {od} --profile __PROFILE__ --verbose 2", f"wgp_{sid}.log")
        files = sorted(p.name for p in od.iterdir())
        if any(n.endswith(".mp4") for n in files): break
        if "429 Too Many Requests" not in lg.read_bytes()[start:].decode(errors="replace") or attempt == 4: break
        note(f"HF 429 on {sid}, attempt {attempt}: waiting {60 * attempt}s"); time.sleep(60 * attempt)
    results[sid] = "ok" if rc == 0 and any(n.endswith(".mp4") for n in files) else "failed"
    note(f"END {sid} rc={rc} files={files}")
finish(results)
'''


DOWNLOAD_CELL = """# RUN THIS AFTER THE CELL ABOVE PRINTS 'ALL DONE': zips the clips and logs, then downloads T0_clips.zip to your PC.
import glob, os, shutil
os.makedirs('/content/T0_clips', exist_ok=True)
for f in glob.glob('/content/out/**/*.mp4', recursive=True) + glob.glob('/content/out/*.txt') + glob.glob('/content/out/*.json') + glob.glob('/content/out/*.csv') + glob.glob('/content/out/wgp_*.log'):
    shutil.copy(f, '/content/T0_clips/' + os.path.basename(f))
print(sorted(os.listdir('/content/T0_clips')))
shutil.make_archive('/content/T0_clips', 'zip', '/content/T0_clips')
from google.colab import files
files.download('/content/T0_clips.zip')
"""


def chunk_long_literals(script, width=4000):
    """Colab's editor freezes on a 7 MB single line: rewrite each huge b64decode("...") literal as implicitly concatenated 4 KB pieces
    (same string, one piece per line, wrapped in parentheses)."""
    def cut(m):
        blob = m.group(1)
        if len(blob) <= 20000:
            return m.group(0)
        parts = "\n".join(f'"{blob[i:i + width]}"' for i in range(0, len(blob), width))
        return f'b64decode((\n{parts}\n))'
    return re.sub(r'b64decode\("([A-Za-z0-9+/=]+)"\)', cut, script)


def png_b64(path):
    """Lossless PNG; only a picture whose long side is over 1376 is shrunk (LANCZOS; thumbnail never enlarges)."""
    im = Image.open(path)
    if im.mode not in ("RGB", "RGBA", "L", "LA", "P"):   # CMYK and the like: PNG cannot store them
        im = im.convert("RGB")
    im.thumbnail((1376, 1376), Image.LANCZOS)
    buf = io.BytesIO(); im.save(buf, "PNG")
    return base64.b64encode(buf.getvalue()).decode("ascii")


def embedder(root, images, base="/kaggle/working"):
    """embed(rel) -> the path on Kaggle. images maps flat name -> (relative source, PNG base64); the full relative path
    names the file, so same-named files from different folders never collide (a real clash raises)."""
    def embed(rel):
        flat = Path(rel).with_suffix(".png").as_posix().replace("/", "__")
        if flat not in images:
            images[flat] = (rel, png_b64(Path(root) / rel))
        elif images[flat][0] != rel:
            raise ValueError(f"{rel} and {images[flat][0]} would both be {flat} on Kaggle")
        return f"{base}/Wan2GP/inputs/{flat}"
    return embed


def build(shots, root, batch, ids=None, bible=None, require_bible=False, target="kaggle", profile=5, manifest=None):
    """Returns (script_text, kernel_metadata). Image paths are rewritten to <base>/Wan2GP/inputs/<flat name>.png.
    target: "kaggle" or "colab" (paths and model cache, see TARGETS); profile: Wan2GP --profile (5 = lowest VRAM, the T4 setting).
    manifest: an empty dict to fill with the render manifest (G3: route, resolution, frames, settings file, embed MB per shot)."""
    base, cache = TARGETS[target]
    check_unique_ids(shots)   # every id in the batch, before the selection
    chosen = [s for s in shots if not ids or s["id"] in ids]
    if not chosen:
        raise ValueError("no shots selected")
    images, settings = {}, {}
    embed = embedder(root, images, base)
    for shot in chosen:
        settings[shot["id"]] = settings_for(shot, bible, embed, require_bible)
    per_shot = {}   # base64 MB of the pictures each shot embeds (flat names come back from the settings paths)
    for shot in chosen:
        s = settings[shot["id"]]
        names = {Path(p).name for p in [s.get("image_start"), s.get("image_end"), *(s.get("image_refs") or [])] if p}
        per_shot[shot["id"]] = round(sum(len(images[n][1]) for n in names) / 2**20, 6)
    images = {flat: b64 for flat, (_, b64) in images.items()}
    blob = base64.b64encode(json.dumps(images).encode()).decode()
    if len(blob) > MAX_EMBED_MB * 1024 * 1024:
        raise ValueError(f"embedded images are {len(blob) / 2**20:.1f} MB (limit {MAX_EMBED_MB}): run fewer shots per batch")
    if manifest is not None:
        manifest.update({"batch": batch, "target": target, "profile": int(profile), "embed_mb_total": round(len(blob) / 2**20, 6), "shots": [
            {"id": sh["id"], "route": sh.get("route", "pika6"), "mode": sh["mode"], "resolution": settings[sh["id"]]["resolution"],
             "frames": settings[sh["id"]]["video_length"], "settings_file": f"settings_{sh['id']}.json", "embed_mb": per_shot[sh["id"]]}
            for sh in chosen]})
    script = (RUNNER.replace("__COMMIT__", WAN2GP_COMMIT).replace("__BASE__", base).replace("__CACHE__", cache)
              .replace("__PROFILE__", str(int(profile))).replace("__IMAGES__", blob)
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
    ap.add_argument("--style", required=True, help="style bible project (style/<name>.json) whose text goes into the prompts")
    ap.add_argument("--target", choices=sorted(TARGETS), default="kaggle")
    ap.add_argument("--profile", type=int, default=5, help="Wan2GP memory profile (5 = lowest VRAM; bigger GPUs can use a lower number)")
    a = ap.parse_args(argv)
    if a.target == "colab" and (a.push or a.fetch):
        ap.error("--push/--fetch are Kaggle only; for Colab upload run.ipynb and run it")
    folder = HERE / f"{a.target}_batches" / a.batch; folder.mkdir(parents=True, exist_ok=True)
    bible = style_bible.load(a.style)
    manifest = {}
    script, meta = build(json.loads(Path(a.shots).read_text(encoding="utf-8")), a.root, a.batch,
                         set(filter(None, a.ids.split(","))), bible, require_bible=True, target=a.target, profile=a.profile, manifest=manifest)
    (folder / "run.py").write_text(script, encoding="utf-8")
    if a.target == "colab":   # G3: what the batch renders, for the UI and the Colab unit estimate
        (folder / "render_manifest.json").write_text(json.dumps(manifest, indent=1, ensure_ascii=False), encoding="utf-8")
    if a.target == "colab":   # one-cell notebook: File > Upload notebook in Colab, pick the GPU, Run all; clips land in /content/out
        nb = {"nbformat": 4, "nbformat_minor": 5,
              "metadata": {"accelerator": "GPU", "colab": {"gpuType": "G4", "provenance": []}, "kernelspec": {"name": "python3", "display_name": "Python 3"}},
              "cells": [{"id": "render", "cell_type": "code", "metadata": {}, "execution_count": None, "outputs": [], "source": chunk_long_literals(script).splitlines(True)},
                {"id": "download", "cell_type": "code", "metadata": {}, "execution_count": None, "outputs": [], "source": DOWNLOAD_CELL.splitlines(True)}]}
        (folder / "run.ipynb").write_text(json.dumps(nb, indent=1), encoding="utf-8")
    else:
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
