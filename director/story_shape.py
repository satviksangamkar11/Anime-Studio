"""Story and script shape lints (card M-23, Opus calibration review 6.1 and 8).

lint(rows, story=None) -> (errors, warnings). rows: the pack rows in shot order (editorial_duration_sec, optional
arc_beat, shape_hook_type, voice_rest, audio_and_dialogue_track). story: the story.json dict (premise, reel_target_s).

A pack is "new format" when story has a premise key or any row has arc_beat. Then every rule is an error.
An old pack (neither) gets warnings only, so it still loads.
voice_rest is [t0, t1] in SHOT-relative seconds (G11, one clock with blocking and cue_sheet); reel_window() converts.
"""

ARC_ORDER = ("hook", "setup", "escalation", "payoff")
HOOK_TYPES = ("kinetic", "scale_tableau", "voice_call", "none")
PREMISE_KEYS = ("character", "goal", "obstacle", "stakes", "payoff")
TARGET_RANGE = (25.0, 75.0)
LONG_FROM = 25.0
SHORT_MAX = 4.4
CENTRE_MIN = 10.0
PAYOFF_MIN = 5.0
METRO_GAP = 0.5
REST_RANGE = (2.0, 4.0)


def _num(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _dur(row):
    value = row.get("editorial_duration_sec")
    return float(value) if _num(value) else 0.0


def _narrated(row):
    track = row.get("audio_and_dialogue_track")
    narr = track.get("narration_by_lang") if isinstance(track, dict) else None
    return isinstance(narr, dict) and any(bool(v) for v in narr.values())


def reel_window(rows, index, key="voice_rest"):
    """Reel-second [t0, t1] of rows[index][key] (shot-relative): shot start + value. None when absent or unreadable."""
    win = rows[index].get(key)
    if not (isinstance(win, list) and len(win) == 2 and all(_num(v) for v in win)):
        return None
    start = sum(_dur(r) for r in rows[:index])
    return [start + win[0], start + win[1]]


def is_new_format(rows, story):
    return "premise" in story or any("arc_beat" in r for r in rows)


def shape_view(rows):
    """Copies of the rows as the lints read them. FIELD NAMES: the story-shape pattern (kinetic | scale_tableau |
    voice_call | none) lives in row key shape_hook_type; row key hook_type is the H3 hook word (reveal, ...) and is
    never read here. A row without shape_hook_type takes it from its blocking sheet's hook_type (same vocabulary,
    blocking/1.1) when that is set. A null voice_rest means no rest."""
    out = []
    for r in rows:
        r = dict(r)
        if "shape_hook_type" in r and r["shape_hook_type"] is None:   # null = not set (only shot 1 carries it), like voice_rest
            r.pop("shape_hook_type")
        sheet = r.get("blocking")
        if "shape_hook_type" not in r and isinstance(sheet, dict) and sheet.get("hook_type") is not None:
            r["shape_hook_type"] = sheet["hook_type"]
        if r.get("voice_rest") is None:
            r.pop("voice_rest", None)
        out.append(r)
    return out


def lint(rows, story=None):
    story = story if isinstance(story, dict) else {}
    rows = shape_view(rows)
    new = is_new_format(rows, story)
    errors = []
    warnings = []

    def add(code, text):
        (errors if new else warnings).append(code + " " + text)

    # SHAPE-01 premise
    premise = story.get("premise")
    if premise is None:
        add("SHAPE-01", "story.json has no premise (character, goal, obstacle, stakes, payoff)")
    elif not isinstance(premise, dict):
        add("SHAPE-01", "premise must be an object")
    else:
        for key in PREMISE_KEYS:
            value = premise.get(key)
            if not isinstance(value, str) or not value.strip():
                add("SHAPE-01", "premise.%s is empty" % key)

    # SHAPE-02 reel_target_s (optional; a range outside 25-75 s is only a warning)
    target = story.get("reel_target_s")
    if target is not None:
        if not _num(target):
            errors.append("SHAPE-02 reel_target_s must be a number of seconds")
        elif not TARGET_RANGE[0] <= target <= TARGET_RANGE[1]:
            warnings.append("SHAPE-02 reel_target_s %s is outside 25-75 s" % target)

    total = sum(_dur(r) for r in rows)
    durs = [_dur(r) for r in rows]
    beats = [r.get("arc_beat") for r in rows]

    # SHAPE-03 to SHAPE-06 arc: order, hook first, payoff at the end
    if not rows or not all(b in ARC_ORDER for b in beats):
        missing = [str(r.get("id")) for r in rows if r.get("arc_beat") not in ARC_ORDER]
        add("SHAPE-03", "arc_beat must be hook|setup|escalation|payoff on each shot (missing: %s)"
            % (", ".join(missing) or "no shots"))
    else:
        idx = [ARC_ORDER.index(b) for b in beats]
        if any(b < a for a, b in zip(idx, idx[1:])):
            add("SHAPE-04", "arc beats out of order: " + " -> ".join(beats))
        if beats[0] != "hook":
            add("SHAPE-05", "shot 1 must be the hook (is %s)" % beats[0])
        payoff = sum(d for d, b in zip(durs, beats) if b == "payoff")
        if payoff < PAYOFF_MIN or beats[-1] != "payoff":
            add("SHAPE-06", "payoff must cover the last 5 s (payoff shots %.1f s, last beat %s)"
                % (payoff, beats[-1]))

    # SHAPE-07 a short shot and a centrepiece in a reel of 25 s or more
    if total >= LONG_FROM:
        if not any(d <= SHORT_MAX for d in durs):
            add("SHAPE-07", "reel of %.1f s needs one shot <= 4.4 s" % total)
        if not any(d >= CENTRE_MIN for d in durs):
            add("SHAPE-07", "reel of %.1f s needs one centrepiece shot >= 10 s" % total)

    # SHAPE-08 anti-metronome: consecutive shots never within 0.5 s of each other's length
    for i in range(len(rows) - 1):
        if abs(durs[i] - durs[i + 1]) <= METRO_GAP:
            add("SHAPE-08", "%s and %s differ by %.1f s or less (metronome)"
                % (rows[i].get("id"), rows[i + 1].get("id"), abs(durs[i] - durs[i + 1])))

    # SHAPE-09 shape_hook_type
    for r in rows:
        if "shape_hook_type" in r and r["shape_hook_type"] not in HOOK_TYPES:
            add("SHAPE-09", "%s shape_hook_type %r is not one of %s"
                % (r.get("id"), r["shape_hook_type"], ", ".join(HOOK_TYPES)))
    if rows and rows[0].get("shape_hook_type") == "none" and any(_narrated(r) for r in rows):
        add("SHAPE-09", "shot 1 shape_hook_type none is refused in a narrated reel")

    # SHAPE-10 voice_rest: shot-relative [t0, t1] inside its own shot, 2-4 s long
    for r, dur in zip(rows, durs):
        if "voice_rest" not in r:
            continue
        rest = r["voice_rest"]
        if not (isinstance(rest, list) and len(rest) == 2 and all(_num(v) for v in rest)):
            add("SHAPE-10", "%s voice_rest must be [t0, t1] numbers" % r.get("id"))
            continue
        t0, t1 = rest
        if not 0 <= t0 < t1 <= dur:
            add("SHAPE-10", "%s voice_rest %s is outside its shot (0-%.1f s)" % (r.get("id"), rest, dur))
        elif not REST_RANGE[0] <= t1 - t0 <= REST_RANGE[1]:
            add("SHAPE-10", "%s voice_rest span %.1f s is outside 2-4 s" % (r.get("id"), t1 - t0))

    return errors, warnings
