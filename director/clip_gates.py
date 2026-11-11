import math
import re
import datetime

import numpy as np


class ClipGateError(ValueError):
    pass


def tail_spike(flow_p95, window=None, tail_frames=30, ratio=2.2, head_skip=10):
    # window = (trim_in, trim_out) from the timeline lock; trim_out is exclusive.
    # Only flow_p95[trim_in:trim_out] is analysed; first_spike_index is a clip-frame number.
    offset = 0
    if window is not None:
        trim_in, trim_out = window
        if not (0 <= trim_in < trim_out <= len(flow_p95)):
            raise ClipGateError("window outside the clip")
        offset = trim_in
        flow_p95 = flow_p95[trim_in:trim_out]
    n = len(flow_p95)
    if n < tail_frames + head_skip + 5:
        raise ClipGateError("flow_p95 too short")
    if not np.all(np.isfinite(np.asarray(flow_p95, dtype=float))):
        raise ClipGateError("flow_p95 has non-finite values")
    median_window = flow_p95[head_skip:n - tail_frames]
    median = float(np.median(median_window))
    if median == 0.0:
        raise ClipGateError("median flow is zero")
    tail = flow_p95[n - tail_frames:n]
    tail_max = max(tail)
    first_spike_index = None
    for i in range(n - tail_frames, n):
        if flow_p95[i] > ratio * median:
            first_spike_index = offset + i
            break
    flag = first_spike_index is not None
    return {
        "flag": flag,
        "ratio": tail_max / median,
        "first_spike_index": first_spike_index,
        "median": median,
    }


def suggest_trim_out(first_spike_index, back=4, minimum=1):
    if first_spike_index is None:
        raise ClipGateError("first_spike_index is None")
    return max(minimum, first_spike_index - back)


def best_cut_frame(similarities, first_index):
    if len(similarities) == 0:
        raise ClipGateError("similarities is empty")
    for v in similarities:
        if not math.isfinite(v):
            raise ClipGateError("similarities has non-finite values")
    best_rel = 0
    best_val = similarities[0]
    for i in range(1, len(similarities)):
        if similarities[i] > best_val:
            best_val = similarities[i]
            best_rel = i
    return first_index + best_rel


def end_frame_pass(ssim, lpips, cosine, min_ssim=0.82, max_lpips=0.18, min_cosine=0.88):
    if not (-1.0 <= ssim <= 1.0):
        raise ClipGateError("ssim out of range")
    if not (-1.0 <= cosine <= 1.0):
        raise ClipGateError("cosine out of range")
    if not (lpips >= 0.0):
        raise ClipGateError("lpips out of range")
    failed = []
    if ssim < min_ssim:
        failed.append("ssim")
    if lpips > max_lpips:
        failed.append("lpips")
    if cosine < min_cosine:
        failed.append("cosine")
    return {"pass": len(failed) == 0, "failed": failed}


def scene_cut(similarities_to_a, min_sim=0.75, start_index=1):
    result = []
    start = max(1, start_index)
    for i in range(start, len(similarities_to_a)):
        if not math.isfinite(similarities_to_a[i]):
            raise ClipGateError("similarity is non-finite")
        if similarities_to_a[i] < min_sim:
            result.append(i)
    return result


def new_object_classes(counts_by_frame, after_frame=12, known=()):
    if isinstance(after_frame, bool) or not isinstance(after_frame, int) or after_frame < 0:
        raise ClipGateError("after_frame must be an int >= 0")
    known = set(known)
    for i in range(0, min(after_frame, len(counts_by_frame))):
        for name, count in counts_by_frame[i].items():
            if count > 0:
                known.add(name)
    new = set()
    for i in range(after_frame, len(counts_by_frame)):
        for name, count in counts_by_frame[i].items():
            if count > 0 and name not in known:
                new.add(name)
    return sorted(new)


