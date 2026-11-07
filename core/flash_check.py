"""Flash safety (WP6, spec 4.4). F1 = luminance general-flash screen (FAIL), F2 = saturated-red screen (WARN).
The core logic is pure (grids in, entries out); only check_flash touches ffmpeg, via core.frame_metrics.
F1 is a screening check based on the WCAG definition. It is not a certified Harding test."""
import tempfile

from core.style_pack import load_core

REPORT_HEADER = ("F1 is a screening check based on the WCAG general-flash definition. "
                 "It is not a certified Harding test.")


def _core(core):
    return load_core() if core is None else core


def _flat(grid):
    out = []
    for v in grid:
        if isinstance(v, (list, tuple)):
            out.extend(float(x) for x in v)
        else:
            out.append(float(v))
    return out


def _entry(rule, level, message):
    return {"rule": rule, "level": level, "shot": None, "episode": None, "message": message}


def find_transitions(prev_grid, cur_grid, core=None):
    """+1 when enough cells brighten, -1 when enough darken, 0 otherwise (spec 4.4, F1)."""
    cfg = _core(core)["flash"]
    prev, cur = _flat(prev_grid), _flat(cur_grid)
    total = len(prev)
    if total == 0 or len(cur) != total:
        return 0
    min_change, dark_below = cfg["min_rel_luma_change"] - 1e-9, cfg["darker_below"]
    inc = dec = 0
    for a, b in zip(prev, cur):
        if min(a, b) >= dark_below:
            continue
        change = b - a
        if change >= min_change:
            inc += 1
        elif change <= -min_change:
            dec += 1
    up = inc / total >= cfg["area_frac"]
    down = dec / total >= cfg["area_frac"]
    if up and down:
        return 1 if inc >= dec else -1   # tie goes to brightening
    if up:
        return 1
    if down:
        return -1
    return 0


def _merged_transitions(grids, core, exempt):
    """[(frame, direction)] in order; consecutive same-direction transitions merge into one."""
    skip = set(exempt)
    out = []
    for i in range(1, len(grids)):
        d = find_transitions(grids[i - 1], grids[i], core)
        if d == 0 or i in skip:
            continue
        if out and out[-1][1] == d:
            continue
        out.append((i, d))
    return out


def _worst_window(transitions, fps):
    """(flashes, start_frame) of the 1 s window with the most flashes; flashes = ceil(transitions / 2).
    An odd transition still counts as a flash: 8 alternating frames (7 changes) are 4 flashes (DECISION 2026-11-07)."""
    frames = [f for f, _ in transitions]
    best = (0, 0)
    for k, start in enumerate(frames):
        count = 0
        for f in frames[k:]:
            if f >= start + fps:
                break
            count += 1
        flashes = (count + 1) // 2
        if flashes > best[0]:
            best = (flashes, start)
    return best


def _report(signal, fps, cfg, exempt, rule, level, what, core):
    fps = max(1, int(fps))
    worst, start = _worst_window(_merged_transitions(signal, core, exempt), fps)
    limit = cfg["max_flashes_per_s"]
    if worst <= limit:
        return []
    return [_entry(rule, level, f"{worst} {what} in the 1 s window starting at {start / fps:.2f} s "
                                f"(frame {start}); limit {limit} per second")]


def f1_report(grids, fps, core=None, exempt_frames=()):
    """grids: per-frame luminance grids (8x8 flattened or nested). FAIL when a 1 s window holds more than
    max_flashes_per_s flashes."""
    full = _core(core)
    return _report(grids, fps, full["flash"], exempt_frames, "F1", "FAIL", "luminance flashes", full)


def _red_signal(grids, red_grids, cfg):
    rmin, lmin = cfg["red_ratio_min"], cfg["red_min_luma"]
    signal = []
    for lum_grid, red_grid in zip(grids, red_grids):
        lum, red = _flat(lum_grid), _flat(red_grid)
        signal.append([r if (r >= rmin and y >= lmin) else 0.0 for y, r in zip(lum, red)])
    return signal


def f2_report(grids, red_grids, fps, core=None):
    """Saturated-red flashes, WARN only. A cell counts when red share >= red_ratio_min and its
    luminance >= red_min_luma. Returns [] when flash.red_flash is false."""
    full = _core(core)
    cfg = full["flash"]
    if not cfg.get("red_flash"):
        return []
    return _report(_red_signal(grids, red_grids, cfg), fps, cfg, (), "F2", "WARN",
                   "saturated-red flashes", full)


def with_header(entries):
    return {"note": REPORT_HEADER, "entries": entries}


def check_flash(clip, core=None, tmp_dir=None):
    """F1 + F2 for one clip: frames at 1/4 size, 8x8 grids, then the pure checks."""
    from PIL import Image

    from core.frame_metrics import extract_frames, grid_luma, grid_red_share

    full = _core(core)
    own = None
    if tmp_dir is None:
        own = tempfile.TemporaryDirectory()
        tmp_dir = own.name
    try:
        lum, red = [], []
        for _, path in extract_frames(clip, tmp_dir, scale=0.25, every=1):
            with Image.open(path) as im:
                lum.append(grid_luma(im))
                red.append(grid_red_share(im))
    finally:
        if own is not None:
            own.cleanup()
    fps = full.get("fps", 24)
    return f1_report(lum, fps, full) + f2_report(lum, red, fps, full)
