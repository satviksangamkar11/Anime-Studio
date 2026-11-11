"""Clip QA for one shot (X-14): frame features, clip_gates verdict inside the lock window, clip_qa.json.

Frames come from the timeline lock trim window only. Verdicts come from clip_gates.verdict.
The owner can accept a failed verdict with `accept`; clip_ok then unblocks the clip.
"""
import argparse
import datetime
import hashlib
import json
import os
import subprocess
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

import blocking  # noqa: E402
import clip_gates  # noqa: E402
import image_gates  # noqa: E402
import timeline_lock_io  # noqa: E402
from score import sfx_study  # noqa: E402

FLICKER_LIMIT = 0.1  # placeholder limit (same value as the tests); no calibrated number in the card
HIT_WINDOW = (-0.05, 0.25)  # same span find_hits uses around an onset
# The card's CLI code is NEW_OBJECT; clip_gates calls the same reason NEW_CLASS.
ACCEPT_CODES = set(clip_gates.CLIP_CODES) | {"NEW_OBJECT"}
ALIASES = {"NEW_OBJECT": "NEW_CLASS"}  # the card's code for the same reason clip_gates calls NEW_CLASS
# CRITICAL failures: the clip is not the picture the shot asked for. No owner accept can clear them.
CRITICAL_CODES = frozenset({"FRAME_COUNT", "CORRUPT"})


class ClipQAError(ValueError):
    pass


def extract(clip, trim_in, trim_out, size=(192, 336), run=subprocess.run):
    """Grey frames [trim_in, trim_out) as float32 0..1, shape (F, H, W). Count must equal trim_out - trim_in."""
    w, h = size
    if not (0 <= trim_in < trim_out):
        raise ClipQAError("bad trim window: " + str((trim_in, trim_out)))
    vf = "select='between(n\\," + str(trim_in) + "\\," + str(trim_out - 1) + ")',scale=" + str(w) + ":" + str(h)
    vf += ",format=gray"
    cmd = ["ffmpeg", "-v", "error", "-i", str(clip), "-vf", vf, "-vsync", "0",
           "-f", "rawvideo", "-pix_fmt", "gray", "-"]
    try:
        raw = run(cmd, check=True, capture_output=True).stdout
    except subprocess.CalledProcessError as exc:
        raise ClipQAError("ffmpeg failed: " + str(exc.stderr)[:200])
    if len(raw) % (w * h):
        raise ClipQAError("ffmpeg output is not whole frames")
    frames = np.frombuffer(raw, dtype=np.uint8).reshape(-1, h, w).astype(np.float32) / 255.0
    want = trim_out - trim_in
    if frames.shape[0] != want:
        raise ClipQAError("frame count " + str(frames.shape[0]) + " != trim_out - trim_in " + str(want))
    return frames


def _rgb8(gray):
    # image_gates.block_ssim only takes uint8 (H, W, 3)
    g = np.clip(np.rint(np.asarray(gray, dtype=float) * 255.0), 0, 255).astype(np.uint8)
    return np.repeat(g[:, :, None], 3, axis=2)


def features(frames, key_a, key_b):
    """Flow, similarity to keyframe A per frame, end metrics against keyframe B, and flicker."""
    frames = np.asarray(frames, dtype=np.float32)
    h, w = frames.shape[1], frames.shape[2]
    valid = np.ones((h, w), dtype=bool)
    flow_p95 = np.percentile(np.abs(np.diff(frames, axis=0)).reshape(len(frames) - 1, -1), 95, axis=1)
    a_rgb = _rgb8(key_a)
    sim_to_a = [image_gates.block_ssim(_rgb8(f), a_rgb, valid) for f in frames]
    end_ssim = image_gates.block_ssim(_rgb8(frames[-1]), _rgb8(key_b), valid)
    x = frames[-1].ravel().astype(float)
    y = np.asarray(key_b, dtype=float).ravel()
    denom = float(np.linalg.norm(x) * np.linalg.norm(y))
    cosine = min(1.0, max(-1.0, float(x @ y / denom))) if denom > 0 else 0.0  # float noise can pass 1.0
    flicker = clip_gates.flicker_score([f for f in frames[::2]])
    return {
        "flow_p95": flow_p95.tolist(),
        "sim_to_a": sim_to_a,
        "end": {"ssim": end_ssim, "lpips": 0.0, "cosine": cosine, "lpips_note": "lpips not measured"},
        # ponytail: lpips not measured, the record says so
        "flicker": flicker,
    }