def flicker_score(luma_frames, mask=None):
    if len(luma_frames) < 3:
        raise ClipGateError("need at least 3 frames")
    shape = luma_frames[0].shape
    if len(shape) != 2:
        raise ClipGateError("luma_frames must be 2-D arrays")
    for i in range(1, len(luma_frames)):
        if luma_frames[i].shape != shape:
            raise ClipGateError("luma_frames must all have the same shape")
    if mask is None:
        mask = np.zeros(shape, dtype=bool)
    else:
        if mask.shape != shape:
            raise ClipGateError("mask shape must match luma_frames shape")
    for f in luma_frames:
        if not np.all(np.isfinite(f)):
            raise ClipGateError("luma_frames contain non-finite values")
    stack = np.stack([np.asarray(f, dtype=float) for f in luma_frames])
    second = np.abs(stack[2:] - 2.0 * stack[1:-1] + stack[:-2])
    keep = ~np.asarray(mask, dtype=bool)
    kept = int(np.count_nonzero(keep))
    if kept == 0:
        raise ClipGateError("all pixels masked")
    return float(second[:, keep].sum()) / ((len(luma_frames) - 2) * kept)


VERDICT_KEYS = ("tail", "end", "cuts", "new_classes", "flicker", "flicker_limit")
CLIP_CODES = ("TAIL_SNAP", "END_MISMATCH", "SCENE_CUT", "NEW_CLASS", "FLICKER")


def verdict(results, owner_accept=()):
    missing = [k for k in VERDICT_KEYS if k not in results]
    if missing:
        raise ClipGateError("verdict missing keys: " + ", ".join(missing))
    reasons = []
    tail = results["tail"]
    if not isinstance(tail.get("flag"), bool):
        raise ClipGateError("tail['flag'] must be a bool")
    if tail["flag"]:
        reasons.append({"code": "TAIL_SNAP", "text": "tail snap at frame " + str(tail.get("first_spike_index"))})
    end = results["end"]
    if not isinstance(end.get("pass"), bool):
        raise ClipGateError("end['pass'] must be a bool")
    if not end["pass"]:
        failed = ", ".join(end.get("failed", []))
        reasons.append({"code": "END_MISMATCH", "text": "end frame differs from keyframe B (failed: " + failed + ")"})
    if len(results["cuts"]) > 0:
        reasons.append({"code": "SCENE_CUT", "text": "scene cut at samples " + str(results["cuts"])})
    if len(results["new_classes"]) > 0:
        reasons.append({"code": "NEW_CLASS", "text": "new objects appear: " + str(results["new_classes"])})
    flicker = results["flicker"]
    limit = results["flicker_limit"]
    if (isinstance(flicker, bool) or isinstance(limit, bool)
            or not isinstance(flicker, (int, float)) or not isinstance(limit, (int, float))
            or not math.isfinite(flicker) or not math.isfinite(limit)):
        raise ClipGateError("flicker and flicker_limit must be finite numbers")
    if flicker > limit:
        reasons.append({"code": "FLICKER", "text": "flicker score " + str(flicker) + " above limit " + str(limit)})
    for entry in owner_accept:
        if not isinstance(entry, dict) or set(entry) != {"code", "date", "note"}:
            raise ClipGateError("owner_accept entry must be {code, date, note}")
        if entry["code"] not in CLIP_CODES:
            raise ClipGateError("owner_accept unknown code: " + str(entry["code"]))
        if not str(entry["date"]).strip() or not str(entry["note"]).strip():
            raise ClipGateError("owner_accept date and note must be non-empty")
        if not isinstance(entry["date"], str) or not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", entry["date"]):
            raise ClipGateError("owner_accept date must be YYYY-MM-DD")
        try:
            datetime.date.fromisoformat(entry["date"])
        except ValueError:
            raise ClipGateError("owner_accept date must be YYYY-MM-DD")
    accepted_codes = {entry["code"] for entry in owner_accept}
    accepted = [r["code"] for r in reasons if r["code"] in accepted_codes]
    reasons = [r for r in reasons if r["code"] not in accepted_codes]
    return {"pass": len(reasons) == 0, "reasons": reasons, "accepted": accepted}
