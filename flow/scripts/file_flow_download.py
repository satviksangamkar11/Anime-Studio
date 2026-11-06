"""Files a Flow 2K download (from Downloads) into the Anime Studio (Kaliya Mardan) structure and logs it.
usage: file_flow_download.py <download path> <IMAGE_ID> <vNN> <flow edit id> <references joined by |> <notes> [sub] [v2 jobs file] [model shown on screen]
Root: env FLOW_OUT_ROOT (default D:/aai work/flow_outputs/anime_kaliya), then adhyay_NN.
Adhyay: env FLOW_ADHYAY (default 1). With a v2 jobs file the logged prompt_sha256 is that job's prompt_sha256 field; without one it is null and prompt_source is "none".
The model is the one read off the screen (arg) - else env FLOW_MODEL - else "unknown". Operator: env FLOW_OPERATOR (default claude).
Optional env, set by download_queue collect from the queue item (empty = not set = old behaviour):
  FLOW_ASPECT (16:9 or 9:16), FLOW_APPROVED_DHASH (16 hex chars), FLOW_LINEAGE (free text), FLOW_DECIDED_BY (owner, claude or haiku).
A refusal prints "REFUSED: <reason>" to stderr and exits 2. The checks are explicit, not asserts (asserts vanish under python -O).
2K check: 2752x1536 (16:9 sheets and plates) or 1536x2752 (9:16 keyframes)."""
import datetime
import hashlib
import json
import os
import re
import shutil
import sys
import time
from pathlib import Path

from PIL import Image

from fingerprint import dhash_image, hamming

SIZES = {"16:9": (2752, 1536), "9:16": (1536, 2752)}
FINGERPRINT_MAX_DISTANCE = 14


def refuse(reason: str):
    print(f"REFUSED: {reason}", file=sys.stderr)
    sys.exit(2)


src, iid, ver, edit, refs, notes = sys.argv[1:7]
sub = sys.argv[7] if len(sys.argv) > 7 else "references"
if Path(sub).is_absolute() or ".." in Path(sub).parts:   # the sub-folder must stay inside the chapter folder (Dots review 2026-11-06)
    print("REFUSED: sub-folder must be a relative path inside the chapter folder", file=sys.stderr)
    sys.exit(2)
jobs_file = sys.argv[8] if len(sys.argv) > 8 and sys.argv[8] else None
model_arg = sys.argv[9] if len(sys.argv) > 9 and sys.argv[9] else None
aspect = os.environ.get("FLOW_ASPECT", "").strip() or None
approved = os.environ.get("FLOW_APPROVED_DHASH", "").strip().lower() or None
lineage = os.environ.get("FLOW_LINEAGE", "") or None
decided_by = os.environ.get("FLOW_DECIDED_BY", "").strip() or None
if aspect is not None and aspect not in SIZES:
    refuse(f"aspect must be 16:9 or 9:16, got {aspect}")
if approved is not None and not re.fullmatch(r"[0-9a-f]{16}", approved):
    refuse(f"approved dHash must be 16 hex characters, got {approved}")
root = Path(os.environ.get("FLOW_OUT_ROOT", "D:/aai work/flow_outputs/anime_kaliya")) / f"adhyay_{int(os.environ.get('FLOW_ADHYAY', '1')):02d}"
job = None
if jobs_file:
    job = next((j for j in json.loads(Path(jobs_file).read_text(encoding="utf-8")) if j["shot_id"] == iid), None)
    if job is None:
        refuse(f"{iid} is not in {jobs_file}")
d = Path(src).read_bytes()
if not (d[:2] == b"\xff\xd8" and d[-2:] == b"\xff\xd9"):
    refuse("not a complete JPEG")
jpg, png = root / sub / f"{iid}__candidate_{ver}__2K_source.jpg", root / sub / f"{iid}__candidate_{ver}.png"
if jpg.exists() or png.exists():
    refuse(f"refusing to overwrite {jpg.name}")
new_sha = hashlib.sha256(d).hexdigest()
for old in root.rglob("*__2K_source.jpg"):
    if hashlib.sha256(old.read_bytes()).hexdigest() == new_sha:
        refuse(f"this file is identical to {old.name}: the new download has not arrived yet")
# 300 s is the guard for hand filing: the file must be the download just made.
# collect passes FLOW_MAX_AGE_S=604800 (7 days) on purpose: the download pass files saves by exact tile title, often long
# after they were downloaded, so this guard would refuse good files there. The title and duplicate-bytes checks still apply.
_max_age = int(os.environ.get("FLOW_MAX_AGE_S", "300"))
if time.time() - Path(src).stat().st_mtime >= _max_age:
    refuse(f"the download is older than {_max_age} s: it is not the download you just made")
_probe = Image.open(src)                                              # validate BEFORE copying: no partial filing
size = _probe.size
if size not in SIZES.values():
    refuse(f"not 2K 16:9 or 9:16: {size}")
if aspect is not None and size != SIZES[aspect]:
    refuse(f"wrong orientation: aspect {aspect} needs {SIZES[aspect][0]}x{SIZES[aspect][1]}, got {size[0]}x{size[1]}")
fingerprint = "none"
if approved is not None:
    got = dhash_image(_probe)
    dist = hamming(got, approved)
    if dist > FINGERPRINT_MAX_DISTANCE:
        refuse(f"does not match the approved picture: dHash distance {dist} > {FINGERPRINT_MAX_DISTANCE}")
    fingerprint = {"approved_dhash": approved, "downloaded_dhash": got, "hamming": dist}
_probe.close()
jpg.parent.mkdir(parents=True, exist_ok=True)                          # a new Adhyay starts with no folders
shutil.copy2(src, jpg)
im = Image.open(jpg)
try:
    im.save(png)
except Exception:
    jpg.unlink(missing_ok=True)
    png.unlink(missing_ok=True)
    raise
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
rec = {"time": datetime.datetime.now().astimezone().isoformat(), "image_id": iid, "version": ver, "file": str(png), "source_jpg": str(jpg), "pixel_width": im.size[0], "pixel_height": im.size[1],
       "sha256_jpg": sha(jpg), "sha256_png": sha(png), "model_shown": model_arg or os.environ.get("FLOW_MODEL", "unknown (set FLOW_MODEL)"), "final_model": model_arg,
       "credits_shown": os.environ.get("FLOW_CREDITS", "unknown (set FLOW_CREDITS)"), "references_attached": refs.split("|"),
       "prompt_sha256": job.get("prompt_sha256") if job else None, "prompt_source": f"jobs v2: {jobs_file}" if job else "none",
       "chips": job.get("chips") if job else None, "flow_project": "Anime Studio - Kaliya Mardan 6a7ab793-d05f-476d-91a2-aaeb00c234a0", "flow_tile_url_or_id": edit,
       "download": "Flow Download media -> 2K Upscaled (built-in browser saves into Downloads)", "operator": os.environ.get("FLOW_OPERATOR", "claude"),
       "status": "candidate, not accepted", "notes": notes,
       "aspect": aspect, "lineage": lineage, "decided_by": decided_by, "fingerprint": fingerprint}
with open(root / "flow_log.jsonl", "a", encoding="utf-8") as f:
    f.write(json.dumps(rec, ensure_ascii=False) + "\n")
print("filed", iid, ver, im.size, rec["sha256_jpg"][:12])
