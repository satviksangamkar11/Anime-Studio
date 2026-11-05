"""Files a Flow 2K download (from Downloads) into the Anime Studio (Kaliya Mardan) structure and logs it. ANIME copy of the Granth filer.
usage: file_flow_download.py <download path> <IMAGE_ID> <vNN> <flow edit id> <references joined by |> <notes> [sub] [v2 jobs file] [model shown on screen]
Root: env FLOW_OUT_ROOT (default D:/aai work/flow_outputs/anime_kaliya), then adhyay_NN.
Adhyay: env FLOW_ADHYAY (default 1). With a v2 jobs file the logged prompt_sha256 is the ACTUAL prompt of that job (not the catalog prompt);
the model is the one read off the screen (arg) - else env FLOW_MODEL - else "unknown". Operator: env FLOW_OPERATOR (default claude).
2K check: 2752x1536 (16:9 sheets and plates) or 1536x2752 (9:16 keyframes)."""
import datetime
import os
import hashlib
import json
import shutil
import struct
import sys
from pathlib import Path

from PIL import Image

src, iid, ver, edit, refs, notes = sys.argv[1:7]
sub = sys.argv[7] if len(sys.argv) > 7 else "references"
jobs_file = sys.argv[8] if len(sys.argv) > 8 and sys.argv[8] else None
model_arg = sys.argv[9] if len(sys.argv) > 9 and sys.argv[9] else None
root = Path(os.environ.get("FLOW_OUT_ROOT", "D:/aai work/flow_outputs/anime_kaliya")) / f"adhyay_{int(os.environ.get('FLOW_ADHYAY', '1')):02d}"
job = None
if jobs_file:
    job = next((j for j in json.loads(Path(jobs_file).read_text(encoding="utf-8")) if j["shot_id"] == iid), None)
    assert job is not None, f"{iid} is not in {jobs_file}"
d = Path(src).read_bytes()
assert d[:2] == b"\xff\xd8" and d[-2:] == b"\xff\xd9", "not a complete JPEG"
jpg, png = root / sub / f"{iid}__candidate_{ver}__2K_source.jpg", root / sub / f"{iid}__candidate_{ver}.png"
assert not jpg.exists() and not png.exists(), "refusing to overwrite"
new_sha = hashlib.sha256(d).hexdigest()
for old in root.rglob("*__2K_source.jpg"):
    assert hashlib.sha256(old.read_bytes()).hexdigest() != new_sha, f"this file is identical to {old.name}: the new download has not arrived yet"
import time
_max_age = int(os.environ.get("FLOW_MAX_AGE_S", "300"))                # the download pass matches by exact title, so it may file older saves
assert time.time() - Path(src).stat().st_mtime < _max_age, f"the download is older than {_max_age} s: it is not the download you just made"
_probe = Image.open(src)
assert _probe.size in ((2752, 1536), (1536, 2752)), f"not 2K 16:9 or 9:16: {_probe.size}"   # validate BEFORE copying: no partial filing
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
cat = {x["image_id"]: x for x in json.loads(Path("D:/aai work/granthstudio/canon/drafts/A1_image_catalog_v2_DRAFT.json").read_text(encoding="utf-8"))}
rec = {"time": datetime.datetime.now().astimezone().isoformat(), "image_id": iid, "version": ver, "file": str(png), "source_jpg": str(jpg), "pixel_width": im.size[0], "pixel_height": im.size[1],
       "sha256_jpg": sha(jpg), "sha256_png": sha(png), "model_shown": model_arg or os.environ.get("FLOW_MODEL", "unknown (set FLOW_MODEL)"), "credits_shown": os.environ.get("FLOW_CREDITS", "unknown (set FLOW_CREDITS)"), "references_attached": refs.split("|"),
       "prompt_sha256": job["prompt_sha256"] if job else (hashlib.sha256(cat[iid]["prompt"].encode()).hexdigest() if iid in cat else None),
       "prompt_source": f"jobs v2: {jobs_file}" if job else "catalog (NOT the prompt actually sent)", "chips": job["chips"] if job else None, "flow_project": "Anime Studio - Kaliya Mardan 6a7ab793-d05f-476d-91a2-aaeb00c234a0", "flow_tile_url_or_id": edit,
       "download": "Flow Download media -> 2K Upscaled (built-in browser saves into Downloads)", "operator": os.environ.get("FLOW_OPERATOR", "claude"), "status": "candidate, not accepted", "notes": notes}
with open(root / "flow_log.jsonl", "a", encoding="utf-8") as f:
    f.write(json.dumps(rec, ensure_ascii=False) + "\n")
print("filed", iid, ver, im.size, rec["sha256_jpg"][:12])
