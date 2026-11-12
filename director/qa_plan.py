"""QA plan builder + clip review producer (M-29). Feeds post_fetch_qa / run_colab_batch --qa-plan.

  python qa_plan.py --lock L.json --pack PACK --results RES --keyframes KEYS
      --audio-dir AUDIO --out-dir OUT --shots SHOT-001,...

Per shot it needs: RES/<shot>/*.mp4, KEYS/<shot>-A.png and -B.png, PACK/<shot>.json (blocking sheet),
AUDIO/<shot>.wav.
The clip review (what clip_qa.new_classes reads) is {"<absolute frame>": {"<class>": count}} for a few frames of
the lock trim window. A free NVIDIA vision model (keys NVIDIA_API_KEY_01..14, tools/key_pool.py) counts the classes;
with no key a deterministic STUB answers with exactly what the sheet knows. A stub proves the plumbing only and is
recorded as "review_source": "stub" in the plan. No Claude and no paid call."""
import argparse
import base64
import io
import json
import os
import re
import sys
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "tools"))

import blocking  # noqa: E402
import clip_qa  # noqa: E402
import timeline_lock_io  # noqa: E402

NVIDIA_URL = "https://integrate.api.nvidia.com/v1/chat/completions"
NVIDIA_MODEL = "nvidia/llama-3.1-nemotron-nano-vl-8b-v1"       # free tier vision model
SAMPLES = 4


class RateLimited(Exception):
    pass


def sample_frames(ti, to, n=SAMPLES):
    """n absolute frame numbers spread evenly over [ti, to); every frame once when the window is shorter than n."""
    span = to - ti
    return list(range(ti, to)) if span <= n else [ti + span * i // n for i in range(n)]


def parse_counts(text):
    """{class: count} from a model reply (think block and code fence tolerated)."""
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.S)
    m = re.search(r"\{.*\}", text, flags=re.S)
    if not m:
        raise ValueError("model reply has no JSON object")
    return json.loads(m.group(0))


def _check_counts(counts):
    if not isinstance(counts, dict):
        raise ValueError("review answer is not a class-count object")
    for name, c in counts.items():
        if isinstance(c, bool) or not isinstance(c, (int, float)) or c < 0:
            raise ValueError(f"review count for {name!r} is not a number >= 0")
    return counts


def stub_ask(sheet):
    """Deterministic stand-in: counts exactly the classes the sheet knows (person = cast size, each prop once)."""
    counts = {}
    if sheet.get("cast"):
        counts["person"] = len(sheet["cast"])
    for p in sheet.get("props", []):
        counts[p.get("class")] = counts.get(p.get("class"), 0) + 1
    return lambda jpeg: dict(counts)


def _nvidia_post(url, key, body):
    headers = {"Authorization": "Bearer " + key, "Content-Type": "application/json"}
    req = urllib.request.Request(url, json.dumps(body).encode(), headers)
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return json.loads(r.read())["choices"][0]["message"]["content"]
    except urllib.error.HTTPError as e:
        if e.code == 429:
            raise RateLimited() from e
        raise


def nvidia_ask(keys, pool, post=_nvidia_post, model=NVIDIA_MODEL, classes=("person",), tries=6):
    """ask(jpeg_bytes) -> counts, via the shared key pool (<=9 calls/key/min); a 429 cools that key for 60 s."""
    prompt = ("Count the objects visible in this picture by class. Reply with one JSON object only, class name to "
              "count, e.g. {\"person\": 1}. Use \"person\" for every human. Known classes: "
              + ", ".join(sorted(classes)) + ".")

    def ask(jpeg):
        url = "data:image/jpeg;base64," + base64.b64encode(jpeg).decode()
        parts = [{"type": "text", "text": prompt}, {"type": "image_url", "image_url": {"url": url}}]
        body = {"model": model, "max_tokens": 200, "temperature": 0, "messages": [{"role": "user", "content": parts}]}
        for _ in range(tries):
            idx = pool.acquire()
            try:
                return parse_counts(post(NVIDIA_URL, keys[idx % len(keys)], body))
            except RateLimited:
                pool.cooldown(idx, 60)
        raise ValueError("NVIDIA review: rate limited on every try")
    return ask


def pick_ask(sheet):
    """(ask, source): the NVIDIA model when keys exist, else the stub."""
    keys = [os.environ.get("NVIDIA_API_KEY_%02d" % i, "").strip() for i in range(1, 15)]
    keys = [k for k in keys if k]
    if not keys:
        return stub_ask(sheet), "stub"
    import key_pool
    pool = key_pool.KeyPool(Path(tempfile.gettempdir()) / "nvidia_key_pool.json", nkeys=len(keys))
    classes = blocking.known_classes(sheet) | {"person"}
    return nvidia_ask(keys, pool, classes=classes), "nvidia:" + NVIDIA_MODEL


def stub_identity_ask(frame, master):
    """Deterministic stand-in (no key): same character when the colour histograms correlate (>= HIST_FAIL).
    Proves the plumbing only; the owner eye stays mandatory on the first S clip."""
    c = clip_qa._hist_corr(clip_qa.hsv_hist(frame), clip_qa.hsv_hist(master))
    return {"same": c >= clip_qa.HIST_FAIL, "reason": "stub: histogram corr " + str(round(c, 3))}


def _jpeg(rgb):
    from PIL import Image
    buf = io.BytesIO()
    Image.fromarray(rgb).save(buf, "JPEG", quality=85)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


