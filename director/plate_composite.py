"""Composite keyframe B's character onto keyframe A's background."""

import os
import tempfile


class CompositeError(ValueError):
    """Raised when plate compositing inputs are invalid."""


def load_rgb(path):
    """Load an RGB image as a uint8 (H, W, 3) numpy array via Pillow."""
    from PIL import Image

    if not os.path.isfile(path):
        raise FileNotFoundError("no such file: %s" % path)
    with Image.open(path) as im:
        im = im.convert("RGB")
        arr = __import__("numpy").array(im, dtype="uint8")
    return arr


def save_rgb(path, img):
    """Atomically save a uint8 (H, W, 3) RGB image via Pillow."""
    import numpy as np

    if not isinstance(img, np.ndarray):
        raise CompositeError("image must be a numpy array")
    if img.dtype != np.uint8:
        raise CompositeError("image must be uint8")
    if img.ndim != 3 or img.shape[2] != 3:
        raise CompositeError("image must have shape (H, W, 3)")

    _, ext = os.path.splitext(path)
    if ext.lower() != ".png":
        raise CompositeError("save_rgb writes PNG only; use a .png name")

    folder = os.path.dirname(os.path.abspath(path))
    fd, tmp_path = tempfile.mkstemp(dir=folder, suffix=".png")
    os.close(fd)
    try:
        from PIL import Image

        Image.fromarray(img).save(tmp_path)
        os.replace(tmp_path, path)
    except BaseException:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        raise


def _validate_images(img_a, img_b):
    import numpy as np

    if not isinstance(img_a, np.ndarray) or not isinstance(img_b, np.ndarray):
        raise CompositeError("images must be numpy arrays")
    if img_a.ndim != 3 or img_a.shape[2] != 3:
        raise CompositeError("image must have shape (H, W, 3)")
    if img_b.ndim != 3 or img_b.shape[2] != 3:
        raise CompositeError("image must have shape (H, W, 3)")
    if img_a.shape != img_b.shape:
        raise CompositeError("image shapes must match")
    if img_a.dtype != np.uint8 or img_b.dtype != np.uint8:
        raise CompositeError("images must be uint8")


def _validate_mask(mask, shape):
    import numpy as np

    if not isinstance(mask, np.ndarray):
        raise CompositeError("mask must be a numpy array")
    if mask.dtype != bool:
        raise CompositeError("mask must be bool")
    if mask.shape != shape[:2]:
        raise CompositeError("mask shape must match image (H, W)")


def _dilate_square(mask, px):
    """Chebyshev-square dilation by px, the same operation as image_gates.dilate."""
    if px <= 0:
        return mask.copy()
    import image_gates

    px = int(px)
    return image_gates.dilate(mask, px)


# ponytail: python loop, O(HW); swap for scipy.ndimage.label if 768x1344 is slow
def _label_components(mask):
    import numpy as np

    h, w = mask.shape
    labels = np.zeros((h, w), dtype=np.int64)
    parent = [0]
    current = 0

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    def union(a, b):
        ra = find(a)
        rb = find(b)
        if ra != rb:
            parent[rb] = ra

    for y in range(h):
        for x in range(w):
            if not mask[y, x]:
                continue
            neighbors = []
            if y > 0 and labels[y - 1, x] != 0:
                neighbors.append(labels[y - 1, x])
            if x > 0 and labels[y, x - 1] != 0:
                neighbors.append(labels[y, x - 1])
            if not neighbors:
                current += 1
                labels[y, x] = current
                parent.append(current)
            else:
                lab = min(neighbors)
                labels[y, x] = lab
                for n in neighbors:
                    union(lab, n)

    for y in range(h):
        for x in range(w):
            lab = labels[y, x]
            if lab != 0:
                labels[y, x] = find(lab)
    return labels, current


def _remove_small(mask, min_area):
    if min_area <= 1:
        return mask.copy()
    labels, n = _label_components(mask)
    import numpy as np

    counts = np.bincount(labels.ravel())
    out = np.zeros_like(mask, dtype=bool)
    for lab in range(1, len(counts)):
        if counts[lab] >= min_area:
            out[labels == lab] = True
    return out


