"""Pacing inspection of a reel script (J9b). Input checks come from script_hook.validate_shots."""

import script_hook

SUPPORTED_LANGS = ("en", "hi", "mr")


def _seconds(shot, seconds_override):
    # Lock seconds (O18) replace the script seconds for each id present in the override.
    if seconds_override is not None and shot["id"] in seconds_override:
        value = seconds_override[shot["id"]]
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError("seconds_override for %s must be a positive finite number" % (shot["id"],))
        if value <= 0 or value != value or value in (float("inf"), float("-inf")):
            raise ValueError("seconds_override for %s must be a positive finite number" % (shot["id"],))
        return float(value)
    return float(shot["seconds"])


def inspect_pacing(shots, lang, seconds_override=None):
    """Return {"pass", "problems", "warnings"} for a reel shot list.

    pass is True when problems is empty. warnings never fail the check (length 60-75 s)."""
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
        if len(lines) >= 2:
            prev_end = lines[0]["end_s"]
            for line in lines[1:]:
                gap = line["start_s"] - prev_end
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

    # P3 re-hook: some shot whose absolute start is between 25 and 35 s must have an event or line
    # starting within 1.0 s of its own start. Skipped when the reel is shorter than 36 s.
    if total >= 36.0:
        absolute_start = 0.0
        rehook_ok = False
        for shot in shots:
            if 25.0 <= absolute_start <= 35.0:
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
            problems.append("re-hook missing: no shot in the 25-35 s window starts with an event or line within 1.0 s")

    # P4 reel length between 60 and 75 s inclusive (warning only, not a hard fail).
    warnings = []
    if total < 60.0 or total > 75.0:
        warnings.append("length warning: reel is %.1f s, must be between 60 and 75 s" % (total,))

    return {"pass": len(problems) == 0, "problems": problems, "warnings": warnings}
