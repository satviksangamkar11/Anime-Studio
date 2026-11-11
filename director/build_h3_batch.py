"""Build a Colab batch (director/colab_batches/<batch>/run.py) from an H3 story: FL2VA, route pika6 (the proven Pika H3 Flex 6-step preset),
start/end = the boundary frames, prompt = the linted H3 prompt (h3.compile_h3_sing8). Builds only; nothing is run or spent.
  python build_h3_batch.py STORY.json PACK_DIR BATCH --routes routes.json --lock lock.json [--episode EP1] [--ids SHOT-001,SHOT-002] [--profile 5] [--resolution 768x1344]
PACK_DIR holds keyframes/<SHOT>-A.png and -B.png (the images are embedded relative to it). Run on the GPU with run_colab_batch.py."""
import argparse
import base64
import hashlib
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))

import run_kaggle  # noqa: E402
from h3 import shot_mode  # noqa: E402
from h3.compile_h3_sing8 import compile_fl2va_prompt  # noqa: E402
from timeline_lock_io import load_lock  # noqa: E402


def jpeg_b64(path, size=(768, 1344)):
    """The keyframe at the render size as JPEG q90 (about 0.3 MB instead of 2.7 MB as PNG; the source is a Flow JPEG anyway).
    Wan2GP opens the file by content, so the .png name run_kaggle gives it does no harm. ponytail: monkeypatched into run_kaggle,
    not a run_kaggle option, because only this builder needs it."""
    import base64
    import io

    from PIL import Image
    im = Image.open(path).convert("RGB")
    w, h = im.size
    tw, th = size
    if w * th > h * tw:      # centred crop to the target aspect (864x1536 is 0.5625, 768x1344 is 0.5714), never a stretch
        cw = round(h * tw / th)
        im = im.crop(((w - cw) // 2, 0, (w - cw) // 2 + cw, h))
    elif w * th < h * tw:
        ch = round(w * th / tw)
        im = im.crop((0, (h - ch) // 2, w, (h - ch) // 2 + ch))
    im = im.resize(size, Image.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=90)
    return base64.b64encode(buf.getvalue()).decode("ascii")


def jpg_embedder(root, images, base="/kaggle/working"):
    """run_kaggle.embedder that keeps the .jpg suffix (render pre-flight 2026-11-09: JPEG bytes under a .png name might be picked by
    extension). images maps flat name -> (relative source, base64 JPEG)."""
    def embed(rel):
        flat = Path(rel).with_suffix(".jpg").as_posix().replace("/", "__")
        if flat not in images:
            images[flat] = (rel, run_kaggle.png_b64(Path(root) / rel))
        elif images[flat][0] != rel:
            raise ValueError(f"{rel} and {images[flat][0]} would both be {flat}")
        return f"{base}/Wan2GP/inputs/{flat}"
    return embed


def harden(script):
    """Patches of the on-VM script (review 2026-11-09): a hard timeout on every shell command, and the HF retry on any 429."""
    a = "rc = subprocess.run(cmd, shell=True, stdout=f, stderr=subprocess.STDOUT).returncode"
    b = "rc = run_limited(cmd, f)"
    c = "if \"429 Too Many Requests\" not in lg.read_bytes()[start:].decode(errors=\"replace\") or attempt == 4: break"
    d = "if \"429\" not in lg.read_bytes()[start:].decode(errors=\"replace\") or attempt == 4: break"
    e = "        if any(n.endswith(\".mp4\") for n in files): break"
    f = "        if rc == 0 and any(n.endswith(\".mp4\") for n in files): break"   # a partial clip of a failed attempt must not stop the retries
    if any(script.count(x) != 1 for x in (a, c, e)):
        raise ValueError("run_kaggle RUNNER changed: update build_h3_batch.harden")
    # the whole process group is killed on a timeout (shell=True would kill only the shell and leave wgp.py burning the GPU); 2700 s per command
    helper = ("def run_limited(cmd, f, limit=2700):\n"
              "    p = subprocess.Popen(cmd, shell=True, stdout=f, stderr=subprocess.STDOUT, start_new_session=True)\n"
              "    try: return p.wait(timeout=limit)\n"
              "    except subprocess.TimeoutExpired:\n"
              "        import signal\n"
              "        os.killpg(p.pid, signal.SIGKILL); p.wait(); note(f\"TIMEOUT after {limit}s: {cmd[:80]}\"); return 124\n"
              # render attempt S009-1 (2026-11-09): GitHub answered HTTP 504 for one pip wheel and the whole run died in 5 s; retry the install
              "def sh_retry(cmd, log, tries=4):\n"
              "    for n in range(1, tries + 1):\n"
              "        rc = sh(cmd, log)\n"
              "        if rc == 0 or n == tries: return rc\n"
              # the runner downloads timeline.txt but not setup.log (attempt S009-2 lost the pip error text), so the log tail goes into the timeline
              "        try: note(\"LOG TAIL: \" + open(OUT / log).read()[-700:].replace(\"\\n\", \" | \"))\n"
              "        except Exception: pass\n"
              "        note(f\"RETRY {n}/{tries - 1} after exit {rc}: waiting {30 * n}s\"); time.sleep(30 * n)\n")
    pip_old = "sh(f\"cd {APP} && pip install -r requirements.txt\", \"setup.log\")"
    if script.count(pip_old) != 1:
        raise ValueError("run_kaggle RUNNER changed (pip install line): update build_h3_batch.harden")
    # chumpy comes from a GitHub release that answered HTTP 504 for a whole day (2026-11-09): when the vendored wheel was uploaded, requirements.txt is pointed at it
    pip_new = ("sh_retry(f\"cd {APP} && ( [ ! -f /content/wheels/chumpy-0.71-py3-none-any.whl ] || sed -i 's#^chumpy.*#chumpy @ file:///content/wheels/chumpy-0.71-py3-none-any.whl#' requirements.txt )"
               " && pip install -r requirements.txt\", \"setup.log\")")
    script = script.replace(pip_old, pip_new, 1)
    # the owner's Hugging Face token (written to /content/.hf_token by the runner through stdin, never into a batch file) lifts the 429 limit on model downloads
    hf_old = "os.environ[\"HF_HOME\"] = str(TMP / \"hf\")"
    if script.count(hf_old) != 1:
        raise ValueError("run_kaggle RUNNER changed (HF_HOME line): update build_h3_batch.harden")
    script = script.replace(hf_old, hf_old + "\nif os.path.exists(\"/content/.hf_token\"): os.environ[\"HF_TOKEN\"] = open(\"/content/.hf_token\").read().strip()", 1)
    script = script.replace("def sh(cmd, log=\"shell.log\"):", helper + "def sh(cmd, log=\"shell.log\"):", 1)
    return script.replace(a, b, 1).replace(c, d, 1).replace(e, f, 1)


BLOB_RE = re.compile(r'b64decode\("([A-Za-z0-9+/=]{100000,})"\)')


def split_blobs(script, folder, chunk=3_000_000):
    """Moves every huge base64 literal out of run.py into upload_NN.py files of about `chunk` characters that write /content/_blobK.txt on the VM;
    run.py then reads the file. Reason: `colab exec -f` hangs on this PC for run.py of 11 MB and 20 MB (7 MB worked); run.py becomes ~20 KB."""
    parts = []

    def sub(m):
        path = f"/content/_blob{len(parts)}.txt"
        data = m.group(1)
        parts.append((path, [data[k:k + chunk] for k in range(0, len(data), chunk)]))
        return f'b64decode(open("{path}").read())'
    script = BLOB_RE.sub(sub, script)
    for old in Path(folder).glob("upload_*.py"):
        old.unlink()
    n = 0
    for path, chunks in parts:
        for j, c in enumerate(chunks):
            mode = "w" if j == 0 else "a"
            Path(folder, f"upload_{n:02d}.py").write_text(
                f'c = "{c}"\nopen("{path}", "{mode}").write(c)\nprint("part {n} ok", len(c))\n', encoding="utf-8")
            n += 1
    return script


def legacy_rows(story, episode_id, resolution="768x1344", ids=None, routes=None, lock=None, env=None):
    """(rows, post_ids) for run_kaggle.build: fl2va + pika6, prompt_override = the compiled H3 prompt. routes: the shot_router output
    (a dict with a "routes" map by shot id; required). A POST route is left out and its id returned. The mode and strength come from
    the route; every row passes shot_mode.frame_row. A soft end (input_video_strength other than None or 1.0) is refused: Wan2GP
    bd1ff59 drops it (research/WAN2GP_SOFT_END_TRACE_2026-11-11.md, owner decision D4). lock (optional): the timeline lock; its
    pixel_frames must equal the story's, and its end_frame_position is the SE end position."""
    ep = next((e for e in story["episodes"] if e.get("episode_id", e.get("id")) == episode_id), None)
    if ep is None:
        raise ValueError(f"unknown episode {episode_id!r}; story has {[e.get('episode_id', e.get('id')) for e in story['episodes']]}")
    if routes is None:
        raise ValueError("routes are required: run shot_router.py first and pass its routes file (--routes)")
    route_map = routes.get("routes") if isinstance(routes, dict) else None
    if not isinstance(route_map, dict):
        raise ValueError("routes must be a dict with a 'routes' map by shot id")
    locked = {s.get("id"): s for s in lock.get("shots", [])} if lock is not None else {}
    rows, post_ids = [], []
    for sh in ep["shots"]:
        sid = sh["shot_id"]
        if ids and sid not in ids:
            continue
        if sid not in route_map:
            raise ValueError(f"{sid}: no route in the routes file")
        route = route_map[sid]
        if route.get("route") == "POST":
            post_ids.append(sid)
            continue
        frames = sh["timing_and_lattice"]["pixel_frames"]
        strength = route.get("input_video_strength")
        shot = {"id": sid, "image_prompt_type": route.get("image_prompt_type"), "pixel_frames": frames,
                "start": f"keyframes/{sid}-A.png", "end": f"keyframes/{sid}-B.png", "input_video_strength": strength}
        if lock is not None:
            if sid not in locked:
                raise ValueError(f"{sid}: not in the timeline lock")
            if locked[sid].get("pixel_frames") != frames:
                raise ValueError(f"{sid}: story pixel_frames {frames} differs from the lock's {locked[sid].get('pixel_frames')}")
            if "end_frame_position" in locked[sid]:
                shot["end_frame_position"] = locked[sid]["end_frame_position"]
        frame = shot_mode.frame_row(shot, env)
        if frame.get("input_video_strength") not in (None, 1.0):
            raise ValueError(f"{sid}: route {route.get('route')} needs input_video_strength {frame['input_video_strength']}, "
                             "which Wan2GP bd1ff59 drops (research/WAN2GP_SOFT_END_TRACE_2026-11-11.md); owner decision D4")
        prompt = compile_fl2va_prompt(sh, story["registry"])["compiled_prompt"]
        # Wan2GP (multi_prompts_gen_type PG) reads a BLANK line as a second generation request and refuses (render attempt 5: every
        # shot rc=1); the proven T0 prompts had single line breaks only
        prompt = re.sub(r"\n[ \t]*\n+", "\n", prompt.replace("\r\n", "\n").replace("\r", "\n"))
        if "\n\n" in prompt:
            raise ValueError(f"{sid}: blank line left in the prompt")
        row = {"id": sid, "mode": "fl2va", "route": "pika6", "aspect": "9:16", "resolution": resolution, "render_frames": frame["pixel_frames"],
               "start": shot["start"], "image_prompt_type": frame["image_prompt_type"], "prompt_override": prompt}
        if frame["image_prompt_type"] == "SE":          # S has no end picture
            row["end"] = shot["end"]
        rows.append(row)
    if not rows:
        raise ValueError("no shots selected")
    return rows, post_ids


def _sha(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True).encode("utf-8")).hexdigest()


SETTINGS_RE = re.compile(r'for sid, settings in json\.loads\(base64\.b64decode\("([A-Za-z0-9+/=]+)"\)\)')


def add_settings_sha(manifest, script):
    """settings_sha256 for each manifest shot and for the batch: sha256 of json.dumps(settings, sort_keys=True) of the effective
    Wan2GP settings (the blob in the runner). W-11 checks it before a canary."""
    m = SETTINGS_RE.search(script)
    if not m:
        raise ValueError("settings blob not found in the runner: no settings_sha256 can be written")
    settings = json.loads(base64.b64decode(m.group(1)))
    for sh in manifest.get("shots", []):
        if sh["id"] not in settings:
            raise ValueError(f"{sh['id']}: no settings in the runner")
        sh["settings_sha256"] = _sha(settings[sh["id"]])
    manifest["settings_sha256"] = _sha(settings)


WHEEL = Path("D:/aai work/vendor/chumpy_0.71/chumpy-0.71-py3-none-any.whl")        # supplied by the owner, verified 2026-11-09 (vendor/chumpy_0.71/VENDOR.md)
WHEEL_SHA256 = "ab6c59c799e2a1011a36f4e080309383c0631354c881689affa4a89b7f9d7925"


def write_wheel_upload(folder, wheel=WHEEL, sha=WHEEL_SHA256):
    """upload_wheel.py: writes the vendored chumpy wheel to /content/wheels on the VM (the runner uploads every upload_*.py before run.py).
    Refuses a wheel whose sha256 is not the verified one."""
    import base64
    import hashlib
    data = Path(wheel).read_bytes()
    if hashlib.sha256(data).hexdigest() != sha:
        raise ValueError(f"{wheel} is not the verified chumpy wheel (sha256 differs)")
    code = ("import base64, pathlib\n"
            "d = pathlib.Path('/content/wheels'); d.mkdir(parents=True, exist_ok=True)\n"
            f"(d / '{Path(wheel).name}').write_bytes(base64.b64decode('{base64.b64encode(data).decode()}'))\n"
            f"print('wheel ok', (d / '{Path(wheel).name}').stat().st_size)\n")
    (Path(folder) / "upload_wheel.py").write_text(code, encoding="utf-8")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("story"); ap.add_argument("pack"); ap.add_argument("batch")
    ap.add_argument("--episode", default="EP1"); ap.add_argument("--ids", default="")
    ap.add_argument("--profile", type=int, default=5); ap.add_argument("--resolution", default="768x1344")
    ap.add_argument("--routes", required=True, help="routes.json from shot_router.py --out (its lock_sha256 must match --lock)")
    ap.add_argument("--lock", required=True, help="the timeline lock the routes were made from")
    a = ap.parse_args(argv)
    story = json.loads(Path(a.story).read_text(encoding="utf-8"))
    routes = json.loads(Path(a.routes).read_text(encoding="utf-8"))
    lock = load_lock(a.lock)
    if not isinstance(routes, dict):
        raise ValueError("routes must be a JSON object with a 'routes' map")
    if routes.get("lock_sha256") != lock.get("input_sha256"):
        raise ValueError("stale routes: the routes file was made from another lock; rerun shot_router.py")
    rows, post_ids = legacy_rows(story, a.episode, a.resolution, set(filter(None, a.ids.split(","))), routes=routes, lock=lock)
    if post_ids:
        print("POST (no render, not in the batch):", ", ".join(post_ids))
    manifest = {}
    w, h = (int(v) for v in a.resolution.split("x"))
    run_kaggle.png_b64 = lambda path: jpeg_b64(path, (w, h))
    run_kaggle.embedder = jpg_embedder
    script, _ = run_kaggle.build(rows, a.pack, a.batch, None, None, False, "colab", a.profile, manifest)
    add_settings_sha(manifest, script)
    folder = HERE / "colab_batches" / a.batch
    folder.mkdir(parents=True, exist_ok=True)
    script = split_blobs(harden(script), folder)
    (folder / "run.py").write_text(script, encoding="utf-8")
    write_wheel_upload(folder)
    (folder / "render_manifest.json").write_text(json.dumps(manifest, indent=1, ensure_ascii=False), encoding="utf-8")
    print("built", folder, "|", len(rows), "shots,", sum(r["render_frames"] for r in rows), "frames,", manifest["embed_mb_total"], "MB embedded")
    return 0


if __name__ == "__main__":
    sys.exit(main())