def new_classes(review_path, sheet):
    """Classes the reviewer counted in any sampled frame that the shot sheet does not know."""
    if isinstance(sheet, (str, os.PathLike)):
        with open(sheet, encoding="utf-8") as fh:
            sheet = json.load(fh)
    with open(review_path, encoding="utf-8") as fh:
        review = json.load(fh)
    if not isinstance(review, dict):
        raise ClipQAError("clip_review must be an object of frame -> class counts")
    known = blocking.known_classes(sheet)
    seen = set()
    for frame, counts in review.items():
        if not isinstance(counts, dict):
            raise ClipQAError("clip_review frame " + str(frame) + " is not a class-count object")
        for name, count in counts.items():
            if isinstance(count, bool) or not isinstance(count, (int, float)):
                raise ClipQAError("clip_review count for " + str(name) + " is not a number")
            if count > 0:
                seen.add(name)
    return sorted(seen - known)


def audio_analysis(audio_path, sheet, sr=48000):
    """Returns (sfx_keep, bed_db): expected SFX hits as (t0, t1) and the level of the audio outside them."""
    x = sfx_study.decode_audio(audio_path, sr)
    if len(x) == 0:
        raise ClipQAError("no audio samples")
    hits = sfx_study.find_hits(x, sr)
    cues = [{"key": c.get("name"), "start": c.get("start", c.get("t")), "end": c.get("end", c.get("t"))}
            for c in sheet.get("sound_cues", [])]
    matched, _ = sfx_study.match_cues(hits, cues)
    sfx_keep = [(round(h["t"] + HIT_WINDOW[0], 3), round(h["t"] + HIT_WINDOW[1], 3)) for h in matched if h["expected"]]
    mask = np.zeros(len(x), dtype=bool)
    for h in hits:
        mask[max(0, int((h["t"] + HIT_WINDOW[0]) * sr)):int((h["t"] + HIT_WINDOW[1]) * sr)] = True
    bed = x[~mask] if (~mask).any() else x
    return sfx_keep, float(sfx_study.level_db(bed))


def _sha256(path):
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def _qa_path(root, shot):
    return os.path.join(root, "results", shot, "clip_qa.json")


def _verified_lock(lock_path):
    """The lock, verified against its own recorded inputs and params first. Stale or missing is refused."""
    try:
        recorded = timeline_lock_io.load_lock(lock_path)
        return timeline_lock_io.verify_lock(lock_path, recorded["inputs"], recorded["params"])
    except (FileNotFoundError, timeline_lock_io.StaleLockError) as exc:
        raise ClipQAError(str(exc)) from exc


def _canon(code):
    return ALIASES.get(str(code), str(code))


def _records(doc):
    """owner_accept as a list of {code, note, by, at} records. Reads the old single-dict form and None too."""
    acc = doc.get("owner_accept")
    if acc is None:
        return []
    return [acc] if isinstance(acc, dict) else list(acc)


def _uncleared(codes, records):
    """Failures no owner record clears. A record clears only a failure with its own code (NEW_OBJECT is NEW_CLASS)."""
    crit = [c for c in codes if c in CRITICAL_CODES]
    if crit:
        return ["verdict failed on critical code, no owner accept can clear it: " + ", ".join(crit)]
    accepted = {_canon(r.get("code")) for r in records}
    rest = [c for c in codes if _canon(c) not in accepted]
    return ["verdict failed, not cleared by owner accept: " + ", ".join(rest)] if rest else []