def diff_mask(img_a, img_b, threshold=24, dilate_px=6, min_area=50):
    """Return a bool mask of changed pixels, dilated and cleaned."""
    import numpy as np

    _validate_images(img_a, img_b)
    if img_a.dtype != np.uint8 or img_b.dtype != np.uint8:
        raise CompositeError("images must be uint8")

    diff = np.abs(img_a.astype(np.int16) - img_b.astype(np.int16)).max(axis=2)
    mask = diff > threshold
    mask = _dilate_square(mask, dilate_px)
    mask = _remove_small(mask, min_area)
    return mask


def composite(img_a, img_b, mask, feather_px=0):
    """Composite B over A where mask is True, with optional feathered edge."""
    import numpy as np

    _validate_images(img_a, img_b)
    _validate_mask(mask, img_a.shape)

    if feather_px < 0:
        raise CompositeError("feather_px must be non-negative")

    a = img_a.astype(np.float64)
    b = img_b.astype(np.float64)
    m = mask.astype(np.float64)

    if feather_px > 0:
        m = _box_blur(m, feather_px)
        m = np.clip(m, 0.0, 1.0)

    m3 = m[:, :, None]
    out = a * (1.0 - m3) + b * m3
    out = np.clip(out, 0, 255).astype(np.uint8)
    return out


def _box_blur(mask, px):
    """Box blur of radius px with edge padding, computed from an integral image."""
    import numpy as np

    h, w = mask.shape
    padded = np.pad(np.asarray(mask, dtype=np.float64), px, mode="edge")
    integral = np.zeros((padded.shape[0] + 1, padded.shape[1] + 1), dtype=np.float64)
    integral[1:, 1:] = padded.cumsum(axis=0).cumsum(axis=1)
    k = 2 * px + 1
    window = integral[k:k + h, k:k + w] - integral[0:h, k:k + w] - integral[k:k + h, 0:w] + integral[0:h, 0:w]
    return window / float(k * k)


def hole_fraction(char_mask_a, char_mask_b):
    """Fraction of image that was character in A but not in B."""
    import numpy as np

    if not isinstance(char_mask_a, np.ndarray) or not isinstance(char_mask_b, np.ndarray):
        raise CompositeError("masks must be numpy arrays")
    if char_mask_a.shape != char_mask_b.shape:
        raise CompositeError("mask shapes must match")
    if char_mask_a.dtype != bool or char_mask_b.dtype != bool:
        raise CompositeError("masks must be bool")

    holes = char_mask_a & ~char_mask_b
    total = char_mask_a.size
    if total == 0:
        return 0.0
    return float(holes.sum()) / float(total)


def composite_is_safe(char_mask_a, char_mask_b, max_hole_fraction=0.02):
    """Return a dict describing whether compositing is safe."""
    hf = hole_fraction(char_mask_a, char_mask_b)
    safe = hf <= max_hole_fraction
    if safe:
        reason = "character does not uncover background A never showed"
    else:
        reason = "character uncovers background that A does not show; use B unchanged or re-edit"
    return {"safe": bool(safe), "hole_fraction": float(hf), "reason": reason}


def plan(img_a, img_b, char_mask_a, char_mask_b, max_hole_fraction=0.02):
    """Plan whether to composite or keep B unchanged."""
    import numpy as np

    _validate_images(img_a, img_b)
    _validate_mask(char_mask_a, img_a.shape)
    _validate_mask(char_mask_b, img_a.shape)

    safety = composite_is_safe(char_mask_a, char_mask_b, max_hole_fraction=max_hole_fraction)
    if safety["safe"]:
        use = "composite"
    else:
        use = "keep_b"
    return {
        "use": use,
        "hole_fraction": float(safety["hole_fraction"]),
        "mask_area": float(char_mask_b.sum()),
    }
