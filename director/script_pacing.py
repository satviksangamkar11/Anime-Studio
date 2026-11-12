"""Pacing inspection of a reel script (J9b). Input checks come from script_hook.validate_shots."""

import functools
import json
import math
import os

import script_hook

SUPPORTED_LANGS = ("en", "hi", "mr")

# Default length window (warning only) when the story gives no reel_target_s.
LENGTH_WINDOW_S = (60.0, 75.0)
# ponytail: fixed +-10% band around a story target; widen only if reels show it is too tight.
LENGTH_TOLERANCE_FRAC = 0.10
REHOOK_MIN_TOTAL_S = 36.0
_CORE_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "core", "core.json")


@functools.lru_cache(maxsize=1)
def _default_core():
    with open(_CORE_PATH, encoding="utf8") as handle:
        return json.load(handle)


def _rehook_frac(core):
    source = _default_core() if core is None else core
    lo, hi = source["retention"]["rehook_window_frac"]
    return float(lo), float(hi)


def _length_window(story):
    if not isinstance(story, dict) or "reel_target_s" not in story:
        return LENGTH_WINDOW_S, None
    target = story["reel_target_s"]
    if isinstance(target, bool) or not isinstance(target, (int, float)):
        raise ValueError("story reel_target_s must be a positive finite number")
    if not math.isfinite(target) or target <= 0:
        raise ValueError("story reel_target_s must be a positive finite number")
    band = LENGTH_TOLERANCE_FRAC * target
    return (target - band, target + band), target


def _seconds(shot, seconds_override):
    # Lock seconds (O18) replace the script seconds for each id present in the override.
    if seconds_override is not None and shot["id"] in seconds_override:
        value = seconds_override[shot["id"]]
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError("seconds_override for %s must be a positive finite number" % (shot["id"],))
        if value <= 0 or value != value or value in (float("inf"), float("-inf")):
            raise ValueError("seconds_override for %s must be a positive finite number" % (shot["id"],))
        return float(value)
    value = shot["seconds"]
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
        raise ValueError("shot %s seconds must be a positive finite number" % (shot["id"],))
    return float(value)


def inspect_pacing(shots, lang, seconds_override=None, core=None, story=None):
    """Return {"pass", "problems", "warnings"} for a reel shot list.

    pass is True when problems is empty. warnings never fail the check.
    core: parsed core.json (default: core/core.json) for retention.rehook_window_frac.
    story: optional story dict; reel_target_s sets the length target (default window 60-75 s)."""
    if lang not in SUPPORTED_LANGS:
        raise ValueError("unsupported language: %r" % (lang,))
    script_hook.validate_shots(shots)

    problems = []
    total = 0.0
    for shot in shots:
        total += _seconds(shot, seconds_override)

    # P1 dead air: within a shot gap > 1.5 s; later shot first line > 2.0 s after its start.
    for index, shot in enumerate(shots):
        lines = shot["lines"]
        rest = shot.get("voice_rest")                      # RULE 59(3)/(6): a planned shot-relative voice rest is not dead air
        rest = rest if isinstance(rest, list) and len(rest) == 2 and all(isinstance(v, (int, float)) for v in rest) else None
        if len(lines) >= 2:
            prev_end = lines[0]["end_s"]
            for line in lines[1:]:
                gap = line["start_s"] - prev_end
                if rest:
                    gap -= max(0.0, min(line["start_s"], rest[1]) - max(prev_end, rest[0]))
                if gap > 1.5:
                    problems.append("dead air inside shot %s: gap %.1f s > 1.5 s" % (shot["id"], gap))
                prev_end = line["end_s"]
        if index > 0 and lines:
            first_start = lines[0]["start_s"]
            if first_start > 2.0:
                problems.append("dead air before first line in shot %s: %.1f s > 2.0 s" % (shot["id"], first_start))

    # P2 payoff: last shot must have an event or line starting in its last 5 s.
    last_shot = shots[-1]
    last_duration = _seconds(last_shot, seconds_override)
    payoff_start = last_duration - 5.0
    if payoff_start < 0.0:
        payoff_start = 0.0
    has_payoff = False
    for event in last_shot["events"]:
        event_t = float(event["t"])
        if event_t >= payoff_start:
            has_payoff = True
            break
    if not has_payoff:
        for line in last_shot["lines"]:
            line_start = float(line["start_s"])
            if line_start >= payoff_start:
                has_payoff = True
                break
    if not has_payoff:
        problems.append("payoff missing in last shot %s: no event or line in last 5 s" % (last_shot["id"],))

    # P3 re-hook: some shot whose absolute start is inside rehook_window_frac x total (core.json,
    # inclusive) must have an event or line starting within 1.0 s of its own start.
    # Skipped when the reel is shorter than 36 s.
    if total >= REHOOK_MIN_TOTAL_S:
        lo_frac, hi_frac = _rehook_frac(core)
        lo_s, hi_s = lo_frac * total, hi_frac * total
        absolute_start = 0.0
        rehook_ok = False
        for shot in shots:
            if lo_s <= absolute_start <= hi_s:
                shot_has_hook = False
                for event in shot["events"]:
                    event_t = float(event["t"])
                    if 0.0 <= event_t <= 1.0:
                        shot_has_hook = True
                        break
                if not shot_has_hook:
                    for line in shot["lines"]:
                        line_start = float(line["start_s"])
                        if 0.0 <= line_start <= 1.0:
                            shot_has_hook = True
                            break
                if shot_has_hook:
                    rehook_ok = True
                    break
            absolute_start += _seconds(shot, seconds_override)
        if not rehook_ok:
            problems.append(
                "re-hook missing: no shot starting %.1f-%.1f s has an event or line within 1.0 s" % (lo_s, hi_s)
            )

    # P4 length: window from story reel_target_s (+-10%) or the default 60-75 s. Warning only, never a fail.
    warnings = []
    (len_lo, len_hi), target = _length_window(story)
    if total < len_lo or total > len_hi:
        if target is None:
            warnings.append("length warning: reel is %.1f s, must be between 60 and 75 s" % (total,))
        else:
            warnings.append("length warning: reel is %.1f s, story target is %.1f s (+-10%%)" % (total, target))

    return {"pass": len(problems) == 0, "problems": problems, "warnings": warnings}
