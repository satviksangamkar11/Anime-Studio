import os
import sys
import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import plate_composite


def _reference_remove_small(mask, min_area):
    h, w = mask.shape
    labels = [[0] * w for _ in range(h)]
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
            if y > 0 and labels[y - 1][x] != 0:
                neighbors.append(labels[y - 1][x])
            if x > 0 and labels[y][x - 1] != 0:
                neighbors.append(labels[y][x - 1])
            if not neighbors:
                current += 1
                labels[y][x] = current
                parent.append(current)
            else:
                lab = min(neighbors)
                labels[y][x] = lab
                for n in neighbors:
                    union(lab, n)

    for y in range(h):
        for x in range(w):
            lab = labels[y][x]
            if lab != 0:
                labels[y][x] = find(lab)

    counts = {}
    for y in range(h):
        for x in range(w):
            lab = labels[y][x]
            if lab != 0:
                counts[lab] = counts.get(lab, 0) + 1

    out = [[False] * w for _ in range(h)]
    for y in range(h):
        for x in range(w):
            lab = labels[y][x]
            if lab != 0 and counts[lab] >= min_area:
                out[y][x] = True

    import numpy as np
    result = np.zeros((h, w), dtype=bool)
    for y in range(h):
        for x in range(w):
            result[y, x] = out[y][x]
    return result


def test_remove_small_matches_reference():
    import numpy as np

    rng = np.random.default_rng(1)
    mask = rng.random((64, 64)) < 0.5
    min_area = 10
    expected = _reference_remove_small(mask, min_area)
    actual = plate_composite._remove_small(mask, min_area)
    assert np.array_equal(actual, expected)


def test_dilate_accepts_float_px():
    import numpy as np

    img_a = np.zeros((10, 10, 3), dtype=np.uint8)
    img_b = np.zeros((10, 10, 3), dtype=np.uint8)
    img_b[3:7, 3:7] = 255
    result_float = plate_composite.diff_mask(img_a, img_b, dilate_px=6.0)
    result_int = plate_composite.diff_mask(img_a, img_b, dilate_px=6)
    assert np.array_equal(result_float, result_int)


def test_many_components_fast():
    import numpy as np
    import time

    mask = np.zeros((400, 400), dtype=bool)
    count = 0
    y = 0
    while count < 2000 and y < 400:
        x = 0
        while x < 400 and count < 2000:
            mask[y, x] = True
            count = count + 1
            x = x + 3
        y = y + 3

    start = time.time()
    result = plate_composite._remove_small(mask, 2)
    elapsed = time.time() - start
    assert elapsed < 2.0
    assert result.sum() == 0
