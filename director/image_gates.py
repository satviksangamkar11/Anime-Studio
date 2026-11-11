import math

import numpy as np


class GateError(ValueError):
    pass


def to_float01(img):
    arr = np.asarray(img)
    if arr.ndim != 3 or arr.shape[2] != 3:
        raise GateError("image must have shape (H, W, 3)")
    if arr.dtype == object:
        raise GateError("object dtype is not supported")
    if arr.dtype == np.uint8:
        return arr.astype(np.float64) / 255.0
    if np.issubdtype(arr.dtype, np.floating):
        raise GateError("convert to uint8 0..255 first")
    raise GateError("unsupported image dtype")


def _check_bool_mask(mask):
    mask = np.asarray(mask)
    if mask.dtype != bool:
        raise GateError("masks must be bool")
    return mask


def dilate(mask, px):
    if isinstance(px, bool) or not isinstance(px, (int, np.integer)):
        raise GateError("px must be an integer >= 0")
    if px < 0:
        raise GateError("px must be >= 0")
    mask = _check_bool_mask(mask)
    if px == 0:
        return mask.copy()
    # Dilating by max(H, W) already reaches every pixel of the frame, so larger px gives the same result.
    out = mask.copy()
    for _ in range(min(int(px), max(mask.shape))):
        padded = np.zeros((out.shape[0] + 2, out.shape[1] + 2), dtype=bool)
        padded[1:-1, 1:-1] = out
        out = (
            padded[:-2, :-2]
            | padded[:-2, 1:-1]
            | padded[:-2, 2:]
            | padded[1:-1, :-2]
            | padded[1:-1, 1:-1]
            | padded[1:-1, 2:]
            | padded[2:, :-2]
            | padded[2:, 1:-1]
            | padded[2:, 2:]
        )
    return out


def block_ssim(a, b, valid, block=8):
    a = to_float01(a)
    b = to_float01(b)
    valid = _check_bool_mask(valid)
    if a.shape != b.shape:
        raise GateError("image shapes must match")
    if valid.shape != a.shape[:2]:
        raise GateError("valid mask shape must match image")
    h, w = a.shape[:2]
    gray_a = a.mean(axis=2)
    gray_b = b.mean(axis=2)
    c1 = 0.01 ** 2
    c2 = 0.03 ** 2
    scores = []
    for y in range(0, h - block + 1, block):
        for x in range(0, w - block + 1, block):
            tile_valid = valid[y:y + block, x:x + block]
            if not tile_valid.all():
                continue
            ta = gray_a[y:y + block, x:x + block]
            tb = gray_b[y:y + block, x:x + block]
            mu_a = ta.mean()
            mu_b = tb.mean()
            var_a = ta.var()
            var_b = tb.var()
            cov = ((ta - mu_a) * (tb - mu_b)).mean()
            num = (2 * mu_a * mu_b + c1) * (2 * cov + c2)
            den = (mu_a ** 2 + mu_b ** 2 + c1) * (var_a + var_b + c2)
            scores.append(num / den)
    if not scores:
        raise GateError("no comparable area")
    return float(sum(scores) / len(scores))


def background_lock(img_a, img_b, mask_a, mask_b, dilate_px=24, min_ssim=0.97, max_l1=3.0 / 255.0,
                    min_area_fraction=0.25):
    """Check that the background is unchanged between frames A and B outside the masks.

    min_ssim=0.97 and max_l1=3/255 are uncalibrated knobs: tune them on reel 2 B frames (O16).
    """
    img_a = np.asarray(img_a)
    img_b = np.asarray(img_b)
    mask_a = _check_bool_mask(mask_a)
    mask_b = _check_bool_mask(mask_b)
    if img_a.shape != img_b.shape:
        raise GateError("image shapes must match")
    if mask_a.shape != img_a.shape[:2] or mask_b.shape != img_a.shape[:2]:
        raise GateError("mask shapes must match image")
    excluded = dilate(mask_a, dilate_px) | dilate(mask_b, dilate_px)
    valid = ~excluded
    ssim = block_ssim(img_a, img_b, valid)
    fa = to_float01(img_a)
    fb = to_float01(img_b)
    diff = np.abs(fa - fb)
    compared = diff[valid]
    mean_l1 = float(compared.mean()) if compared.size else 0.0
    area_fraction = float(valid.sum()) / float(valid.size)
    reasons = []
    if not math.isfinite(ssim):
        reasons.append("ssim is not a finite number")
    elif ssim < min_ssim:
        reasons.append("ssim %.4f below %.4f" % (ssim, min_ssim))
    if mean_l1 > max_l1:
        reasons.append("mean L1 %.5f above %.5f" % (mean_l1, max_l1))
    if area_fraction < min_area_fraction:
        reasons.append("comparable area %.4f below %.4f" % (area_fraction, min_area_fraction))
    result = {
        "ssim": float(ssim),
        "mean_l1": mean_l1,
        "pass": not reasons,
        "area_fraction": area_fraction,
        "reasons": reasons,
    }
    return result


def _check_int(value):
    if isinstance(value, bool) or not isinstance(value, (int, np.integer)):
        raise GateError("counts must be int, not bool or float")
    return value


def cast_parity(count_a, count_b, required_cast_count, entry_exit_allowed=False):
    count_a = _check_int(count_a)
    count_b = _check_int(count_b)
    required_cast_count = _check_int(required_cast_count)
    if count_a < 0 or count_b < 0:
        raise GateError("counts must be non-negative")
    problems = []
    if count_a != count_b and not entry_exit_allowed:
        problems.append("cast count differs between A and B (%d vs %d)" % (count_a, count_b))
    if count_a < required_cast_count:
        problems.append("A shows fewer people than the script requires (%d < %d)" % (count_a, required_cast_count))
    if count_b < required_cast_count:
        problems.append("B shows fewer people than the script requires (%d < %d)" % (count_b, required_cast_count))
    return problems


def limb_parity(arms_a, arms_b):
    arms_a = _check_int(arms_a)
    arms_b = _check_int(arms_b)
    if arms_a != arms_b:
        return ["arm count differs between A and B (%d vs %d)" % (arms_a, arms_b)]
    return []


def posture_state(hip_ankle_over_torso):
    if hip_ankle_over_torso > 1.1:
        return "standing"
    if hip_ankle_over_torso < 0.65:
        return "seated"
    return "unknown"


def posture_matches(state_a, state_b, script_start, script_end):
    problems = []
    if state_a == "unknown":
        if script_start is not None:
            problems.append("A posture unclear")
    elif script_start is not None and state_a != script_start:
        problems.append("A is %s but the script says %s" % (state_a, script_start))
    if state_b == "unknown":
        if script_end is not None:
            problems.append("B posture unclear")
    elif script_end is not None and state_b != script_end:
        problems.append("B is %s but the script says %s" % (state_b, script_end))
    return problems


def feasible_motion(displacement, seconds, max_per_sec):
    if not math.isfinite(displacement) or not math.isfinite(seconds) or not math.isfinite(max_per_sec):
        raise GateError("inputs must be finite")
    if seconds <= 0:
        raise GateError("seconds must be > 0")
    if displacement < 0:
        raise GateError("displacement must be >= 0")
    return displacement / seconds <= max_per_sec