def qa_shot(shot, clip, lock_path, key_a, key_b, review_path, sheet, audio_path, root):
    """Run every check for one shot inside its lock trim window and write results/<shot>/clip_qa.json."""
    rows = {r["id"]: r for r in timeline_lock_io.lock_rows(_verified_lock(lock_path))}
    if shot not in rows:
        raise ClipQAError("shot not in timeline lock: " + shot)
    ti, to = rows[shot]["trim_in_frame"], rows[shot]["trim_out_frame"]
    feats = features(extract(clip, ti, to), key_a, key_b)
    tail = clip_gates.tail_spike(np.asarray(feats["flow_p95"]))
    cuts = clip_gates.scene_cut(feats["sim_to_a"])
    end = clip_gates.end_frame_pass(feats["end"]["ssim"], feats["end"]["lpips"], feats["end"]["cosine"])
    new = new_classes(review_path, sheet)
    results = {"tail": tail, "end": end, "cuts": cuts, "new_classes": new,
               "flicker": feats["flicker"], "flicker_limit": FLICKER_LIMIT}
    verdict = clip_gates.verdict(results)
    sfx_keep, bed_db = audio_analysis(audio_path, sheet)
    doc = {"clip_sha256": _sha256(clip), "window": [ti, to], "results": results,
           "verdict": verdict, "sfx_keep": sfx_keep, "bed_db": bed_db, "owner_accept": None}
    out = _qa_path(root, shot)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=2)
    return doc


def clip_ok(qa_path, clip):
    """Problems that block the clip: sha mismatch, or a failed verdict with no owner accept."""
    with open(qa_path, encoding="utf-8") as fh:
        doc = json.load(fh)
    problems = []
    actual = _sha256(clip)
    if doc.get("clip_sha256") != actual:
        problems.append("clip sha256 mismatch: qa has " + str(doc.get("clip_sha256")) + ", clip is " + actual)
    verdict = doc.get("verdict")
    if not isinstance(verdict, dict):
        problems.append("verdict missing")
    elif verdict.get("pass") is not True:
        codes = [str(r.get("code")) for r in verdict.get("reasons", [])] or ["no pass recorded"]
        records = _records(doc)
        if not records:
            problems.append("verdict failed without owner accept: " + ", ".join(codes))
        else:
            problems.extend(_uncleared(codes, records))
    return problems


def accept(shot, code, note, root):
    """Append the owner's accept for one code to a shot's clip_qa.json owner_accept list. The code is stored as given.
    The same code accepted twice is a no-op that returns the existing record."""
    if code not in ACCEPT_CODES:
        raise ClipQAError("unknown accept code: " + str(code))
    if code in CRITICAL_CODES:
        raise ClipQAError("critical code cannot be accepted: " + str(code))
    if not str(note).strip():
        raise ClipQAError("accept note must not be empty")
    path = _qa_path(root, shot)
    with open(path, encoding="utf-8") as fh:
        doc = json.load(fh)
    # clip_ok matches the accepted code against the failed reasons; accept itself does not.
    records = _records(doc)
    for rec in records:
        if rec.get("code") == code:
            return rec
    rec = {"code": code, "note": str(note), "by": "owner", "date": datetime.datetime.now().isoformat(timespec="seconds")}
    doc["owner_accept"] = records + [rec]
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=2)
    return rec


def main(argv=None):
    parser = argparse.ArgumentParser(description="Clip QA owner accept (X-14).")
    sub = parser.add_subparsers(dest="cmd", required=True)
    acc = sub.add_parser("accept", help="record an owner accept on a shot")
    acc.add_argument("--shot", required=True)
    acc.add_argument("--code", required=True)
    acc.add_argument("--note", required=True)
    acc.add_argument("--root", default=".", help="folder that holds results/<SHOT>/clip_qa.json")
    args = parser.parse_args(argv)
    if args.cmd == "accept":
        print(json.dumps(accept(args.shot, args.code, args.note, args.root)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