def nvidia_identity_ask(keys, pool, post=_nvidia_post, model=NVIDIA_MODEL, tries=6):
    """ask(frame_rgb, master_rgb) -> {"same", "reason"} from a free NVIDIA vision model (same pool and 429 rules)."""
    prompt = ("Picture 1 is the reference character, picture 2 is a video frame. Is the main character in picture 2 "
              "the same character as in picture 1 (face, hair, clothes)? Reply with one JSON object only: "
              "{\"same\": true or false, \"reason\": \"short\"}.")

    def ask(frame, master):
        parts = [{"type": "text", "text": prompt}, {"type": "image_url", "image_url": {"url": _jpeg(master)}},
                 {"type": "image_url", "image_url": {"url": _jpeg(frame)}}]
        body = {"model": model, "max_tokens": 200, "temperature": 0, "messages": [{"role": "user", "content": parts}]}
        for _ in range(tries):
            idx = pool.acquire()
            try:
                ans = parse_counts(post(NVIDIA_URL, keys[idx % len(keys)], body))
                return {"same": ans["same"] is True, "reason": str(ans.get("reason", ""))}
            except RateLimited:
                pool.cooldown(idx, 60)
        raise ValueError("NVIDIA identity review: rate limited on every try")
    return ask


def pick_identity_ask():
    """(ask, source): the NVIDIA model when keys exist, else the deterministic stub."""
    keys = [os.environ.get("NVIDIA_API_KEY_%02d" % i, "").strip() for i in range(1, 15)]
    keys = [k for k in keys if k]
    if not keys:
        return stub_identity_ask, "stub"
    import key_pool
    pool = key_pool.KeyPool(Path(tempfile.gettempdir()) / "nvidia_key_pool.json", nkeys=len(keys))
    return nvidia_identity_ask(keys, pool), "nvidia:" + NVIDIA_MODEL


def add_identity(plan, master):
    """Record the identity master PNG on every shot of a plan dict (post_fetch_qa passes it to route S clips)."""
    if not Path(master).is_file():
        raise ValueError(f"identity master missing: {master}")
    for e in plan["shots"].values():
        e["identity"] = str(master)
    return plan


def _load_frames(clip, ti, to, idx):
    from PIL import Image
    rgb = clip_qa.extract_rgb(clip, ti, to)
    out = []
    for i in idx:
        buf = io.BytesIO()
        Image.fromarray(rgb[i - ti]).save(buf, "JPEG", quality=85)
        out.append(buf.getvalue())
    return out


def produce_review(sheet, clip, ti, to, ask, load_frames=_load_frames, n=SAMPLES):
    """The clip review clip_qa reads: {absolute frame: {class: count}} for n sampled frames."""
    idx = sample_frames(ti, to, n)
    return {str(i): _check_counts(ask(jpeg)) for i, jpeg in zip(idx, load_frames(clip, ti, to, idx))}


def build_plan(lock, pack, results, keyframes, audio_dir, out_dir, shot_ids, trim=None, review=None,
               review_source=None, identity=None):
    """Write OUT/qa_plan.json (+ OUT/<shot>_review.json); returns the plan path. Every input is checked first."""
    pack, results, keyframes, audio_dir, out_dir = (Path(p) for p in (pack, results, keyframes, audio_dir, out_dir))
    shots, problems = {}, []
    for sid in shot_ids:
        clips = sorted((results / sid).glob("*.mp4"))
        want = {"key_a": keyframes / f"{sid}-A.png", "key_b": keyframes / f"{sid}-B.png",
                "sheet": pack / f"{sid}.json", "audio": audio_dir / f"{sid}.wav"}
        if not clips:
            problems.append(f"{sid}: clip missing in {results / sid}")
        problems += [f"{sid}: {k} missing: {p}" for k, p in want.items() if not p.is_file()]
        if clips:
            shots[sid] = {"clip": f"{sid}/{clips[0].name}", **{k: str(p) for k, p in want.items()}}
    if problems:
        raise ValueError("; ".join(problems))
    if trim is None:
        rows = {r["id"]: r for r in timeline_lock_io.lock_rows(clip_qa._verified_lock(lock))}
        trim = lambda sid: (rows[sid]["trim_in_frame"], rows[sid]["trim_out_frame"])      # noqa: E731
    out_dir.mkdir(parents=True, exist_ok=True)
    source = review_source or ("given" if review else None)
    for sid, e in shots.items():
        sheet = json.loads(Path(e["sheet"]).read_text(encoding="utf-8"))
        ti, to = trim(sid)
        clip = str(results / e["clip"])
        if review is None:
            ask, src = pick_ask(sheet)
            source = source or src
            doc = produce_review(sheet, clip, ti, to, ask)
        else:
            doc = review(sid, sheet, clip, ti, to)
        rp = out_dir / f"{sid}_review.json"
        rp.write_text(json.dumps(doc, indent=1), encoding="utf-8")
        e["review"] = str(rp)
    plan = {"lock": str(lock), "root": str(out_dir), "review_source": source, "shots": shots}
    if identity is not None:
        add_identity(plan, identity)
    path = out_dir / "qa_plan.json"
    path.write_text(json.dumps(plan, indent=1), encoding="utf-8")
    return path


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    for k in ("lock", "pack", "results", "keyframes", "audio-dir", "out-dir", "shots"):
        ap.add_argument("--" + k, required=True)
    ap.add_argument("--identity", default=None, help="identity master PNG; route S clips are checked against it")
    a = ap.parse_args(argv)
    ids = [s for s in a.shots.split(",") if s]
    path = build_plan(a.lock, a.pack, a.results, a.keyframes, a.audio_dir, a.out_dir, ids, identity=a.identity)
    print("qa plan:", path, "| review source:", json.loads(path.read_text(encoding="utf-8"))["review_source"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
